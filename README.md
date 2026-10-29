# AI-Driven Adaptive Network Traffic Management using SDN and Machine Learning

A computer-networks mini project that simulates a **Software-Defined Network (SDN)
controller** which uses **machine learning** to classify traffic and predict
congestion, then reroutes flows adaptively — and compares it against a
traditional **static, non-adaptive** routing scheme on the same topology and
the same traffic.

Open **`index.html`** in any browser — it's a self-contained dashboard (no
server needed) that presents the whole project to your teacher: architecture,
topology, ML model performance, and the static-vs-adaptive results, all
generated from the actual simulation run in `src/`.

---

## 1. Problem statement

Traditional networks (OSPF/static routing) pick a path based on fixed link
costs (like hop count or delay) and **never change it based on current
traffic**. If a "shortest" path gets congested, every new flow still piles
onto it — causing high latency and packet loss — while a different, slightly
longer path sits idle.

**Idea:** give the network's controller a global view (this is exactly what
SDN provides) plus a machine-learning brain that can (a) tell what *kind* of
traffic a flow is, and (b) forecast which links are *about to* get congested.
Use both to pick better paths in real time.

## 2. Architecture

```
 Flow stats  ─▶ [1] Traffic Classifier (Random Forest)
 (from switches)      classifies: voice / video / web / bulk
                              │
                              ▼
 Link history ─▶ [2] Congestion Predictor (RF Regressor)
                      forecasts next-interval utilization per link
                              │
                              ▼
                 [3] SDN Controller (Dijkstra, re-weighted)
                      path cost = base delay
                               + (current load)^3  x priority factor
                               + (forecast load)^3 x priority factor
                              │
                              ▼
                 [4] Flow rules pushed to switches (simulated)
```

This mirrors a real deployment: a **Ryu** or **ONOS** controller app would
poll OpenFlow switch statistics, run the same two ML models, and call
`nx.shortest_path` (or an equivalent path computation) with adaptive weights
before pushing flow-mod messages to switches. The topology in `topology.py`
is written the same way you'd declare it in **Mininet** (`addLink(s1, s2,
bw=100, delay='2ms')`), so this simulation can be ported to a real Mininet +
Ryu setup with minimal changes if you want to extend the project.

## 3. What's simulated

- **Topology** (`src/topology.py`): 8 OpenFlow switches in a partial mesh (so
  redundant paths genuinely exist between most switch pairs) + 6 hosts, each
  link with its own capacity (Mbps) and propagation delay.
- **Traffic generator** (`src/traffic_gen.py`): synthetic flows from 4
  application classes (voice, video, web, bulk), each with realistic packet
  size / inter-arrival-time / duration / demand distributions — similar in
  spirit to real traffic-classification datasets.
- **ML models** (`src/ml_models.py`):
  - `TrafficClassifier` — Random Forest, trained on 1500 synthetic flows,
    ~99–100% held-out accuracy (the classes are statistically well
    separated, similar to real QoS classification papers).
  - `CongestionPredictor` — Random Forest Regressor on lag features,
    forecasts a link's utilization one interval ahead.
- **Controller simulation** (`src/controller_sim.py`): runs 24 controller
  intervals. In every interval it generates flows, classifies them, and
  routes them **twice** — once with static shortest-path routing, once with
  the AI-adaptive controller — so both strategies see *identical* traffic and
  only the routing decision differs.
- **Experiment driver** (`src/run_experiment.py`): runs everything, saves
  `results/results.json` (all the numbers behind the dashboard) and
  `results/topology.png` (the topology diagram).

## 4. How to run it yourself

```bash
pip install -r requirements.txt
cd src
python3 run_experiment.py
```

This regenerates `results/results.json` and `results/topology.png`. To
rebuild `index.html` from those results (optional — a copy is already
included), see the inline comments in `run_experiment.py`; the dashboard
simply embeds that JSON and image.

## 5. Key results (from the included run)

| Metric | Static routing | AI-Adaptive routing |
|---|---|---|
| Traffic classification accuracy | — | ~99.7% |
| Average flow latency | baseline | ~15% lower |
| Peak link utilization | baseline | ~39% lower |
| Congested / dropped flows | 23 | 0 |

The adaptive controller trades a small amount of routing simplicity for a
large reduction in congestion and drops — because it can see current load
*and* forecast future load, while static routing is blind to both.

## 7. Project structure

```
├── index.html               ← open this to present the project
├── requirements.txt
├── src/
│   ├── topology.py           network topology (Mininet-style)
│   ├── traffic_gen.py        synthetic flow/traffic generator
│   ├── ml_models.py          traffic classifier + congestion predictor
│   ├── controller_sim.py     static vs adaptive routing simulation
│   ├── run_experiment.py     runs everything, exports results
│   ├── template.html         dashboard template (results get injected here)
│   │                         ── hybrid routing study (section 9) ──
│   ├── netsim.py             flow-level simulator (queueing delay, loss, failures)
│   ├── routing.py            all routing strategies (baselines + hybrids)
│   ├── scenarios.py          link failure / hotspot / silent degradation events
│   ├── hybrid_experiment.py  round 1 driver (campus topology, normal traffic)
│   └── scenario_experiment.py rounds 2–3 driver (scenarios, NSFNET, validation)
├── results/
│   ├── results.json          all metrics behind the dashboard
│   ├── topology.png          rendered topology diagram
│   ├── hybrid/               round 1 results
│   ├── hybrid_v2/            round 2 results
│   └── hybrid_v3/            round 3 results (campus8/, nsfnet14/, validation/)
└── mininet_sdn/               ← a REAL Mininet + OVS + OpenFlow deployment
    ├── README_MININET.md      setup + how to run it on your own machine
    ├── network_topo.py        builds the actual Mininet topology
    ├── controller_static.py   real baseline SDN controller (non-adaptive)
    ├── controller_adaptive.py real AI-driven SDN controller
    ├── run_demo.sh            one-command demo (static or adaptive)
    └── sample_run_logs/       real captured output, in case you can't run it live
