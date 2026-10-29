"""
routing.py
All routing strategies compared in the hybrid-routing study.

Every strategy sees exactly the same information the SDN controller has at
flow-setup time:
    - the topology (G)
    - the current measured load on every link (Mbps), including long-lived
      flows placed in earlier intervals
    - the ML congestion forecast for every link (utilization fraction)
    - the flow's demand and its *predicted* class/priority (from the
      TrafficClassifier - never the ground truth)

Strategies
    StaticDijkstra      classic OSPF-like shortest path on fixed link delay
    ECMP                equal-cost multipath (hop count), hash-based split
    LoadAwareDijkstra   the project's original AI-adaptive controller:
                        Dijkstra on load + forecast + priority weighted costs
    TelemetryAwareDijkstra
                        control baseline: LoadAwareDijkstra that also adds the
                        measured per-link excess delay/loss (same telemetry the
                        hybrid gets), to separate "learning" from "more data"
    QRouting            pure RL ablation: hop-by-hop Q-routing
                        (Boyan & Littman, 1994), no Dijkstra involved
    HybridDijkstraQL    PROPOSED: Dijkstra/Yen k-shortest candidate paths
                        + Q-learning path selection + Dijkstra fallback
                        (v2 adds a load-balance reward term and measured
                        link telemetry as a feature; v1 = both switched off)

Failed links (net.up == False) are never used by any strategy: the
controller sees port-down events and recomputes on net.graph().
"""

import zlib
from itertools import islice

import networkx as nx
import numpy as np


class Strategy:
    name = "base"
    learns = False

    def __init__(self, net):
        self.net = net

    def reset(self):
        """Called at the start of every episode (simulation run)."""

    def choose(self, flow, load, forecast, train=False):
        raise NotImplementedError

    def observe(self, outcomes, link_cost_ms):
        """Called once per interval with the realised outcome of flows placed in it."""


# --------------------------------------------------------------------------
# Baselines
# --------------------------------------------------------------------------

class LinkTelemetry:
    """EWMA of each link's measured excess cost (queueing delay + priced loss
    above its propagation delay), as an SDN controller would get from
    in-band telemetry or active probing."""

    def __init__(self, net, beta=0.5):
        self.net, self.beta = net, beta
        self.reset()

    def reset(self):
        self.excess = np.zeros(len(self.net.edges))

    def update(self, link_cost_ms):
        self.excess += self.beta * (link_cost_ms - self.net.base - self.excess)


class StaticDijkstra(Strategy):
    name = "Static Dijkstra"

    def __init__(self, net):
        super().__init__(net)
        self.cache = {}

    def choose(self, flow, load, forecast, train=False):
        key = (flow["src"], flow["dst"], self.net.down_key())
        if key not in self.cache:
            self.cache[key] = tuple(nx.shortest_path(self.net.graph(), *key[:2], weight="base_delay_ms"))
        return self.cache[key]


class ECMP(Strategy):
    name = "ECMP"

    def __init__(self, net):
        super().__init__(net)
        self.cache = {}

    def choose(self, flow, load, forecast, train=False):
        key = (flow["src"], flow["dst"], self.net.down_key())
        if key not in self.cache:
            self.cache[key] = [tuple(p) for p in nx.all_shortest_paths(self.net.graph(), *key[:2])]
        paths = self.cache[key]
        # 5-tuple hash in a real switch; flow id is our stand-in
        return paths[zlib.crc32(flow["flow_id"].encode()) % len(paths)]


class LoadAwareDijkstra(Strategy):
    """The original adaptive controller from controller_sim.py, unchanged weights."""
    name = "Load-aware Dijkstra"
    PRIORITY_FACTOR = {1: 1.6, 2: 1.3, 3: 1.0, 4: 0.7}

    def _extra(self, e):
        return 0.0

    def choose(self, flow, load, forecast, train=False):
        net = self.net
        pf = self.PRIORITY_FACTOR[flow["priority"]]

        def weight(u, v, d):
            e = net.eid[(u, v)]
            if not net.up[e]:
                return None
            util_ratio = load[e] / net.cap[e]
            congestion_term = (max(0.0, util_ratio) ** 3) * 35
            forecast_term = (max(0.0, forecast[e]) ** 3) * 12
            return d["base_delay_ms"] + (congestion_term + forecast_term + self._extra(e)) * pf

        return tuple(nx.shortest_path(net.G, flow["src"], flow["dst"], weight=weight))


class TelemetryAwareDijkstra(LoadAwareDijkstra):
    """Load-aware Dijkstra + measured per-link excess delay/loss in the link cost."""
    name = "Telemetry-aware Dijkstra"

    def __init__(self, net):
        super().__init__(net)
        self.tele = LinkTelemetry(net)

    def reset(self):
        self.tele.reset()

    def _extra(self, e):
        return max(0.0, self.tele.excess[e])

    def observe(self, outcomes, link_cost_ms):
        self.tele.update(link_cost_ms)


