"""
scenarios.py
Network events used to stress the routing strategies beyond smooth diurnal
load. All parameters below were fixed before any test run; the random parts
(which link fails, which host is the hotspot) are drawn from the scenario's
own seed, so every strategy faces exactly the same event.

    normal      no event (the original experiment)
    failure     two links on host-pair shortest paths go down: link A at
                t=12 (repaired at t=28), link B at t=20 (stays down).
                Visible to the controller as port-down events; flows on a
                failed link are re-routed immediately.
    hotspot     flash crowd: from t=15 to t=26 the arrival rate doubles and
                70% of new flows are sent to one randomly chosen host.
    degraded    silent ("gray") failure: from t=10 one link on a shortest
                path runs at 40% of its nominal capacity and drops 2% of
                packets. The controller's topology / capacity view does NOT
                change, so it can only be noticed through measured delay
                and loss.
"""

import networkx as nx
import numpy as np

SCENARIOS = ["normal", "failure", "hotspot", "degraded"]


def critical_links(net, host_pairs):
    """Core links on at least one host pair's static shortest path."""
    out = set()
    for s, d in host_pairs:
        p = nx.shortest_path(net.G, s, d, weight="base_delay_ms")
        for u, v in zip(p[:-1], p[1:]):
            e = net.eid[(u, v)]
            if net.core[e]:
                out.add(e)
    return sorted(out)


def _connected_without(net, host_pairs, eids):
    H = nx.restricted_view(net.G, [], [net.edges[e] for e in eids])
    return all(nx.has_path(H, s, d) for s, d in host_pairs)


class Scenario:
    def __init__(self, kind, net, host_pairs, seed):
        assert kind in SCENARIOS, kind
        self.kind = kind
        rng = np.random.default_rng(seed + 7_919)
        crit = critical_links(net, host_pairs)
        self.fail_a = self.fail_b = self.degraded = self.hot_host = None
        if kind == "failure":
            while True:
                a, b = rng.choice(crit, size=2, replace=False)
                if _connected_without(net, host_pairs, [a, b]):
                    self.fail_a, self.fail_b = int(a), int(b)
                    break
        elif kind == "degraded":
            self.degraded = int(rng.choice(crit))
        elif kind == "hotspot":
            hosts = sorted({h for p in host_pairs for h in p})
            self.hosts = hosts
            self.hot_host = hosts[rng.integers(len(hosts))]

    # ---- traffic side (used by make_arrivals) ----
    def rate_mult(self, t):
        return 2.0 if self.kind == "hotspot" and 15 <= t < 27 else 1.0

    def redirect(self, df, t, rng):
        if self.kind != "hotspot" or not 15 <= t < 27:
            return df
        df = df.copy()
        others = [h for h in self.hosts if h != self.hot_host]
        for i in df.index:
            if rng.random() < 0.7:
                df.at[i, "dst"] = self.hot_host
                df.at[i, "src"] = others[rng.integers(len(others))]
        return df

    # ---- network side (called by run_episode at the start of each interval) ----
    def apply(self, net, t):
        if self.kind == "failure":
            net.up[:] = True
            if 12 <= t < 28:
                net.up[self.fail_a] = False
            if t >= 20:
                net.up[self.fail_b] = False
        elif self.kind == "degraded" and t >= 10:
            net.true_cap_scale[self.degraded] = 0.4
            net.extra_loss[self.degraded] = 0.02

    def describe(self, net):
        if self.kind == "failure":
            return f"fail {net.edges[self.fail_a]}@12-28, {net.edges[self.fail_b]}@20+"
        if self.kind == "degraded":
            return f"degrade {net.edges[self.degraded]}@10+"
        if self.kind == "hotspot":
            return f"hotspot {self.hot_host}@15-26"
        return "normal"
