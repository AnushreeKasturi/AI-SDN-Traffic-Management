"""Fast regression checks for the Python simulation (stdlib unittest, ~seconds).

    python -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from topology import TOPOLOGIES, build_topology, HOST_PAIRS  # noqa: E402
from traffic_gen import generate_flows  # noqa: E402
from ml_models import TrafficClassifier  # noqa: E402
from controller_sim import simulate  # noqa: E402
from netsim import Net, make_arrivals, run_episode, summarize  # noqa: E402
from routing import StaticDijkstra, LoadAwareDijkstra  # noqa: E402
from scenarios import Scenario, SCENARIOS  # noqa: E402


class TopologyTest(unittest.TestCase):
    def test_shapes(self):
        g = build_topology()
        kinds = [d["kind"] for _, d in g.nodes(data=True)]
        self.assertEqual((kinds.count("switch"), kinds.count("host"), g.number_of_edges()), (8, 6, 18))
        nsf = TOPOLOGIES["nsfnet14"][0]()
        self.assertEqual(sum(d["kind"] == "core" for *_, d in nsf.edges(data=True)), 21)


class ControllerSimTest(unittest.TestCase):
    def test_adaptive_never_drops_more_than_static(self):
        df, clf, _ = simulate(n_intervals=8, flows_per_interval=22, seed=7)
        self.assertEqual(len(df), 8)
        self.assertLessEqual(df["dropped_adaptive"].sum(), df["dropped_static"].sum())
        self.assertLessEqual(df["max_util_adaptive"].mean(), df["max_util_static"].mean())
        self.assertGreater(clf["accuracy"], 0.95)


class NetsimTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clf = TrafficClassifier()
        cls.clf.fit(generate_flows(400, HOST_PAIRS, seed=1))

    def run_strategy(self, cls_, scenario_kind="normal"):
        net = Net(build_topology())
        scen = Scenario(scenario_kind, net, HOST_PAIRS, seed=0)
        arrivals = make_arrivals(0, 20, 4, self.clf, scenario=scen)
        flows, intervals, *_, us = run_episode(cls_(net), net, arrivals,
                                               lambda hist, carried, t: carried[t] / 100.0,
                                               scenario=scen)
        return summarize(flows, intervals, us)

    def test_summary_is_sane_in_every_scenario(self):
        for kind in SCENARIOS:
            with self.subTest(kind):
                s = self.run_strategy(LoadAwareDijkstra, kind)
                self.assertGreater(s["mean_latency_ms"], 0)
                self.assertTrue(0 <= s["loss_pct"] <= 100)
                self.assertTrue(0 < s["jain_fairness"] <= 1)

    def test_load_aware_beats_static(self):
        static, adaptive = self.run_strategy(StaticDijkstra), self.run_strategy(LoadAwareDijkstra)
        self.assertLess(adaptive["mean_latency_ms"], static["mean_latency_ms"])


if __name__ == "__main__":
    unittest.main()
