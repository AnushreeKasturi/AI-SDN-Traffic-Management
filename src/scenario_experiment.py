"""
scenario_experiment.py
Third round of the hybrid-routing study (results in ../results/hybrid_v3/;
the v2 campus run is kept in ../results/hybrid_v2/).

v3: the proposed method is QTunedDijkstra (routing.py) - Q-learning chooses
Dijkstra's link-cost profile per traffic group and network state. The v2
path-selection hybrid is kept as an ablation, and a "best fixed profile"
Dijkstra (the best single profile pair, chosen on validation seeds) checks
whether learning beats simply tuning the constants.

What it adds over hybrid_experiment.py (v1, results kept in results/hybrid/):
    - a second, larger topology (NSFNET, 14 nodes / 21 core links)
    - network events: link failures, a flash-crowd hotspot, and a silent
      link degradation (scenarios.py)
    - Hybrid v2 = Hybrid v1 + load-balance reward term + link telemetry
      feature; v1 is kept as an ablation
    - Telemetry-aware Dijkstra, a control baseline that gets the same
      telemetry as Hybrid v2 but no learning, so a gain can be attributed
      to learning rather than to extra measurements

Protocol (same as v1): predictor and agents are trained on TRAINING seeds
(which include every scenario type, with different random events), the
hyperparameters and the fixed-profile baseline are chosen on separate VALIDATION seeds (--validate),
and all strategies are evaluated on the same TEST seeds.

    python scenario_experiment.py --validate           # best fixed profile + sanity check (validation seeds)
    python scenario_experiment.py --topo campus8       # full test run, one topology
    python scenario_experiment.py --topo nsfnet14
    python scenario_experiment.py --quick              # smoke test
"""

import argparse
import copy
import json
import os
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from topology import TOPOLOGIES, HOST_PAIRS
from traffic_gen import generate_flows
from ml_models import TrafficClassifier, CongestionPredictor
from netsim import Net, make_arrivals, make_forecaster, run_episode, summarize, exog_series
from routing import (StaticDijkstra, ECMP, LoadAwareDijkstra, TelemetryAwareDijkstra,
                     QRouting, HybridDijkstraQL, QTunedDijkstra)
from scenarios import Scenario, SCENARIOS
from hybrid_experiment import METRICS, ci95, wilcoxon_p, MIN_BASE_FOR_PCT

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "results", "hybrid_v3")

LOAD_LEVELS = [2, 3, 4, 6, 8]        # same calibration (Static Dijkstra) holds on both topologies
EVENT_LOADS = [3, 6]                 # moderate and heavy load for the event scenarios
N_INTERVALS = 40
TRAIN_SEED0, PRED_TEST_SEED0, VAL_SEED0, TEST_SEED0 = 10_000, 20_000, 30_000, 0

# Chosen on VALIDATION seeds (campus8, 4 seeds x 4 scenarios x 2 loads) by the rule fixed in
# advance "lowest mean latency over all scenarios"; grid alpha {0.1, 0.5} x balance {0.25, 0.5, 1.0},
# NLMS update. Record: results/hybrid_v2/validation/validation_nlms.csv
ALPHA = 0.1
BALANCE = 0.5
BALANCE_GRID = [0.0, 0.25, 0.5, 1.0, 2.0]

PROPOSED = QTunedDijkstra.name
PATH_QL = "Hybrid path-selection QL (v2, ablation)"
FIXED = "Best fixed-profile Dijkstra"
ORDER = [StaticDijkstra.name, ECMP.name, LoadAwareDijkstra.name, TelemetryAwareDijkstra.name,
         FIXED, QRouting.name, PATH_QL, PROPOSED]
COLORS = {
    PROPOSED: "#2a78d6",
    StaticDijkstra.name: "#eb6834",
    ECMP.name: "#1baf7a",
    LoadAwareDijkstra.name: "#eda100",
    QRouting.name: "#e87ba4",
    TelemetryAwareDijkstra.name: "#8a63d2",
    PATH_QL: "#7fa9dc",
    FIXED: "#5a5955",
}
MARKERS = {PROPOSED: "o", StaticDijkstra.name: "s", ECMP.name: "^", LoadAwareDijkstra.name: "D",
           QRouting.name: "v", TelemetryAwareDijkstra.name: "P", PATH_QL: "X", FIXED: "*"}
