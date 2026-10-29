"""
netsim.py
Flow-level network simulator used by the hybrid-routing study.

Differences from the quick simulation in controller_sim.py (kept as-is for
the original dashboard):
    - flows are long-lived: a flow occupies its path for
      ceil(duration / INTERVAL_S) controller intervals, so links carry
      load from earlier decisions (this is what makes forecasting and
      learning meaningful)
    - arrivals follow a Poisson process whose rate varies over time
      (diurnal-style sine wave), so load rises and falls
    - every link has a queueing model: delay grows as utilization
      approaches 1 (M/M/1-style u/(1-u) term) and any load above
      capacity is dropped proportionally (loss = 1 - 1/u)
    - each flow's latency / loss is evaluated at the END of the interval,
      after all of that interval's flows are placed, so a strategy is
      charged for congestion it causes for later flows too
    - an optional Scenario (scenarios.py) can fail / recover links, add a
      flash-crowd hotspot, or silently degrade a link. Failed links are
      visible to every controller (port-down event) and flows on them are
      re-routed by the strategy; silent degradation is NOT visible in the
      controller's capacity view, only in measured delay / loss.
"""

import math
import time

import networkx as nx
import numpy as np
import pandas as pd

from topology import HOST_PAIRS
from traffic_gen import generate_flows, CLASS_PRIORITY

INTERVAL_S = 30          # seconds per controller interval
QUEUE_MS = 0.5           # queueing-delay scale (ms) of the u/(1-u) term
UTIL_CAP = 0.99          # queueing term saturates here; above 1.0 we drop
LOSS_COST_MS = 100.0     # how Q-routing prices packet loss as delay
SLA_LATENCY_MS = {"voice": 15.0, "video": 30.0, "web": 60.0, "bulk": float("inf")}
SLA_LOSS = 0.01


class Net:
    def __init__(self, G):
        self.G = G
        self.edges = list(G.edges())
        self.eid = {}
        for i, (u, v) in enumerate(self.edges):
            self.eid[(u, v)] = i
            self.eid[(v, u)] = i
        self.cap = np.array([G[u][v]["capacity_mbps"] for u, v in self.edges], dtype=float)
        self.base = np.array([G[u][v]["base_delay_ms"] for u, v in self.edges], dtype=float)
        self.core = np.array([G[u][v]["kind"] == "core" for u, v in self.edges])
        self._pe = {}
        self._views = {}
        self.reset_conditions()

    def reset_conditions(self):
        E = len(self.edges)
        self.up = np.ones(E, dtype=bool)          # controller-visible link state
        self.true_cap_scale = np.ones(E)          # hidden (silent) capacity degradation
        self.extra_loss = np.zeros(E)             # hidden random packet loss

    def down_key(self):
        return tuple(np.flatnonzero(~self.up))

    def graph(self):
        """Topology without failed links (what the controller can route on)."""
        key = self.down_key()
        if not key:
            return self.G
        if key not in self._views:
            self._views[key] = nx.restricted_view(self.G, [], [self.edges[e] for e in key])
        return self._views[key]

    def path_ok(self, path):
        return bool(self.up[self.path_eids(path)].all())

    def path_eids(self, path):
        if path not in self._pe:
            self._pe[path] = np.array([self.eid[(u, v)] for u, v in zip(path[:-1], path[1:])])
        return self._pe[path]

    def link_state(self, load):
        """Returns (delay, loss, true utilization, measured utilization).
        Measured utilization is what the controller computes from port
        counters and nominal capacity; it misses silent degradation."""
        # a failed link carries nothing: anything still sent over it is lost
        cap = np.where(self.up, self.cap * self.true_cap_scale, 1e-9)
        u = load / cap
        uc = np.minimum(u, UTIL_CAP)
        delay = self.base + QUEUE_MS * uc / (1.0 - uc)
        loss = np.where(u > 1.0, 1.0 - 1.0 / np.maximum(u, 1e-9), 0.0)
        loss = 1.0 - (1.0 - loss) * (1.0 - self.extra_loss)
        return delay, loss, u, load / self.cap


def make_arrivals(seed, n_intervals, mean_new_flows, clf, host_pairs=HOST_PAIRS, scenario=None):
    """Same arrivals are replayed for every strategy, so only routing differs."""
    rng = np.random.default_rng(seed)
    phase = rng.uniform(0, 2 * np.pi)
    per_t = []
    for t in range(n_intervals):
        rate = mean_new_flows * (1.0 + 0.35 * math.sin(2 * np.pi * t / 20 + phase))
        if scenario is not None:
            rate *= scenario.rate_mult(t)
        n = int(rng.poisson(rate))
        if n == 0:
            per_t.append(pd.DataFrame())
            continue
        df = generate_flows(n, host_pairs, seed=int(rng.integers(1 << 31)))
        if scenario is not None:
            df = scenario.redirect(df, t, rng)
        df["flow_id"] = [f"{t}_{i}" for i in range(n)]
        df["pred_class"] = clf.predict(df)
        df["priority"] = df["pred_class"].map(CLASS_PRIORITY)
        df["life"] = np.maximum(1, np.ceil(df["duration_s"] / INTERVAL_S)).astype(int)
        per_t.append(df.sort_values("priority").reset_index(drop=True))
    return per_t


