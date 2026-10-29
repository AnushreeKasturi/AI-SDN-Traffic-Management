# Results — campus8

Means over test seeds (and over loads within a scenario).

## Normal (loads [np.int64(2), np.int64(3), np.int64(4), np.int64(6), np.int64(8)])

| Strategy | Mean latency (ms) | 95th-percentile latency (ms) | Voice/video latency (ms) | Packet loss (%) | SLA violations (% of flows) | Peak link utilization (%) | Jain's fairness of link load | Decision time per flow (µs) |
|---|---|---|---|---|---|---|---|---|
| Static Dijkstra | 32.71 | 91.72 | 31.68 | 12.89 | 29.18 | 90.17 | 0.35 | 30.30 |
| ECMP | 15.62 | 49.88 | 14.69 | 4.98 | 14.54 | 77.46 | 0.48 | 32.26 |
| Load-aware Dijkstra | 8.86 | 21.81 | 8.72 | 0.35 | 3.00 | 55.26 | 0.63 | 201.24 |
| Telemetry-aware Dijkstra | 9.02 | 21.40 | 8.86 | 0.36 | 3.07 | 55.19 | 0.63 | 216.04 |
| Q-Routing (RL only) | 50.35 | 138.55 | 47.50 | 16.56 | 38.90 | 94.32 | 0.55 | 71.59 |
| Hybrid, v1 features (ablation) | 9.30 | 23.03 | 9.00 | 0.62 | 3.71 | 54.85 | 0.63 | 329.25 |
| Hybrid v2 (proposed) | 9.18 | 21.70 | 8.90 | 0.52 | 3.61 | 54.96 | 0.61 | 502.88 |

## Link failures (loads [np.int64(3), np.int64(6)])

| Strategy | Mean latency (ms) | 95th-percentile latency (ms) | Voice/video latency (ms) | Packet loss (%) | SLA violations (% of flows) | Peak link utilization (%) | Jain's fairness of link load | Decision time per flow (µs) |
|---|---|---|---|---|---|---|---|---|
| Static Dijkstra | 24.81 | 91.32 | 23.66 | 8.68 | 23.26 | 84.70 | 0.48 | 58.10 |
| ECMP | 20.99 | 65.06 | 20.13 | 7.88 | 22.75 | 88.32 | 0.49 | 55.09 |
| Load-aware Dijkstra | 13.55 | 37.68 | 13.43 | 1.94 | 9.34 | 67.11 | 0.66 | 200.44 |
| Telemetry-aware Dijkstra | 14.21 | 38.85 | 14.12 | 2.28 | 10.48 | 67.78 | 0.66 | 216.16 |
| Q-Routing (RL only) | 59.92 | 168.36 | 57.47 | 18.42 | 48.21 | 102.42 | 0.62 | 72.67 |
| Hybrid, v1 features (ablation) | 14.10 | 41.24 | 13.77 | 2.32 | 10.05 | 66.92 | 0.65 | 374.89 |
| Hybrid v2 (proposed) | 14.18 | 42.53 | 13.95 | 2.40 | 10.62 | 67.76 | 0.62 | 546.04 |

## Flash-crowd hotspot (loads [np.int64(3), np.int64(6)])

| Strategy | Mean latency (ms) | 95th-percentile latency (ms) | Voice/video latency (ms) | Packet loss (%) | SLA violations (% of flows) | Peak link utilization (%) | Jain's fairness of link load | Decision time per flow (µs) |
|---|---|---|---|---|---|---|---|---|
| Static Dijkstra | 40.76 | 110.97 | 39.05 | 17.45 | 40.78 | 106.98 | 0.39 | 22.87 |
| ECMP | 19.36 | 61.35 | 17.87 | 7.10 | 20.93 | 90.10 | 0.53 | 22.61 |
| Load-aware Dijkstra | 11.41 | 34.43 | 10.91 | 1.29 | 7.02 | 65.16 | 0.70 | 155.05 |
| Telemetry-aware Dijkstra | 11.85 | 35.83 | 11.43 | 1.39 | 7.65 | 64.63 | 0.70 | 166.63 |
| Q-Routing (RL only) | 61.86 | 168.68 | 58.65 | 20.89 | 50.90 | 109.78 | 0.61 | 61.06 |
| Hybrid, v1 features (ablation) | 12.31 | 36.67 | 11.68 | 1.55 | 8.45 | 65.40 | 0.69 | 222.24 |
| Hybrid v2 (proposed) | 12.21 | 37.96 | 11.56 | 1.49 | 8.25 | 65.47 | 0.67 | 340.53 |

