"""
hybrid_experiment.py
Paper experiment: proposed Hybrid Dijkstra + Q-learning routing vs.
four baselines, across several traffic loads and independent random seeds.

Protocol (train / test separation, so nothing is tuned on test data):
    1. Train the TrafficClassifier offline (as in the original project).
    2. Pre-train the CongestionPredictor on link-utilization traces from
       TRAINING seeds (routed by Static Dijkstra and ECMP), report its
       error on separate held-out traces.
    3. Train the two learning agents (Q-Routing, Hybrid) on TRAINING seeds
       with epsilon-greedy exploration.
    4. Evaluate every strategy on the same TEST seeds and loads. Learning
       agents start each test run from their trained state, keep learning
       online, but never explore (epsilon = 0).
    5. Report mean +/- 95% CI over seeds, and paired Wilcoxon signed-rank
       tests of Hybrid vs. each baseline.

Outputs go to ../results/hybrid/ (the original results/ files are untouched).

    python hybrid_experiment.py            # full run
    python hybrid_experiment.py --quick    # small smoke test
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
from scipy import stats

from topology import build_topology, HOST_PAIRS
from traffic_gen import generate_flows
from ml_models import TrafficClassifier, CongestionPredictor
from netsim import Net, make_arrivals, make_forecaster, run_episode, summarize, exog_series
from routing import StaticDijkstra, ECMP, LoadAwareDijkstra, QRouting, HybridDijkstraQL

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "results", "hybrid")

LOAD_LEVELS = [2, 3, 4, 6, 8]           # mean new flows per interval (calibrated on Static Dijkstra only)
N_INTERVALS = 40
TRAIN_SEED0, PRED_TEST_SEED0, TEST_SEED0 = 10_000, 20_000, 0

METRICS = {
    "mean_latency_ms": ("Mean latency (ms)", "lower"),
    "p95_latency_ms": ("95th-percentile latency (ms)", "lower"),
    "realtime_latency_ms": ("Voice/video latency (ms)", "lower"),
    "loss_pct": ("Packet loss (%)", "lower"),
    "sla_violation_pct": ("SLA violations (% of flows)", "lower"),
    "max_util_pct": ("Peak link utilization (%)", "lower"),
    "jain_fairness": ("Jain's fairness of link load", "higher"),
    "decision_us": ("Decision time per flow (µs)", "lower"),
}
PROPOSED = HybridDijkstraQL.name
MIN_BASE_FOR_PCT = 0.1     # below this baseline value a % improvement is not reported

# categorical slots 1-5 of the reference palette; proposed method gets slot 1
COLORS = {
    PROPOSED: "#2a78d6",
    StaticDijkstra.name: "#eb6834",
    ECMP.name: "#1baf7a",
    LoadAwareDijkstra.name: "#eda100",
    QRouting.name: "#e87ba4",
}
MARKERS = {PROPOSED: "o", StaticDijkstra.name: "s", ECMP.name: "^",
           LoadAwareDijkstra.name: "D", QRouting.name: "v"}


def _traces(net, clf, seed0, n_seeds):
    """Per-link (util series, exog series) from Static Dijkstra and ECMP runs."""
    series, exogs = [], []
    zero = lambda h, c, t: np.zeros(len(net.edges))
    for i in range(n_seeds):
        level = LOAD_LEVELS[i % len(LOAD_LEVELS)]
        arr = make_arrivals(seed0 + i, N_INTERVALS, level, clf)
        for S in (StaticDijkstra, ECMP):
            _, _, hist, carried, _ = run_episode(S(net), net, arr, zero)
            ex = exog_series(hist, carried)
            series.extend(hist.T)
            exogs.extend(ex[:, e, :] for e in range(hist.shape[1]))
    return series, exogs


def pretrain_predictor(net, clf, n_seeds):
    tr_s, tr_x = _traces(net, clf, TRAIN_SEED0, n_seeds)
    te_s, te_x = _traces(net, clf, PRED_TEST_SEED0, n_seeds)

    w = 4
    # forest learns the correction on top of the carried-over load (column w = first exog feature)
    pred = CongestionPredictor(window=w).fit_pooled(tr_s, tr_x, residual_col=w)
    direct = CongestionPredictor(window=w).fit_pooled(tr_s, tr_x)    # same features, no residual
    lag_only = CongestionPredictor(window=w).fit_pooled(tr_s)        # original feature set

    X, y = zip(*(pred._make_lag_features(s, x) for s, x in zip(te_s, te_x)))
    X, y = np.vstack(X), np.concatenate(y)
    hot = y > 70.0      # links about to be congested: the ones routing decisions hinge on
    forecasts = {
        "residual_rf": pred.predict_many(X),
        "direct_rf": direct.predict_many(X),
        "lag_only_rf": lag_only.predict_many(X[:, :w]),
        "naive_last_value": X[:, w - 1],
        "naive_carried_load": X[:, w],
    }
    p = forecasts["residual_rf"]
    return pred, {
        "r2": float(1 - ((p - y) ** 2).sum() / ((y - y.mean()) ** 2).sum()),
        "by_model": {
            name: dict(mae=float(np.mean(np.abs(f - y))),
                       rmse=float(np.sqrt(np.mean((f - y) ** 2))),
                       mae_congested_links=float(np.mean(np.abs(f[hot] - y[hot]))))
            for name, f in forecasts.items()
        },
    }


def train_agents(net, clf, forecast_fn, n_episodes):
    agents = [QRouting(net, seed=1), HybridDijkstraQL(net, seed=1)]
    curve = {a.name: [] for a in agents}
    for ep in range(n_episodes):
        eps = max(0.02, 0.3 * (1 - ep / (0.7 * n_episodes)))
        level = LOAD_LEVELS[ep % len(LOAD_LEVELS)]
        arr = make_arrivals(TRAIN_SEED0 + 500 + ep, N_INTERVALS, level, clf)
        for a in agents:
            a.eps = eps
            flows, _, _, _, _ = run_episode(a, net, arr, forecast_fn, train=True)
            curve[a.name].append(float(flows["latency_ms"].mean()))
        if (ep + 1) % 10 == 0:
            print(f"  training episode {ep + 1}/{n_episodes}  eps={eps:.2f}  "
                  + "  ".join(f"{k}: {v[-1]:.1f}ms" for k, v in curve.items()))
    return agents, curve


def ci95(x):
    x = np.asarray(x, dtype=float)
    if len(x) < 2:
        return 0.0
    return float(stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x)))


def wilcoxon_p(a, b):
    a, b = np.asarray(a), np.asarray(b)
    if np.allclose(a, b):
        return 1.0
    return float(stats.wilcoxon(a, b).pvalue)


def plot_metric(agg, metric, path):
    label, _ = METRICS[metric]
    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    for name in agg["strategy"].unique():
        d = agg[agg["strategy"] == name].sort_values("load")
        is_p = name == PROPOSED
        ax.errorbar(d["load"], d[f"{metric}_mean"], yerr=d[f"{metric}_ci"],
                    label=name, color=COLORS[name], marker=MARKERS[name],
                    markersize=6 if is_p else 5, linewidth=2.2 if is_p else 1.4,
                    capsize=3, zorder=3 if is_p else 2)
    ax.set_xlabel("Offered load (mean new flows per interval)")
    ax.set_ylabel(label)
    ax.set_xticks(LOAD_LEVELS)
    ax.grid(True, color="#e5e5e2", linewidth=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def plot_vs_strongest(raw, path):
    """Paired per-seed improvement of the hybrid over Load-aware Dijkstra (zoom-in of the close race)."""
    hyb = raw[raw["strategy"] == PROPOSED].sort_values(["load", "seed"])
    base = raw[raw["strategy"] == LoadAwareDijkstra.name].sort_values(["load", "seed"])
    series = [("mean_latency_ms", "Mean latency", "#2a78d6", "o"),
              ("p95_latency_ms", "95th-pct latency", "#eb6834", "s"),
              ("realtime_latency_ms", "Voice/video latency", "#1baf7a", "^")]
    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    ax.axhline(0, color="#8a8984", linewidth=1)
    offsets = np.linspace(-0.12, 0.12, len(series))
    for (m, label, color, marker), off in zip(series, offsets):
        means, cis = [], []
        for level in LOAD_LEVELS:
            a = hyb[hyb["load"] == level][m].values
            b = base[base["load"] == level][m].values
            gain = (b - a) / b * 100           # positive = hybrid better
            means.append(gain.mean())
            cis.append(ci95(gain))
        ax.errorbar(np.array(LOAD_LEVELS) + off, means, yerr=cis, label=label, color=color,
                    marker=marker, markersize=5, linewidth=1.8, capsize=3)
    ax.set_xlabel("Offered load (mean new flows per interval)")
    ax.set_ylabel("Improvement over Load-aware\nDijkstra (%, paired)")
    ax.set_xticks(LOAD_LEVELS)
    ax.grid(True, color="#e5e5e2", linewidth=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def plot_learning(curve, path):
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    for name, ys in curve.items():
        ys = np.asarray(ys)
        # per-episode load varies, so smooth over one full load cycle
        w = len(LOAD_LEVELS)
        smooth = np.convolve(ys, np.ones(w) / w, mode="valid")
        ax.plot(np.arange(w, len(ys) + 1), smooth, label=name, color=COLORS[name], linewidth=2)
    ax.set_xlabel("Training episode")
    ax.set_ylabel(f"Mean latency (ms, {len(LOAD_LEVELS)}-episode avg)")
    ax.grid(True, color="#e5e5e2", linewidth=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--train-episodes", type=int, default=60)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    if args.quick:
        args.seeds, args.train_episodes = 2, 5
    os.makedirs(OUT_DIR, exist_ok=True)
    t_start = time.time()

    net = Net(build_topology())
    clf = TrafficClassifier()
    clf_metrics = clf.fit(generate_flows(1500, HOST_PAIRS, seed=1))
    print(f"[1/4] classifier accuracy {clf_metrics['accuracy']:.4f}")

    predictor, pred_metrics = pretrain_predictor(net, clf, n_seeds=max(2, args.seeds))
    forecast_fn = make_forecaster(predictor, predictor.window)
    print(f"[2/4] congestion predictor (R2 {pred_metrics['r2']:.3f}), error in % points:")
    for name, e in pred_metrics["by_model"].items():
        print(f"      {name:20s} MAE {e['mae']:.2f}  RMSE {e['rmse']:.2f}  "
              f"MAE on congested links {e['mae_congested_links']:.2f}")

    print(f"[3/4] training learning agents for {args.train_episodes} episodes")
    trained, curve = train_agents(net, clf, forecast_fn, args.train_episodes)

    print(f"[4/4] evaluating on {args.seeds} test seeds x {len(LOAD_LEVELS)} loads")
    rows, fallback_counts = [], []
    for level in LOAD_LEVELS:
        for s in range(args.seeds):
            arr = make_arrivals(TEST_SEED0 + s, N_INTERVALS, level, clf)
            strategies = [StaticDijkstra(net), ECMP(net), LoadAwareDijkstra(net)] + \
                         [copy.deepcopy(a) for a in trained]
            for strat in strategies:
                if isinstance(strat, HybridDijkstraQL):
                    strat.fallbacks = 0
                flows, intervals, _, _, dec = run_episode(strat, net, arr, forecast_fn, train=False)
                rows.append(dict(strategy=strat.name, load=level, seed=s, **summarize(flows, intervals, dec)))
                if isinstance(strat, HybridDijkstraQL):
                    fallback_counts.append(strat.fallbacks)
        print(f"  load {level} done ({time.time() - t_start:.0f}s)")

    raw = pd.DataFrame(rows)
    raw.to_csv(os.path.join(OUT_DIR, "raw_runs.csv"), index=False)

    agg_rows = []
    for (name, level), g in raw.groupby(["strategy", "load"]):
        r = dict(strategy=name, load=level)
        for m in METRICS:
            r[f"{m}_mean"] = float(g[m].mean())
            r[f"{m}_ci"] = ci95(g[m])
        agg_rows.append(r)
    agg = pd.DataFrame(agg_rows)
    agg.to_csv(os.path.join(OUT_DIR, "summary_by_load.csv"), index=False)

    # paired significance tests: Hybrid vs each baseline, per load, per metric
    tests = []
    hyb = raw[raw["strategy"] == PROPOSED].sort_values(["load", "seed"])
    for name in raw["strategy"].unique():
        if name == PROPOSED:
            continue
        base = raw[raw["strategy"] == name].sort_values(["load", "seed"])
        for m, (_, better) in METRICS.items():
            if m == "decision_us":
                continue
            for level in LOAD_LEVELS:
                a = hyb[hyb["load"] == level][m].values
                b = base[base["load"] == level][m].values
                diff = a.mean() - b.mean()
                gain = -diff if better == "lower" else diff
                # a % change of a ~zero baseline (e.g. 0.001% loss) is meaningless; report
                # the absolute difference instead and leave the % blank
                improvement = gain / abs(b.mean()) * 100 if abs(b.mean()) >= MIN_BASE_FOR_PCT else np.nan
                tests.append(dict(baseline=name, metric=m, load=level,
                                  hybrid_mean=float(a.mean()), baseline_mean=float(b.mean()),
                                  abs_gain=float(gain),
                                  improvement_pct=float(improvement),
                                  hybrid_wins_seeds=int(((a < b) if better == "lower" else (a > b)).sum()),
                                  p_value=wilcoxon_p(a, b)))
    tests = pd.DataFrame(tests)
    tests.to_csv(os.path.join(OUT_DIR, "significance_tests.csv"), index=False)

    for m in METRICS:
        plot_metric(agg, m, os.path.join(OUT_DIR, f"fig_{m}.png"))
    plot_learning(curve, os.path.join(OUT_DIR, "fig_learning_curve.png"))
    plot_vs_strongest(raw, os.path.join(OUT_DIR, "fig_hybrid_vs_loadaware.png"))

    # overall (all loads pooled) table for the paper
    overall = raw.groupby("strategy")[list(METRICS)].mean()
    overall = overall.reindex([StaticDijkstra.name, ECMP.name, LoadAwareDijkstra.name,
                               QRouting.name, PROPOSED])
    with open(os.path.join(OUT_DIR, "results_table.md"), "w", encoding="utf-8") as f:
        f.write("| Strategy | " + " | ".join(METRICS[m][0] for m in METRICS) + " |\n")
        f.write("|---" * (len(METRICS) + 1) + "|\n")
        for name, r in overall.iterrows():
            f.write(f"| {name} | " + " | ".join(f"{r[m]:.2f}" for m in METRICS) + " |\n")

    payload = dict(
        config=dict(load_levels=LOAD_LEVELS, n_intervals=N_INTERVALS, test_seeds=args.seeds,
                    train_episodes=args.train_episodes),
        classifier_accuracy=clf_metrics["accuracy"],
        congestion_predictor=pred_metrics,
        hybrid_fallbacks_per_run=float(np.mean(fallback_counts)) if fallback_counts else 0.0,
        hybrid_weights=trained[1].w.tolist(),
        overall=overall.reset_index().to_dict("records"),
        learning_curve=curve,
        runtime_s=round(time.time() - t_start, 1),
    )
    with open(os.path.join(OUT_DIR, "hybrid_results.json"), "w") as f:
        json.dump(payload, f, indent=2)

    print("\nOverall (all loads pooled):")
    print(overall.round(2).to_string())
    print(f"\nSaved to {os.path.abspath(OUT_DIR)}  ({payload['runtime_s']}s)")


if __name__ == "__main__":
    main()