def exog_features(hist, carried, t):
    """Per-link features known at the start of interval t, before new flows arrive:
    the link's carried-over utilization from still-active flows, plus the
    network-wide mean utilization last interval and carried-over right now."""
    E = carried.shape[1]
    prev_mean = hist[t - 1].mean() if t > 0 else 0.0
    return np.column_stack([carried[t], np.full(E, prev_mean), np.full(E, carried[t].mean())])


def exog_series(hist, carried):
    """(T, E, n_exog) array of exog_features for every interval, for offline training."""
    return np.stack([exog_features(hist, carried, t) for t in range(len(hist))])


def make_forecaster(predictor, window):
    def forecast(hist, carried, t):
        if t < window:
            return carried[t] / 100.0
        X = np.column_stack([hist[t - window:t].T, exog_features(hist, carried, t)])
        return np.maximum(0.0, predictor.predict_many(X)) / 100.0
    return forecast


def run_episode(strategy, net, arrivals, forecast_fn, train=False, warmup=5, scenario=None):
    """Simulate one run. Returns (per-flow-interval records, per-interval records,
    util history, carried-over util history, decision times)."""
    n_intervals = len(arrivals)
    E = len(net.edges)
    hist = np.zeros((n_intervals, E))
    carried = np.zeros((n_intervals, E))
    active = []                     # [eids, demand, true_class, end_t, flow_id, flow record]
    flow_rows, interval_rows = [], []
    decision_us = []
    reroutes = 0
    net.reset_conditions()
    strategy.reset()

    def place(flow, load, forecast):
        t0 = time.perf_counter()
        path = strategy.choose(flow, load, forecast, train=train)
        decision_us.append((time.perf_counter() - t0) * 1e6)
        e = net.path_eids(path)
        load[e] += flow["demand_mbps"]
        return e

    for t in range(n_intervals):
        if scenario is not None:
            scenario.apply(net, t)
        active = [f for f in active if f[3] > t]
        load = np.zeros(E)
        for f in active:
            load[f[0]] += f[1]
        carried[t] = load / net.cap * 100.0
        forecast = forecast_fn(hist, carried, t)

        new_ids = set()
        # port-down: the controller re-routes every flow that crossed a failed link
        broken = [f for f in active if not net.up[f[0]].all()]
        for f in broken:
            load[f[0]] -= f[1]
        for f in broken:
            f[0] = place(f[5], load, forecast)
            new_ids.add(f[4])
            reroutes += 1

        for flow in arrivals[t].to_dict("records") if len(arrivals[t]) else []:
            e = place(flow, load, forecast)
            active.append([e, flow["demand_mbps"], flow["true_class"], t + flow["life"], flow["flow_id"], flow])
            new_ids.add(flow["flow_id"])

        delay, loss, util, measured = net.link_state(load)
        hist[t] = measured * 100.0

        outcomes = {}
        for e, demand, cls, _, fid, _ in active:
            lat = float(delay[e].sum())
            fl = float(1.0 - np.prod(1.0 - loss[e]))
            if fid in new_ids:
                outcomes[fid] = (lat, fl, float(util[e].max()))
            if t >= warmup:
                flow_rows.append((t, cls, demand, lat, fl,
                                  lat > SLA_LATENCY_MS[cls] or fl > SLA_LOSS))

        strategy.observe(outcomes, delay + LOSS_COST_MS * loss)

        if t >= warmup:
            core_u = util[net.core & net.up]
            interval_rows.append(dict(
                t=t,
                max_util=float(core_u.max()),
                jain=float(core_u.sum() ** 2 / (len(core_u) * (core_u ** 2).sum() + 1e-12)),
                offered_mbps=float(sum(f[1] for f in active)),
                reroutes=reroutes,
            ))

    net.reset_conditions()
    flows = pd.DataFrame(flow_rows, columns=["t", "cls", "demand", "latency_ms", "loss", "sla_violation"])
    return flows, pd.DataFrame(interval_rows), hist, carried, decision_us


def summarize(flows, intervals, decision_us):
    lat = flows["latency_ms"]
    sens = flows["cls"].isin(["voice", "video"])
    return dict(
        mean_latency_ms=float(lat.mean()),
        p95_latency_ms=float(lat.quantile(0.95)),
        realtime_latency_ms=float(flows.loc[sens, "latency_ms"].mean()),
        loss_pct=float(100 * (flows["demand"] * flows["loss"]).sum() / flows["demand"].sum()),
        sla_violation_pct=float(100 * flows["sla_violation"].mean()),
        max_util_pct=float(100 * intervals["max_util"].mean()),
        jain_fairness=float(intervals["jain"].mean()),
        decision_us=float(np.mean(decision_us)) if decision_us else 0.0,
    )