# --------------------------------------------------------------------------
# Ablation: pure reinforcement learning (no Dijkstra)
# --------------------------------------------------------------------------

class QRouting(Strategy):
    """Hop-by-hop Q-routing. Q[x][d][y] = estimated ms to reach d from x via neighbour y."""
    name = "Q-Routing (RL only)"
    learns = True

    def __init__(self, net, alpha=0.3, eps=0.1, seed=0):
        super().__init__(net)
        self.alpha, self.eps = alpha, eps
        self.rng = np.random.default_rng(seed)
        self.Q = {}
        self.pending = []

    def _q(self, x, d):
        if (x, d) not in self.Q:
            self.Q[(x, d)] = {y: 0.0 for y in self.net.G.neighbors(x)}
        return self.Q[(x, d)]

    def choose(self, flow, load, forecast, train=False):
        src, dst = flow["src"], flow["dst"]
        # greedy next-hop walk with backtracking so the path is always loop-free
        path, visited = [src], {src}
        while path[-1] != dst:
            x = path[-1]
            q = self._q(x, dst)
            options = [y for y in q if y not in visited and self.net.up[self.net.eid[(x, y)]]]
            if not options:
                visited.add(path.pop())
                continue
            if train and self.rng.random() < self.eps:
                y = options[self.rng.integers(len(options))]
            else:
                y = min(options, key=lambda n: q[n])
            path.append(y)
            visited.add(y)
        self.pending.append((tuple(path), dst))
        return tuple(path)

    def observe(self, outcomes, link_cost_ms):
        for path, dst in self.pending:
            for x, y in zip(path[:-1], path[1:]):
                hop_cost = link_cost_ms[self.net.eid[(x, y)]]
                future = 0.0 if y == dst else min(self._q(y, dst).values())
                q = self._q(x, dst)
                q[y] += self.alpha * (hop_cost + future - q[y])
        self.pending = []


# --------------------------------------------------------------------------
# Proposed: Hybrid Dijkstra + Q-learning
# --------------------------------------------------------------------------