```

## 8. Two ways to explore this project

This project ships in two layers, and it's worth being clear about which is
which when you present it:

- **`src/` — a fast, large-scale simulation.** Pure Python (networkx +
  scikit-learn), no real network stack. Lets you sweep 24 controller
  intervals and dozens of flows in seconds, which is what the dashboard's
  quantitative comparison (`index.html`) is built from.
- **`mininet_sdn/` — a real SDN deployment.** Actual Mininet switches, real
  Open vSwitch, a real OpenFlow controller (`os-ken`) making live routing
  decisions from real port/flow statistics. Slower to run and smaller in
  scope (a handful of flows, not 24 intervals), but it's the real thing —
  see `mininet_sdn/README_MININET.md` for a captured example where the
  AI-driven controller detects real congestion on a live link and reroutes
  a new flow around it while the baseline controller doesn't.

Presenting both makes the strongest case: the simulation shows the idea
holds up quantitatively at scale, and the Mininet deployment proves the
same logic runs as a real, working SDN controller.

## 9. Hybrid routing study (Dijkstra + machine learning)

The original controller above uses a single hand-made Dijkstra cost
function. To go beyond plain Dijkstra, a second, more rigorous study compares
several hybrid routing algorithms against strong baselines. It lives in
`src/netsim.py`, `src/routing.py`, `src/scenarios.py` and the two experiment
drivers; the original `src/controller_sim.py` results and `index.html` are
unchanged.

### Setup

- **Simulator** (`netsim.py`): long-lived flows with Poisson, diurnal
  arrivals; M/M/1-style queueing delay and overload loss on every link.
- **Topologies**: the 8-switch campus network (`campus8`) and the 14-node
  NSFNET backbone (`nsfnet14`), to check that results generalise.
- **Scenarios** (`scenarios.py`): normal traffic at 5 load levels, plus
  link failures (port-down + rerouting), a flash-crowd hotspot, and a
  *silent* link degradation the controller cannot see in its capacity view.
- **Strategies compared** (`routing.py`):

| Strategy | What it does |
|---|---|
| Static Dijkstra | fixed shortest path (OSPF-like) |
| ECMP | random choice among equal-cost shortest paths |
| Load-aware Dijkstra | the original controller: cost grows with current + forecast load |
| Telemetry-aware Dijkstra | Load-aware + measured delay/loss on each link |
| Best fixed-profile Dijkstra | class-aware, telemetry-aware cost profile (one for voice/video, one for web/bulk), chosen on validation data |
| Q-Routing | reinforcement learning only (ablation) |
| Hybrid path-selection QL | k-shortest Dijkstra candidates, Q-learning picks one (ablation) |
| Hybrid QL-tuned Dijkstra | Q-learning picks Dijkstra's cost profile per traffic group and network state |

- **Fair evaluation**: every strategy sees identical arrivals and the same ML
  predictions. Training, validation and test runs use disjoint random seeds;
  every setting was chosen on validation seeds only. Results are averaged
  over 10 test seeds, with paired Wilcoxon tests (p < 0.05) and 95% CIs.

### Results in brief

- All Dijkstra-based adaptive methods beat Static Dijkstra, ECMP and
  Q-Routing by a wide margin (for example, on campus8 under normal load,
  mean latency 8.7–9.1 ms vs 32.7 ms for Static Dijkstra and 50.4 ms for
  Q-Routing). Pure RL routing performs worst.
- **Best fixed-profile Dijkstra** is the strongest strategy overall. Against
  Load-aware Dijkstra it never loses significantly on latency, SLA or
  fairness; it cuts SLA violations by about 13% (campus8) and 19% (NSFNET)
  and improves link-load fairness in 9 of 11 test cells on both topologies,
  even though its profile was chosen only on campus8 validation data.
- The telemetry term is what helps under silent degradation (campus8 mean
  latency 12.8 ms → 9.8 ms for Telemetry-aware vs Load-aware).
- **Honest finding:** the Q-learning hybrids mostly *tie* Load-aware Dijkstra
  and do not beat the best fixed profile; on NSFNET the QL-tuned Dijkstra is
  significantly slower than Load-aware Dijkstra in 7 of 11 cells. Likely
  causes: each traffic group is rewarded only for its own flows, and the
  tabular Q estimates are sparse and noisy.

Full tables, significance tests and figures are in
`results/hybrid_v3/<topology>/results_tables.md`; earlier rounds are in
`results/hybrid/` and `results/hybrid_v2/`.

### Reproducing

```bash
cd src
python scenario_experiment.py --quick          # smoke test, a few minutes
python scenario_experiment.py --validate       # choose the fixed profile (validation seeds)
python scenario_experiment.py --topo campus8   # full test run (long)
python scenario_experiment.py --topo nsfnet14
```

The full runs take a while and use a lot of memory; run them in a normal
terminal rather than in the background.