SCEN_LABEL = {"normal": "Normal", "failure": "Link failures", "hotspot": "Flash-crowd hotspot",
              "degraded": "Silent link degradation"}


def fresh_copy(agent, net):
    """Copy a trained agent for one test run, sharing the live Net object so
    it sees the same link failures as everything else."""
    return copy.deepcopy(agent, {id(net): net})


def make_path_ql(net):
    """The v2 hybrid (k-shortest candidates + linear QL path choice), now an ablation."""
    return HybridDijkstraQL(net, seed=1, alpha=ALPHA, nlms=True, balance=BALANCE, telemetry=True, name=PATH_QL)


FIXED_FILE = os.path.join(OUT_DIR, "validation", "best_fixed_profile.json")


def load_fixed():
    with open(FIXED_FILE) as f:
        return tuple(json.load(f)["actions"])


# --------------------------------------------------------------------------
# training
# --------------------------------------------------------------------------

def pretrain_predictor(net, clf, pairs, n_seeds):
    """Same residual random-forest predictor as v1, trained on normal-traffic traces."""
    zero = lambda h, c, t: np.zeros(len(net.edges))

    def traces(seed0):
        series, exogs = [], []
        for i in range(n_seeds):
            arr = make_arrivals(seed0 + i, N_INTERVALS, LOAD_LEVELS[i % len(LOAD_LEVELS)], clf, host_pairs=pairs)
            for S in (StaticDijkstra, ECMP):
                _, _, hist, carried, _ = run_episode(S(net), net, arr, zero)
                ex = exog_series(hist, carried)
                series.extend(hist.T)
                exogs.extend(ex[:, e, :] for e in range(hist.shape[1]))
        return series, exogs

    tr_s, tr_x = traces(TRAIN_SEED0)
    te_s, te_x = traces(PRED_TEST_SEED0)
    w = 4
    pred = CongestionPredictor(window=w).fit_pooled(tr_s, tr_x, residual_col=w)
    X, y = zip(*(pred._make_lag_features(s, x) for s, x in zip(te_s, te_x)))
    X, y = np.vstack(X), np.concatenate(y)
    p = pred.predict_many(X)
    return pred, dict(r2=float(1 - ((p - y) ** 2).sum() / ((y - y.mean()) ** 2).sum()),
                      mae=float(np.mean(np.abs(p - y))))