class HybridDijkstraQL(Strategy):
    """
    Stage 1 (Dijkstra): Yen's k-shortest loop-free paths on propagation delay
            give a small, always-valid candidate set per host pair.
    Stage 2 (Q-learning): a linear Q-function scores each candidate from
            path/state features (extra delay, current and ML-forecast
            bottleneck utilization, traffic class) and picks the best one.
    Stage 3 (Dijkstra fallback): if every candidate would overload a link,
            Dijkstra is re-run on the residual graph (links that can still
            fit the flow) and that path is added as an extra candidate.

    The Q-function is updated once per interval from each placed flow's
    realised reward (latency, loss, and bottleneck headroom). Each decision
    is treated as a one-step episode (gamma = 0), i.e. Q-learning with linear
    function approximation in its contextual-bandit form.

    v2 additions (both off in v1, which then behaves exactly as before):
      balance > 0   the reward also charges each flow its marginal increase
                    of sum(u_e^2) over core links, i.e. the imbalance it adds
                    to the network (minimising sum u^2 for a given total load
                    maximises Jain's fairness); the same quantity is a feature.
      telemetry     measured excess delay/loss of the path (LinkTelemetry) is
                    a feature, so the agent can notice links that are slow or
                    lossy for reasons its load/capacity view does not show.
      nlms          normalised update w += alpha*err*phi/(1+|phi|^2). The plain
                    update diverges once failures / hotspots push features
                    (overload terms) high, because alpha*|phi|^2 exceeds 2;
                    the normalised form is stable for any alpha < 2.
    """
    name = "Hybrid Dijkstra+QL (proposed)"
    learns = True
    IMPORTANCE = {1: 2.0, 2: 1.5, 3: 1.0, 4: 0.5}   # voice, video, web, bulk
    N_FEATURES = 13

    def __init__(self, net, k=4, alpha=0.02, eps=0.1, seed=0, balance=0.0, telemetry=False,
                 nlms=False, name="Hybrid Dijkstra+QL (proposed)"):
        super().__init__(net)
        self.k, self.alpha, self.eps = k, alpha, eps
        self.balance, self.telemetry, self.nlms, self.name = balance, telemetry, nlms, name
        self.rng = np.random.default_rng(seed)
        self.cands = {}
        self.w = np.zeros(self.N_FEATURES)
        self.pending = []
        self.fallbacks = 0
        self.tele = LinkTelemetry(net)

    def reset(self):
        self.tele.reset()

    def _candidates(self, src, dst):
        key = (src, dst, self.net.down_key())
        if key not in self.cands:
            paths = islice(nx.shortest_simple_paths(self.net.graph(), src, dst, weight="base_delay_ms"), self.k)
            self.cands[key] = [tuple(p) for p in paths]
        return self.cands[key]

    def _residual_dijkstra(self, flow, load):
        net = self.net
        G = net.G

        def weight(u, v, d):
            e = net.eid[(u, v)]
            fits = net.up[e] and load[e] + flow["demand_mbps"] <= net.cap[e]
            return d["base_delay_ms"] if fits else None

        try:
            return tuple(nx.shortest_path(G, flow["src"], flow["dst"], weight=weight))
        except nx.NetworkXNoPath:
            return None

    def _features(self, path, flow, load, forecast, ref_delay):
        net = self.net
        e = net.path_eids(path)
        delay = net.base[e].sum()
        cur = min(2.0, ((load[e] + flow["demand_mbps"]) / net.cap[e]).max())
        fc = min(2.0, forecast[e].max())
        sens = 1.0 if flow["priority"] <= 2 else 0.0
        extra = delay / ref_delay - 1.0
        big = flow["demand_mbps"] / 20.0
        tele = min(5.0, max(0.0, self.tele.excess[e].sum()) / 10.0) if self.telemetry else 0.0
        imb = self._imbalance(e, flow, load) if self.balance > 0 else 0.0
        return np.array([
            1.0, extra, len(e) / 5.0,
            cur, cur * cur, fc, fc * fc,
            max(0.0, cur - 0.9) * 10.0,
            sens * extra, sens * cur, big * cur,
            tele, imb,
        ])

    def _imbalance(self, e, flow, load):
        """Marginal increase of sum(u^2) over the path's core links, x10."""
        net = self.net
        e = e[net.core[e]]
        u = load[e] / net.cap[e]
        x = flow["demand_mbps"] / net.cap[e]
        return min(5.0, float((2 * u * x + x * x).sum() * 10.0))

    def choose(self, flow, load, forecast, train=False):
        net = self.net
        cands = list(self._candidates(flow["src"], flow["dst"]))
        ref_delay = net.base[net.path_eids(cands[0])].sum()

        projected = [((load[e] + flow["demand_mbps"]) / net.cap[e]).max()
                     for e in (net.path_eids(p) for p in cands)]
        if min(projected) > 1.0:
            alt = self._residual_dijkstra(flow, load)
            if alt is not None and alt not in cands:
                cands.append(alt)
                self.fallbacks += 1

        phi = np.array([self._features(p, flow, load, forecast, ref_delay) for p in cands])
        q = phi @ self.w
        if train and self.rng.random() < self.eps:
            i = int(self.rng.integers(len(cands)))
        else:
            i = int(np.argmax(q))           # ties -> index 0 = plain Dijkstra path
        self.pending.append((flow["flow_id"], phi[i], flow["priority"]))
        return cands[i]

    def reward(self, latency_ms, loss, bottleneck_util, priority, imbalance=0.0):
        return (-self.IMPORTANCE[priority] * latency_ms / 10.0
                - 10.0 * loss
                - 2.0 * max(0.0, bottleneck_util - 0.8)
                - self.balance * imbalance)

    def observe(self, outcomes, link_cost_ms):
        for fid, phi, prio in self.pending:
            lat, loss, bott = outcomes[fid]
            r = self.reward(lat, loss, bott, prio, imbalance=phi[12])
            step = self.alpha / (1.0 + phi @ phi) if self.nlms else self.alpha
            self.w += step * (r - phi @ self.w) * phi
        self.pending = []
        self.tele.update(link_cost_ms)


# --------------------------------------------------------------------------
# Proposed (v3): Q-learning that tunes Dijkstra's link-cost function
# --------------------------------------------------------------------------

