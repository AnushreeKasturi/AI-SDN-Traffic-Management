# Flowstate: AI-driven adaptive routing for SDN

[![CI](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/actions/workflows/ci.yml/badge.svg)](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/actions/workflows/ci.yml)
[![Dashboard](https://img.shields.io/website?url=https%3A%2F%2Fanushreekasturi.github.io%2FAI-SDN-Traffic-Management%2F&label=Dashboard&logo=github)](https://anushreekasturi.github.io/AI-SDN-Traffic-Management/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](requirements.txt)
[![OpenFlow 1.3](https://img.shields.io/badge/OpenFlow-1.3-008080)](mininet_sdn/README_MININET.md)

Flowstate is a software-defined networking (SDN) controller that uses machine
learning to reroute traffic before links congest. It classifies each flow
(voice, video, web, bulk), forecasts per-link utilization one interval ahead,
and runs Dijkstra on a link cost built from current load, forecast load and
traffic priority.

The repository has three parts:

| Layer | What it is | Where |
|---|---|---|
| **Simulation** | Fast flow-level simulator plus an 8-strategy routing study over 2 topologies, 4 scenarios and 10 test seeds | [`src/`](src/) |
| **Real deployment** | The same controller logic on Mininet, Open vSwitch and OpenFlow 1.3 (`os-ken`) | [`mininet_sdn/`](mininet_sdn/) |
| **Dashboard** | One self-contained web page: results explorer plus an in-browser routing simulator | [`index.html`](index.html), [live](https://anushreekasturi.github.io/AI-SDN-Traffic-Management/) |

<p align="center">
  <a href="https://anushreekasturi.github.io/AI-SDN-Traffic-Management/"><b>Open the live dashboard →</b></a>
</p>

---

## Results at a glance

**Original experiment** (campus topology, 24 intervals, identical traffic for
both controllers; source: [`results/results.json`](results/results.json)):

| Metric | Static routing | AI-adaptive routing |
|---|---|---|
| Traffic classification accuracy (held-out) | n/a | 99.7% |
| Average flow latency | baseline | 15.2% lower |
| Peak link utilization | baseline | 38.8% lower |
| Congested flows | 23 | 0 |

**Routing study** (8 strategies; source:
[`results/hybrid_v3/`](results/hybrid_v3/)):

- All Dijkstra-based adaptive strategies beat Static Dijkstra, ECMP and pure
  RL routing by a wide margin. On campus8 under normal load, mean latency is
  8.7 to 9.2 ms for them, against 32.7 ms for Static Dijkstra.
- **Best fixed-profile Dijkstra** is the strongest strategy. Against
  Load-aware and Telemetry-aware Dijkstra it is never significantly worse in
  any test cell, on any reported metric, on either network.
- **Negative result:** the Q-learning hybrids did not add anything on top
  of a well-chosen cost profile. Details are in [the routing study](#routing-study).

The classifier's accuracy is high because the synthetic traffic classes are
statistically well separated. Real traffic would be harder to classify.

Reruns with newer library versions give slightly different numbers. With
Python 3.12, scikit-learn 1.9 and NumPy 2.5, `make experiment` gives 16.6%
lower latency, 36.1% lower peak utilization, and 24 → 0 congested flows. The
direction of every result is the same.

## Quick start

```bash
git clone https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management.git
cd AI-SDN-Traffic-Management
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

make experiment     # original experiment -> results/results.json, results/topology.png
make test           # Python + dashboard regression tests
make serve          # dashboard at http://localhost:8000
```

To view the dashboard without any setup, open `index.html` in a browser. Run
`make help` to list every target. Without `make`, each target is a single
command in the [`Makefile`](Makefile).

## How it works

```
 Flow stats  ─▶ [1] Traffic classifier (Random Forest)
 (switches)         voice / video / web / bulk  →  QoS priority
                              │
 Link history ─▶ [2] Congestion predictor (Random Forest regressor)
                    next-interval utilization per link
                              │
                              ▼
                [3] Path computation (Dijkstra, re-weighted per flow)
                    cost = base delay
                         + priority × (35·current_util³ + 12·forecast_util³)
                              │
                              ▼
                [4] Per-hop OpenFlow flow-mods pushed to switches
```

The static baseline routes on base delay alone, so it never reacts to load.
The adaptive controller recomputes the path for each new flow, using live
utilization plus the ML forecast, and gives voice and video traffic a more
conservative cost.

## Routing study

The original controller uses one hand-made cost function. The routing study
tests which routing design works best: eight strategies, two networks, four
scenarios. It is also shown in the dashboard's "Routing study" section, where
you can switch network, scenario and metric.

| Strategy | What it does |
|---|---|
| Static Dijkstra | Fixed shortest path (OSPF-like) |
| ECMP | Random choice among equal-cost shortest paths |
| Load-aware Dijkstra | The original controller: cost grows with current + forecast load |
| Telemetry-aware Dijkstra | Load-aware + measured delay/loss on each link |
| **Best fixed-profile Dijkstra** | **Main method:** class-aware, telemetry-aware cost profile (one for voice/video, one for web/bulk), chosen on validation data |
| Q-Routing | Reinforcement learning only (ablation) |
| Hybrid path-selection QL | k-shortest Dijkstra candidates, Q-learning picks one (ablation) |
| Hybrid QL-tuned Dijkstra | Q-learning picks Dijkstra's cost profile per traffic group and network state (ablation) |

**Setup**

- **Simulator** ([`netsim.py`](src/netsim.py)): long-lived flows with
  Poisson, diurnal arrivals; M/M/1-style queueing delay and overload loss on
  every link.
- **Topologies**: the 8-switch campus network (`campus8`) and the 14-node
  NSFNET backbone (`nsfnet14`).
- **Scenarios** ([`scenarios.py`](src/scenarios.py)): normal traffic at 5
  load levels, link failures, a flash-crowd hotspot, and a *silent* link
  degradation that the controller's capacity view cannot see.
- **Fair evaluation**: every strategy sees identical arrivals and the same
  ML predictions. Training, validation and test runs use disjoint seeds, and
  every setting was chosen on validation seeds only. Results are averaged
  over 10 test seeds, with paired Wilcoxon tests (p < 0.05) and 95% CIs
  across 11 scenario × load cells.

**Findings**

- Against Load-aware Dijkstra, Best fixed-profile Dijkstra gives
  significantly lower voice/video latency in 6/11 cells (campus8) and 10/11
  (NSFNET), and fairer link load in 9/11 on both. Its profile was chosen
  only on campus8 validation data, so the NSFNET results are an
  out-of-sample check.
- SLA violations against Load-aware Dijkstra fall by 13% (campus8) and 19%
  (NSFNET) on average per test cell. On campus8 the gain comes almost
  entirely from the silent-degradation scenario; the median cell improves by
  only 1.5%.
- The telemetry term is what helps under silent degradation: campus8 mean
  latency drops from 12.8 ms (Load-aware) to 9.8 ms (Telemetry-aware).
- The two Q-learning hybrids mostly *tie* Load-aware Dijkstra and never
  significantly beat the fixed profile on mean or voice/video latency. On
  NSFNET, QL-tuned Dijkstra is significantly slower than Load-aware
  Dijkstra in 7 of 11 cells. Likely causes: each traffic group is rewarded
  only for its own flows, and the tabular Q estimates are sparse and noisy.

Full tables, significance tests and figures are in
`results/hybrid_v3/<topology>/results_tables.md`. Earlier rounds are kept in
`results/hybrid/` and `results/hybrid_v2/`. They use the original "proposed"
labels, and the v2 NSFNET run was stopped early and superseded by v3.

**Reproducing**

```bash
cd src
python scenario_experiment.py --quick          # smoke test, a few minutes
python scenario_experiment.py --validate       # choose the fixed profile (validation seeds)
python scenario_experiment.py --topo campus8   # full test run (long, memory-heavy)
python scenario_experiment.py --topo nsfnet14
python scenario_experiment.py --rebuild        # tables/tests/figures from saved runs (fast)
python export_dashboard.py                     # write the study into index.html
```

## Real deployment (Mininet + Open vSwitch)

[`mininet_sdn/`](mininet_sdn/) runs the same idea as real OpenFlow 1.3
controllers on Linux. The demo saturates the `s2–s4` link with a 60 Mbps
bulk transfer, then opens a voice flow from `h2` to `h5`:

```
[static]   10.0.0.2 -> 10.0.0.5 routed via switches [2, 4, 7]               # through the busy link
[adaptive] 10.0.0.2:50331 -> 10.0.0.5:5060 class=voice priority=1 path=[2, 5, 7]   # around it
```

The setup steps, the full captured logs and the known limitations
(hardcoded topology, port-based classification at flow setup) are in
[`mininet_sdn/README_MININET.md`](mininet_sdn/README_MININET.md).

## Repository layout

```
├── index.html                 dashboard (self-contained; open directly or via GitHub Pages)
├── Makefile                   common tasks: experiment, test, serve, export
├── requirements.txt           Python dependencies for src/
├── src/
│   ├── topology.py            campus8 + NSFNET topologies (Mininet-style)
│   ├── traffic_gen.py         synthetic flow generator (4 traffic classes)
│   ├── ml_models.py           traffic classifier + congestion predictor
│   ├── controller_sim.py      original static vs adaptive simulation
│   ├── run_experiment.py      runs it, writes results/results.json
│   ├── netsim.py              flow-level simulator (queueing, loss, failures)
│   ├── routing.py             all eight routing strategies
│   ├── scenarios.py           failure / hotspot / silent-degradation events
│   ├── hybrid_experiment.py   study round 1
│   ├── scenario_experiment.py study rounds 2–3 (scenarios, NSFNET, validation)
│   ├── export_dashboard.py    writes round-3 results into index.html
│   └── template.html          original dashboard template (pre-redesign)
├── results/                   committed outputs behind every number above
├── mininet_sdn/               real Mininet + OVS + os-ken deployment
└── tests/
    ├── test_simulation.py     Python regression tests (unittest)
    └── dashboard.test.mjs     dashboard data + engine tests (node --test)
```

## Testing

```bash
make test
# or separately:
python -m unittest discover -s tests -v
node --test tests/
```

The dashboard tests use no dependencies. They check that the data embedded
in `index.html` matches the committed result files, that charts keep their
size at high DPI, and that the browser simulator still reproduces its
reference runs. CI runs both suites on every push and pull request.

## Limitations

- The study traffic is synthetic. Classifier accuracy and the latency gains
  have not been measured on production traces.
- The Mininet controllers use a hardcoded topology (no LLDP discovery) and
  classify flows by port at setup time. The ML classifier runs on live flow
  stats but does not yet trigger mid-flow migration.
- The simulator is flow-level (M/M/1-style queueing), not packet-level.

## Roadmap

These items are planned and not built yet:

- [ ] LLDP topology discovery in the `os-ken` controllers
- [ ] Use the live classifier output to migrate established flows
- [ ] Ship Best fixed-profile Dijkstra in the real controller (it currently runs Load-aware)
- [ ] Evaluate on public traffic traces instead of synthetic flows
- [ ] Controller REST API plus a live telemetry view in the dashboard
- [ ] Container image for the Mininet demo

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