def train_agents(agents, net, clf, pairs, forecast_fn, n_episodes, log=True):
    """Training episodes cycle through every scenario type and load level."""
    curve = {a.name: [] for a in agents}
    for ep in range(n_episodes):
        eps = max(0.02, 0.3 * (1 - ep / (0.7 * n_episodes)))
        kind = SCENARIOS[ep % len(SCENARIOS)]
        level = LOAD_LEVELS[(ep // len(SCENARIOS)) % len(LOAD_LEVELS)]
        seed = TRAIN_SEED0 + 500 + ep
        scen = Scenario(kind, net, pairs, seed)
        arr = make_arrivals(seed, N_INTERVALS, level, clf, host_pairs=pairs, scenario=scen)
        for a in agents:
            a.eps = eps
            flows, _, _, _, _ = run_episode(a, net, arr, forecast_fn, train=True, scenario=scen)
            curve[a.name].append(float(flows["latency_ms"].mean()))
        if log and (ep + 1) % 10 == 0:
            print(f"  training episode {ep + 1}/{n_episodes}  eps={eps:.2f}  "
                  + "  ".join(f"{k}: {v[-1]:.1f}ms" for k, v in curve.items()), flush=True)
    return curve


def setup(topo, n_seeds):
    build, pairs = TOPOLOGIES[topo]
    net = Net(build())
    clf = TrafficClassifier()
    clf_metrics = clf.fit(generate_flows(1500, HOST_PAIRS, seed=1))
    predictor, pred_metrics = pretrain_predictor(net, clf, pairs, n_seeds=max(2, n_seeds))
    forecast_fn = make_forecaster(predictor, predictor.window)
    return net, pairs, clf, clf_metrics, forecast_fn, pred_metrics


# --------------------------------------------------------------------------
# validation (campus8, validation seeds only)
# --------------------------------------------------------------------------

def validate(args):
    """1) Pick the best fixed (real-time, elastic) cost-profile pair by mean
    latency over all scenarios -> the FIXED baseline. 2) Sanity-check the
    trained QL-tuned Dijkstra against the baselines (reported, not tuned)."""
    topo = "campus8"
    out = os.path.join(OUT_DIR, "validation")
    os.makedirs(out, exist_ok=True)
    net, pairs, clf, _, forecast_fn, _ = setup(topo, args.seeds)
    cells = []
    for kind in SCENARIOS:
        for level in EVENT_LOADS:
            for sd in range(args.val_seeds):
                seed = VAL_SEED0 + sd
                scen = Scenario(kind, net, pairs, seed)
                cells.append((kind, level, sd, scen,
                              make_arrivals(seed, N_INTERVALS, level, clf, host_pairs=pairs, scenario=scen)))

    # coordinate search (8 + 8 profile pairs instead of all 64): real-time
    # group first with elastic at the default profile, then elastic
    A = len(QTunedDijkstra.PROFILES)
    rows = []

    def score(pair):
        hit = [r for r in rows if (r["a_rt"], r["a_el"]) == pair]
        if not hit:
            for kind, level, sd, scen, arr in cells:
                st = QTunedDijkstra(net, fixed=pair)
                f, iv, _, _, d = run_episode(st, net, arr, forecast_fn, scenario=scen)
                rows.append(dict(a_rt=pair[0], a_el=pair[1], scenario=kind, load=level, seed=sd,
                                 **summarize(f, iv, d)))
            hit = [r for r in rows if (r["a_rt"], r["a_el"]) == pair]
        return float(np.mean([r["mean_latency_ms"] for r in hit]))

    D = QTunedDijkstra.DEFAULT
    a_rt = min(range(A), key=lambda a: score((a, D)))
    print(f"  fixed profiles: real-time -> {QTunedDijkstra.PROFILES[a_rt]}", flush=True)
    a_el = min(range(A), key=lambda a: score((a_rt, a)))
    best = (a_rt, a_el)
    grid = pd.DataFrame(rows)
    grid.to_csv(os.path.join(out, "fixed_profile_grid.csv"), index=False)
    by = grid.groupby(["a_rt", "a_el"])["mean_latency_ms"].mean()
    with open(FIXED_FILE, "w") as f:
        json.dump(dict(actions=best, profiles=[QTunedDijkstra.PROFILES[i] for i in best],
                       val_mean_latency_ms=float(by.min()), rule="lowest mean latency over all validation cells, coordinate search (real-time, then elastic)"),
                  f, indent=2)
    print(f"  best fixed profile pair: {best} = {[QTunedDijkstra.PROFILES[i] for i in best]} ({by.min():.2f} ms)")

    agent = QTunedDijkstra(net, seed=1)
    train_agents([agent], net, clf, pairs, forecast_fn, args.train_episodes, log=False)
    rows = []
    for kind, level, sd, scen, arr in cells:
        for st in (LoadAwareDijkstra(net), TelemetryAwareDijkstra(net),
                   QTunedDijkstra(net, fixed=best, name=FIXED), fresh_copy(agent, net)):
            f, iv, _, _, d = run_episode(st, net, arr, forecast_fn, scenario=scen)
            rows.append(dict(strategy=st.name, scenario=kind, load=level, seed=sd, **summarize(f, iv, d)))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(out, "validation_check.csv"), index=False)
    lat = df.pivot_table(index="strategy", columns="scenario", values="mean_latency_ms")
    lat["ALL"] = df.groupby("strategy")["mean_latency_ms"].mean()
    print(lat.round(2).to_string())
    print(df.groupby("strategy")[["sla_violation_pct", "jain_fairness"]].mean().round(3).to_string())


# --------------------------------------------------------------------------
# test evaluation
# --------------------------------------------------------------------------

def test_cells():
    cells = [("normal", L) for L in LOAD_LEVELS]
    cells += [(k, L) for k in SCENARIOS if k != "normal" for L in EVENT_LOADS]
    return cells


def evaluate(topo, args):
    out = os.path.join(OUT_DIR, topo)
    os.makedirs(out, exist_ok=True)
    t_start = time.time()
    net, pairs, clf, clf_metrics, forecast_fn, pred_metrics = setup(topo, args.seeds)
    print(f"[{topo}] classifier acc {clf_metrics['accuracy']:.4f}, predictor R2 {pred_metrics['r2']:.3f} "
          f"MAE {pred_metrics['mae']:.2f}", flush=True)

    fixed = load_fixed()
    trained = [QRouting(net, seed=1), make_path_ql(net), QTunedDijkstra(net, seed=1)]
    print(f"[{topo}] training {len(trained)} agents for {args.train_episodes} episodes", flush=True)
    curve = train_agents(trained, net, clf, pairs, forecast_fn, args.train_episodes)

    rows, timelines, events = [], [], []
    for kind, level in test_cells():
        for s in range(args.seeds):
            scen = Scenario(kind, net, pairs, TEST_SEED0 + s)
            events.append(dict(scenario=kind, load=level, seed=s, event=scen.describe(net)))
            arr = make_arrivals(TEST_SEED0 + s, N_INTERVALS, level, clf, host_pairs=pairs, scenario=scen)
            strategies = [StaticDijkstra(net), ECMP(net), LoadAwareDijkstra(net), TelemetryAwareDijkstra(net),
                          QTunedDijkstra(net, fixed=fixed, name=FIXED)] + \
                         [fresh_copy(a, net) for a in trained]
            for strat in strategies:
                flows, intervals, _, _, dec = run_episode(strat, net, arr, forecast_fn, scenario=scen)
                m = summarize(flows, intervals, dec)
                m["reroutes"] = int(intervals["reroutes"].iloc[-1]) if len(intervals) else 0
                rows.append(dict(topology=topo, scenario=kind, load=level, seed=s, strategy=strat.name, **m))
                if kind != "normal" and level == EVENT_LOADS[-1]:
                    per_t = flows.groupby("t")["latency_ms"].mean()
                    timelines.extend(dict(scenario=kind, seed=s, strategy=strat.name, t=int(t), latency_ms=float(v))
                                     for t, v in per_t.items())
        print(f"  [{topo}] {kind} load {level} done ({time.time() - t_start:.0f}s)", flush=True)

    raw = pd.DataFrame(rows)
    raw.to_csv(os.path.join(out, "raw_runs.csv"), index=False)
    pd.DataFrame(events).to_csv(os.path.join(out, "test_events.csv"), index=False)
    tl = pd.DataFrame(timelines)
    tl.to_csv(os.path.join(out, "timelines.csv"), index=False)

    metrics = list(METRICS)
    agg_rows = []
    for (kind, level, name), g in raw.groupby(["scenario", "load", "strategy"]):
        r = dict(scenario=kind, load=level, strategy=name)
        for m in metrics:
            r[f"{m}_mean"] = float(g[m].mean())
            r[f"{m}_ci"] = ci95(g[m])
        agg_rows.append(r)
    agg = pd.DataFrame(agg_rows)
    agg.to_csv(os.path.join(out, "summary.csv"), index=False)

    tests = significance(raw)
    tests.to_csv(os.path.join(out, "significance_tests.csv"), index=False)

    write_tables(raw, tests, out, topo)
    plot_load_sweep(agg, out)
    plot_events(agg, out)
    plot_timelines(tl, raw, out)
    plot_learning(curve, out)

    with open(os.path.join(out, "run_info.json"), "w") as f:
        json.dump(dict(topology=topo, load_levels=LOAD_LEVELS, event_loads=EVENT_LOADS, n_intervals=N_INTERVALS,
                       test_seeds=args.seeds, train_episodes=args.train_episodes, balance=BALANCE,
                       fixed_profile=[QTunedDijkstra.PROFILES[i] for i in fixed],
                       profiles=QTunedDijkstra.PROFILES,
                       qtuned_Q=trained[2].Q.tolist(), qtuned_visits=trained[2].N.tolist(),
                       classifier_accuracy=clf_metrics["accuracy"], congestion_predictor=pred_metrics,
                       path_ql_weights=trained[1].w.tolist(),
                       learning_curve=curve, runtime_s=round(time.time() - t_start, 1)), f, indent=2)
    print(f"[{topo}] saved to {os.path.abspath(out)} ({time.time() - t_start:.0f}s)", flush=True)


def significance(raw):
    tests = []
    for (kind, level), cell in raw.groupby(["scenario", "load"]):
        hyb = cell[cell["strategy"] == PROPOSED].sort_values("seed")
        for name in ORDER:
            if name == PROPOSED:
                continue
            base = cell[cell["strategy"] == name].sort_values("seed")
            for m, (_, better) in METRICS.items():
                if m == "decision_us":
                    continue
                a, b = hyb[m].values, base[m].values
                gain = (b.mean() - a.mean()) if better == "lower" else (a.mean() - b.mean())
                tests.append(dict(
                    scenario=kind, load=level, baseline=name, metric=m,
                    hybrid_mean=float(a.mean()), baseline_mean=float(b.mean()), abs_gain=float(gain),
                    improvement_pct=float(gain / abs(b.mean()) * 100) if abs(b.mean()) >= MIN_BASE_FOR_PCT else np.nan,
                    hybrid_wins_seeds=int(((a < b) if better == "lower" else (a > b)).sum()),
                    p_value=wilcoxon_p(a, b)))
    return pd.DataFrame(tests)


def write_tables(raw, tests, out, topo):
    cols = ["mean_latency_ms", "p95_latency_ms", "realtime_latency_ms", "loss_pct",
            "sla_violation_pct", "max_util_pct", "jain_fairness", "decision_us"]
    with open(os.path.join(out, "results_tables.md"), "w", encoding="utf-8") as f:
        f.write(f"# Results — {topo}\n\nMeans over test seeds (and over loads within a scenario).\n\n")
        for kind in SCENARIOS:
            d = raw[raw["scenario"] == kind].groupby("strategy")[cols].mean().reindex(ORDER)
            loads = sorted(raw[raw["scenario"] == kind]["load"].unique())
            f.write(f"## {SCEN_LABEL[kind]} (loads {loads})\n\n")
            f.write("| Strategy | " + " | ".join(METRICS[m][0] for m in cols) + " |\n")
            f.write("|---" * (len(cols) + 1) + "|\n")
            for name, r in d.iterrows():
                f.write(f"| {name} | " + " | ".join(f"{r[m]:.2f}" for m in cols) + " |\n")
            f.write("\n")

        f.write("## Proposed vs. strongest baselines (paired Wilcoxon, p < 0.05)\n\n")
        f.write("Cells = scenario × load. 'win' = significantly better, 'loss' = significantly worse.\n\n")
        f.write("| Baseline | Metric | wins | ties | losses |\n|---|---|---|---|---|\n")
        for base in [LoadAwareDijkstra.name, TelemetryAwareDijkstra.name, FIXED, PATH_QL]:
            for m in ["mean_latency_ms", "p95_latency_ms", "realtime_latency_ms", "loss_pct",
                      "sla_violation_pct", "jain_fairness"]:
                t = tests[(tests["baseline"] == base) & (tests["metric"] == m)]
                sig = t["p_value"] < 0.05
                w = int((sig & (t["abs_gain"] > 0)).sum())
                l = int((sig & (t["abs_gain"] < 0)).sum())
                f.write(f"| {base} | {METRICS[m][0]} | {w} | {len(t) - w - l} | {l} |\n")


def _style(ax):
    ax.grid(True, color="#e5e5e2", linewidth=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def plot_load_sweep(agg, out):
    d0 = agg[agg["scenario"] == "normal"]
    for metric in ["mean_latency_ms", "p95_latency_ms", "sla_violation_pct", "jain_fairness", "loss_pct"]:
        fig, ax = plt.subplots(figsize=(5.4, 3.7))
        for name in ORDER:
            d = d0[d0["strategy"] == name].sort_values("load")
            is_p = name == PROPOSED
            ax.errorbar(d["load"], d[f"{metric}_mean"], yerr=d[f"{metric}_ci"], label=name,
                        color=COLORS[name], marker=MARKERS[name], markersize=6 if is_p else 4.5,
                        linewidth=2.2 if is_p else 1.3, capsize=3, zorder=3 if is_p else 2)
        ax.set_xlabel("Offered load (mean new flows per interval)")
        ax.set_ylabel(METRICS[metric][0])
        ax.set_xticks(LOAD_LEVELS)
        _style(ax)
        ax.legend(fontsize=6.5, frameon=False)
        fig.tight_layout()
        fig.savefig(os.path.join(out, f"fig_normal_{metric}.png"), dpi=200)
        plt.close(fig)


def plot_events(agg, out):
    kinds = [k for k in SCENARIOS if k != "normal"]
    names = [n for n in ORDER if n not in (StaticDijkstra.name, QRouting.name)]   # keep the close race readable
    for metric in ["mean_latency_ms", "sla_violation_pct", "jain_fairness"]:
        fig, axes = plt.subplots(1, len(EVENT_LOADS), figsize=(7.2, 3.4), sharey=False)
        for ax, level in zip(axes, EVENT_LOADS):
            x = np.arange(len(kinds))
            width = 0.8 / len(names)
            for i, name in enumerate(names):
                d = agg[(agg["strategy"] == name) & (agg["load"] == level)].set_index("scenario").reindex(kinds)
                ax.bar(x + (i - (len(names) - 1) / 2) * width, d[f"{metric}_mean"], width,
                       yerr=d[f"{metric}_ci"], color=COLORS[name], label=name, capsize=2,
                       error_kw=dict(linewidth=0.8))
            ax.set_xticks(x)
            ax.set_xticklabels([SCEN_LABEL[k].replace(" ", "\n", 1) for k in kinds], fontsize=7)
            ax.set_title(f"Load {level}", fontsize=9)
            ax.set_ylabel(METRICS[metric][0], fontsize=8)
            _style(ax)
        axes[0].legend(fontsize=6, frameon=False)
        fig.tight_layout()
        fig.savefig(os.path.join(out, f"fig_events_{metric}.png"), dpi=200)
        plt.close(fig)


def plot_timelines(tl, raw, out):
    if tl.empty:
        return
    names = [LoadAwareDijkstra.name, TelemetryAwareDijkstra.name, FIXED, PATH_QL, PROPOSED]
    marks = {"failure": [(12, "A down"), (20, "B down"), (28, "A up")],
             "hotspot": [(15, "start"), (27, "end")], "degraded": [(10, "degraded")]}
    for kind in marks:
        d = tl[tl["scenario"] == kind]
        fig, ax = plt.subplots(figsize=(5.6, 3.3))
        for name in names:
            s = d[d["strategy"] == name].groupby("t")["latency_ms"].mean()
            ax.plot(s.index, s.values, label=name, color=COLORS[name],
                    linewidth=2.2 if name == PROPOSED else 1.3)
        for t, lab in marks[kind]:
            ax.axvline(t, color="#8a8984", linewidth=0.8, linestyle="--")
            ax.text(t + 0.3, ax.get_ylim()[1] * 0.95, lab, fontsize=6.5, color="#5a5955", va="top")
        ax.set_xlabel("Controller interval (30 s each)")
        ax.set_ylabel("Mean flow latency (ms)")
        ax.set_title(f"{SCEN_LABEL[kind]}, load {EVENT_LOADS[-1]} (mean of test seeds)", fontsize=9)
        _style(ax)
        ax.legend(fontsize=6.5, frameon=False)
        fig.tight_layout()
        fig.savefig(os.path.join(out, f"fig_timeline_{kind}.png"), dpi=200)
        plt.close(fig)


def plot_learning(curve, out):
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    w = len(SCENARIOS) * 2
    for name, ys in curve.items():
        ys = np.asarray(ys)
        if len(ys) < w:
            continue
        smooth = np.convolve(ys, np.ones(w) / w, mode="valid")
        ax.plot(np.arange(w, len(ys) + 1), smooth, label=name, color=COLORS[name], linewidth=2)
    ax.set_xlabel("Training episode")
    ax.set_ylabel(f"Mean latency (ms, {w}-episode avg)")
    _style(ax)
    ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig_learning_curve.png"), dpi=200)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topo", default="all", choices=["all"] + list(TOPOLOGIES))
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--val-seeds", type=int, default=4)
    ap.add_argument("--train-episodes", type=int, default=80)
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    global OUT_DIR
    if args.quick:
        args.seeds, args.val_seeds, args.train_episodes = 2, 1, 8
        OUT_DIR = os.path.join(OUT_DIR, "_quick")
        globals()["FIXED_FILE"] = os.path.join(OUT_DIR, "validation", "best_fixed_profile.json")
    os.makedirs(OUT_DIR, exist_ok=True)
    if args.validate:
        validate(args)
        return
    for topo in (TOPOLOGIES if args.topo == "all" else [args.topo]):
        evaluate(topo, args)


if __name__ == "__main__":
    main()