class QTunedDijkstra(Strategy):
    """
    Dijkstra computes every route; Q-learning decides HOW links are priced.

    Link cost (same form as LoadAwareDijkstra, with two learned knobs):
        base_delay + pf * ( s * (35 u^3 + 12 f^3) + tau * telemetry_excess )
    u = measured utilization, f = ML congestion forecast, pf = class factor.
    Action = a cost profile (s, tau): s in {0.5, 1, 2, 4} (how strongly to
    avoid load), tau in {0, 1} (whether to price measured excess delay/loss).
    Profile (1, 0) is exactly LoadAwareDijkstra; (1, 1) is TelemetryAwareDijkstra.

    Two tabular Q-learners, one per traffic group (real-time = voice/video,
    elastic = web/bulk), choose a profile at the start of every controller
    interval from a discrete network state:
        peak core utilization bucket (<0.5, 0.5-0.8, 0.8-1, >1)
        x unexplained-anomaly flag (a link shows > 3 ms excess cost while
          its measured utilization is < 0.8: silent degradation)
        x link-down flag
    Reward = minus the mean cost of the group's flows placed that interval
    (importance-weighted latency, loss, bottleneck overload), measured at the
    end of the interval. Standard one-step Q-learning (gamma = 0.5).
    A state-action never tried falls back to profile (1, 0), so the agent
    starts from the hand-tuned controller and only departs from it where
    experience says another profile is better.

    fixed=(a_rt, a_el) disables learning (used for the "best fixed profile"
    baseline, chosen on validation seeds).
    """
    name = "Hybrid QL-tuned Dijkstra (proposed)"
    learns = True
    PROFILES = [(s, tau) for tau in (0.0, 1.0) for s in (0.5, 1.0, 2.0, 4.0)]
    DEFAULT = 1                                   # (1.0, 0.0) = Load-aware Dijkstra
    PRIORITY_FACTOR = LoadAwareDijkstra.PRIORITY_FACTOR
    IMPORTANCE = HybridDijkstraQL.IMPORTANCE
    N_STATES = 16

    def __init__(self, net, alpha=0.1, gamma=0.5, eps=0.1, seed=0, fixed=None, name=None):
        super().__init__(net)
        self.alpha, self.gamma, self.eps, self.fixed = alpha, gamma, eps, fixed
        if name:
            self.name = name
        self.rng = np.random.default_rng(seed)
        A = len(self.PROFILES)
        self.Q = np.zeros((2, self.N_STATES, A))
        self.N = np.zeros((2, self.N_STATES, A), dtype=int)
        self.tele = LinkTelemetry(net)
        self.reset()

    def reset(self):
        self.tele.reset()
        self.new_interval = True
        self.state, self.act = None, [self.DEFAULT, self.DEFAULT]
        self.pending = ([], [])
        self.last = [None, None]                  # (state, action, reward) awaiting next state

    def _state(self, load):
        net = self.net
        live = net.core & net.up
        u = load / net.cap
        bucket = int(np.digitize(u[live].max(), [0.5, 0.8, 1.0]))
        anomaly = bool(((self.tele.excess > 3.0) & (u < 0.8) & live).any())
        down = not net.up.all()
        return bucket * 4 + int(anomaly) * 2 + int(down)

    def _greedy(self, g, s):
        tried = self.N[g, s] > 0
        if not tried.any():
            return self.DEFAULT
        q = np.where(tried, self.Q[g, s], -np.inf)
        return int(np.argmax(q))

    def _start_interval(self, load, train):
        s = self._state(load)
        for g in (0, 1):
            if self.fixed is not None:
                self.act[g] = self.fixed[g]
                continue
            if self.last[g] is not None:          # Q-learning update now that s' is known
                ps, pa, r = self.last[g]
                nxt = self.Q[g, s][self.N[g, s] > 0]
                target = r + self.gamma * (nxt.max() if len(nxt) else 0.0)
                self.Q[g, ps, pa] += self.alpha * (target - self.Q[g, ps, pa])
                self.last[g] = None
            if train and self.rng.random() < self.eps:
                self.act[g] = int(self.rng.integers(len(self.PROFILES)))
            else:
                self.act[g] = self._greedy(g, s)
        self.state = s
        self.new_interval = False

    def choose(self, flow, load, forecast, train=False):
        if self.new_interval:
            self._start_interval(load, train)
        net = self.net
        g = 0 if flow["priority"] <= 2 else 1
        s_mult, tau = self.PROFILES[self.act[g]]
        pf = self.PRIORITY_FACTOR[flow["priority"]]
        tele = self.tele.excess

        def weight(u, v, d):
            e = net.eid[(u, v)]
            if not net.up[e]:
                return None
            util_ratio = load[e] / net.cap[e]
            cong = (max(0.0, util_ratio) ** 3) * 35 + (max(0.0, forecast[e]) ** 3) * 12
            return d["base_delay_ms"] + (s_mult * cong + tau * max(0.0, tele[e])) * pf

        self.pending[g].append((flow["flow_id"], flow["priority"]))
        return tuple(nx.shortest_path(net.G, flow["src"], flow["dst"], weight=weight))

    def observe(self, outcomes, link_cost_ms):
        for g in (0, 1):
            if self.pending[g] and self.fixed is None and self.state is not None:
                costs = []
                for fid, prio in self.pending[g]:
                    lat, loss, bott = outcomes[fid]
                    costs.append(self.IMPORTANCE[prio] * lat / 10.0 + 10.0 * loss
                                 + 2.0 * max(0.0, bott - 0.8))
                a = self.act[g]
                self.N[g, self.state, a] += 1
                self.last[g] = (self.state, a, -float(np.mean(costs)))
        self.pending = ([], [])
        self.tele.update(link_cost_ms)
        self.new_interval = True