## Silent link degradation (loads [np.int64(3), np.int64(6)])

| Strategy | Mean latency (ms) | 95th-percentile latency (ms) | Voice/video latency (ms) | Packet loss (%) | SLA violations (% of flows) | Peak link utilization (%) | Jain's fairness of link load | Decision time per flow (µs) |
|---|---|---|---|---|---|---|---|---|
| Static Dijkstra | 40.27 | 104.83 | 39.06 | 22.81 | 53.08 | 140.50 | 0.32 | 26.57 |
| ECMP | 16.64 | 54.17 | 15.45 | 6.45 | 26.46 | 88.37 | 0.47 | 28.64 |
| Load-aware Dijkstra | 12.79 | 43.56 | 12.39 | 4.20 | 24.62 | 84.15 | 0.56 | 189.43 |
| Telemetry-aware Dijkstra | 9.83 | 25.42 | 9.45 | 1.48 | 13.41 | 65.89 | 0.63 | 205.24 |
| Q-Routing (RL only) | 57.43 | 161.47 | 54.39 | 20.36 | 59.74 | 113.30 | 0.55 | 68.16 |
| Hybrid, v1 features (ablation) | 12.26 | 41.19 | 12.01 | 3.97 | 22.79 | 79.78 | 0.58 | 293.09 |
| Hybrid v2 (proposed) | 10.38 | 29.56 | 10.05 | 1.89 | 17.17 | 68.96 | 0.59 | 437.33 |

## Hybrid v2 vs. strongest baselines (paired Wilcoxon, p < 0.05)

Cells = scenario × load. 'win' = significantly better, 'loss' = significantly worse.

| Baseline | Metric | wins | ties | losses |
|---|---|---|---|---|
| Load-aware Dijkstra | Mean latency (ms) | 3 | 6 | 2 |
| Load-aware Dijkstra | 95th-percentile latency (ms) | 1 | 8 | 2 |
| Load-aware Dijkstra | Voice/video latency (ms) | 4 | 6 | 1 |
| Load-aware Dijkstra | Packet loss (%) | 2 | 7 | 2 |
| Load-aware Dijkstra | SLA violations (% of flows) | 2 | 8 | 1 |
| Load-aware Dijkstra | Jain's fairness of link load | 1 | 4 | 6 |
| Telemetry-aware Dijkstra | Mean latency (ms) | 0 | 11 | 0 |
| Telemetry-aware Dijkstra | 95th-percentile latency (ms) | 0 | 10 | 1 |
| Telemetry-aware Dijkstra | Voice/video latency (ms) | 1 | 10 | 0 |
| Telemetry-aware Dijkstra | Packet loss (%) | 0 | 9 | 2 |
| Telemetry-aware Dijkstra | SLA violations (% of flows) | 0 | 9 | 2 |
| Telemetry-aware Dijkstra | Jain's fairness of link load | 0 | 2 | 9 |
| Hybrid, v1 features (ablation) | Mean latency (ms) | 2 | 8 | 1 |
| Hybrid, v1 features (ablation) | 95th-percentile latency (ms) | 1 | 10 | 0 |
| Hybrid, v1 features (ablation) | Voice/video latency (ms) | 2 | 9 | 0 |
| Hybrid, v1 features (ablation) | Packet loss (%) | 2 | 9 | 0 |
| Hybrid, v1 features (ablation) | SLA violations (% of flows) | 2 | 9 | 0 |
| Hybrid, v1 features (ablation) | Jain's fairness of link load | 1 | 3 | 7 |
