"""
export_dashboard.py
Packs the round-3 routing study (../results/hybrid_v3/) into the data block
that the "Routing study" section of ../index.html reads, and writes it into
the page between the HYBRID-DATA markers.

    python export_dashboard.py

Run it after scenario_experiment.py (a full run or --rebuild).
"""

import json
import os
import re

import pandas as pd

from hybrid_experiment import ci95
from scenario_experiment import ORDER, REFERENCE, SCEN_LABEL, OUT_DIR
from routing import LoadAwareDijkstra, TelemetryAwareDijkstra, StaticDijkstra
from scenario_experiment import PATH_QL, QTUNED

ROOT = os.path.join(os.path.dirname(__file__), "..")
PAGE = os.path.join(ROOT, "index.html")
TOPOS = {"campus8": "Campus (8 switches)", "nsfnet14": "NSFNET (14 nodes)"}
METRICS = ["mean_latency_ms", "p95_latency_ms", "realtime_latency_ms", "loss_pct",
           "sla_violation_pct", "jain_fairness"]
WTL_METRICS = ["mean_latency_ms", "realtime_latency_ms", "sla_violation_pct", "jain_fairness"]
COMPARED = [LoadAwareDijkstra.name, TelemetryAwareDijkstra.name, PATH_QL, QTUNED]


def topo_block(topo):
    out = os.path.join(OUT_DIR, topo)
    raw = pd.read_csv(os.path.join(out, "raw_runs.csv"))
    tests = pd.read_csv(os.path.join(out, "significance_tests.csv"))

    # per scenario: average each seed over the scenario's loads, then mean and 95% CI over seeds
    scen = {}
    for kind in SCEN_LABEL:
        d = raw[raw["scenario"] == kind]
        per_seed = d.groupby(["strategy", "seed"])[METRICS].mean()
        scen[kind] = {}
        for name in ORDER:
            g = per_seed.loc[name]
            scen[kind][name] = {m: [round(float(g[m].mean()), 3), round(ci95(g[m]), 3)] for m in METRICS}

    normal = raw[raw["scenario"] == "normal"]
    loads = sorted(int(x) for x in normal["load"].unique())
    sweep = {name: [round(float(normal[(normal["strategy"] == name) & (normal["load"] == L)]["mean_latency_ms"].mean()), 2)
                    for L in loads] for name in ORDER}

    wtl = {}
    for base in COMPARED:
        wtl[base] = {}
        for m in WTL_METRICS:
            t = tests[(tests["baseline"] == base) & (tests["metric"] == m)]
            sig = t["p_value"] < 0.05
            w, l = int((sig & (t["abs_gain"] > 0)).sum()), int((sig & (t["abs_gain"] < 0)).sum())
            wtl[base][m] = [w, len(t) - w - l, l]

    # headline numbers, averaged over all scenario x load cells
    cell = raw.groupby(["strategy"])[["mean_latency_ms", "sla_violation_pct"]].mean()
    ref, la, st = cell.loc[REFERENCE], cell.loc[LoadAwareDijkstra.name], cell.loc[StaticDijkstra.name]
    headline = dict(
        latency_vs_static_pct=round(float((st.mean_latency_ms - ref.mean_latency_ms) / st.mean_latency_ms * 100), 1),
        sla_vs_loadaware_pct=round(float((la.sla_violation_pct - ref.sla_violation_pct) / la.sla_violation_pct * 100), 1),
        n_cells=int(tests.groupby(["scenario", "load"]).ngroups),
        n_seeds=int(raw["seed"].nunique()),
    )
    return dict(label=TOPOS[topo], scenarios=scen, loads=loads, sweep=sweep, wtl=wtl, headline=headline)


def main():
    data = dict(reference=REFERENCE, order=ORDER, compared=COMPARED,
                scenario_labels=SCEN_LABEL, topologies={t: topo_block(t) for t in TOPOS})
    with open(os.path.join(OUT_DIR, "dashboard.json"), "w") as f:
        json.dump(data, f, indent=1)

    with open(PAGE, encoding="utf-8") as f:
        html = f.read()
    block = "/* HYBRID-DATA */const HYBRID = " + json.dumps(data, separators=(",", ":")) + ";/* /HYBRID-DATA */"
    new, n = re.subn(r"/\* HYBRID-DATA \*/.*?/\* /HYBRID-DATA \*/", lambda _: block, html, flags=re.S)
    if n != 1:
        raise SystemExit("HYBRID-DATA markers not found in index.html")
    with open(PAGE, "w", encoding="utf-8") as f:
        f.write(new)
    for t, b in data["topologies"].items():
        print(t, b["headline"])


if __name__ == "__main__":
    main()
