# Results — campus8

Means over test seeds (and over loads within a scenario).

## Normal (loads [np.int64(2), np.int64(3), np.int64(4), np.int64(6), np.int64(8)])

| Strategy | Mean latency (ms) | 95th-percentile latency (ms) | Voice/video latency (ms) | Packet loss (%) | SLA violations (% of flows) | Peak link utilization (%) | Jain's fairness of link load | Decision time per flow (µs) |
|---|---|---|---|---|---|---|---|---|
| Static Dijkstra | 32.71 | 91.72 | 31.68 | 12.89 | 29.18 | 90.17 | 0.35 | 22.52 |
| ECMP | 15.62 | 49.88 | 14.69 | 4.98 | 14.54 | 77.46 | 0.48 | 23.54 |
| Load-aware Dijkstra | 8.86 | 21.81 | 8.72 | 0.35 | 3.00 | 55.26 | 0.63 | 172.91 |
| Telemetry-aware Dijkstra | 9.02 | 21.40 | 8.86 | 0.36 | 3.07 | 55.19 | 0.63 | 182.38 |
| Best fixed-profile Dijkstra | 8.73 | 20.78 | 8.38 | 0.35 | 2.87 | 53.92 | 0.65 | 225.09 |
| Q-Routing (RL only) | 50.35 | 138.55 | 47.50 | 16.56 | 38.90 | 94.32 | 0.55 | 68.29 |
| Hybrid path-selection QL (v2, ablation) | 9.18 | 21.70 | 8.90 | 0.52 | 3.61 | 54.96 | 0.61 | 318.74 |
| Hybrid QL-tuned Dijkstra (proposed) | 9.12 | 21.67 | 8.98 | 0.40 | 3.46 | 55.56 | 0.63 | 252.81 |

## Link failures (loads [np.int64(3), np.int64(6)])

| Strategy | Mean latency (ms) | 95th-percentile latency (ms) | Voice/video latency (ms) | Packet loss (%) | SLA violations (% of flows) | Peak link utilization (%) | Jain's fairness of link load | Decision time per flow (µs) |
|---|---|---|---|---|---|---|---|---|
| Static Dijkstra | 24.81 | 91.32 | 23.66 | 8.68 | 23.26 | 84.70 | 0.48 | 51.66 |
| ECMP | 20.99 | 65.06 | 20.13 | 7.88 | 22.75 | 88.32 | 0.49 | 49.78 |
| Load-aware Dijkstra | 13.55 | 37.68 | 13.43 | 1.94 | 9.34 | 67.11 | 0.66 | 176.59 |
| Telemetry-aware Dijkstra | 14.21 | 38.85 | 14.12 | 2.28 | 10.48 | 67.78 | 0.66 | 187.96 |
| Best fixed-profile Dijkstra | 13.32 | 37.36 | 12.94 | 1.92 | 8.75 | 66.07 | 0.68 | 221.81 |
| Q-Routing (RL only) | 59.92 | 168.36 | 57.47 | 18.42 | 48.21 | 102.42 | 0.62 | 61.15 |
| Hybrid path-selection QL (v2, ablation) | 14.18 | 42.53 | 13.95 | 2.40 | 10.62 | 67.76 | 0.62 | 445.25 |
| Hybrid QL-tuned Dijkstra (proposed) | 13.57 | 39.46 | 13.43 | 2.13 | 9.28 | 67.21 | 0.66 | 251.99 |

## Flash-crowd hotspot (loads [np.int64(3), np.int64(6)])

| Strategy | Mean latency (ms) | 95th-percentile latency (ms) | Voice/video latency (ms) | Packet loss (%) | SLA violations (% of flows) | Peak link utilization (%) | Jain's fairness of link load | Decision time per flow (µs) |
|---|---|---|---|---|---|---|---|---|
| Static Dijkstra | 40.76 | 110.97 | 39.05 | 17.45 | 40.78 | 106.98 | 0.39 | 29.53 |
| ECMP | 19.36 | 61.35 | 17.87 | 7.10 | 20.93 | 90.10 | 0.53 | 31.94 |
| Load-aware Dijkstra | 11.41 | 34.43 | 10.91 | 1.29 | 7.02 | 65.16 | 0.70 | 193.90 |
| Telemetry-aware Dijkstra | 11.85 | 35.83 | 11.43 | 1.39 | 7.65 | 64.63 | 0.70 | 211.29 |
| Best fixed-profile Dijkstra | 11.66 | 35.50 | 10.93 | 1.25 | 7.28 | 64.16 | 0.72 | 240.86 |
| Q-Routing (RL only) | 61.86 | 168.68 | 58.65 | 20.89 | 50.90 | 109.78 | 0.61 | 70.81 |
| Hybrid path-selection QL (v2, ablation) | 12.21 | 37.96 | 11.56 | 1.49 | 8.25 | 65.47 | 0.67 | 504.19 |
| Hybrid QL-tuned Dijkstra (proposed) | 11.73 | 34.16 | 11.24 | 1.38 | 7.44 | 64.78 | 0.70 | 264.93 |

## Silent link degradation (loads [np.int64(3), np.int64(6)])

| Strategy | Mean latency (ms) | 95th-percentile latency (ms) | Voice/video latency (ms) | Packet loss (%) | SLA violations (% of flows) | Peak link utilization (%) | Jain's fairness of link load | Decision time per flow (µs) |
|---|---|---|---|---|---|---|---|---|
| Static Dijkstra | 40.27 | 104.83 | 39.06 | 22.81 | 53.08 | 140.50 | 0.32 | 28.77 |
| ECMP | 16.64 | 54.17 | 15.45 | 6.45 | 26.46 | 88.37 | 0.47 | 30.41 |
| Load-aware Dijkstra | 12.79 | 43.56 | 12.39 | 4.20 | 24.62 | 84.15 | 0.56 | 204.03 |
| Telemetry-aware Dijkstra | 9.83 | 25.42 | 9.45 | 1.48 | 13.41 | 65.89 | 0.63 | 218.93 |
| Best fixed-profile Dijkstra | 9.41 | 26.74 | 8.65 | 1.54 | 11.14 | 66.99 | 0.64 | 257.25 |
| Q-Routing (RL only) | 57.43 | 161.47 | 54.39 | 20.36 | 59.74 | 113.30 | 0.55 | 72.50 |
| Hybrid path-selection QL (v2, ablation) | 10.38 | 29.56 | 10.05 | 1.89 | 17.17 | 68.96 | 0.59 | 505.66 |
| Hybrid QL-tuned Dijkstra (proposed) | 11.30 | 34.24 | 11.04 | 2.27 | 19.06 | 71.41 | 0.61 | 287.87 |

## Proposed vs. strongest baselines (paired Wilcoxon, p < 0.05)

Cells = scenario × load. 'win' = significantly better, 'loss' = significantly worse.

| Baseline | Metric | wins | ties | losses |
|---|---|---|---|---|
| Load-aware Dijkstra | Mean latency (ms) | 2 | 8 | 1 |
| Load-aware Dijkstra | 95th-percentile latency (ms) | 1 | 10 | 0 |
| Load-aware Dijkstra | Voice/video latency (ms) | 2 | 8 | 1 |
| Load-aware Dijkstra | Packet loss (%) | 2 | 9 | 0 |
| Load-aware Dijkstra | SLA violations (% of flows) | 1 | 9 | 1 |
| Load-aware Dijkstra | Jain's fairness of link load | 2 | 8 | 1 |
| Telemetry-aware Dijkstra | Mean latency (ms) | 1 | 9 | 1 |
| Telemetry-aware Dijkstra | 95th-percentile latency (ms) | 0 | 10 | 1 |
| Telemetry-aware Dijkstra | Voice/video latency (ms) | 1 | 9 | 1 |
| Telemetry-aware Dijkstra | Packet loss (%) | 0 | 10 | 1 |
| Telemetry-aware Dijkstra | SLA violations (% of flows) | 0 | 9 | 2 |
| Telemetry-aware Dijkstra | Jain's fairness of link load | 0 | 9 | 2 |
| Best fixed-profile Dijkstra | Mean latency (ms) | 0 | 7 | 4 |
| Best fixed-profile Dijkstra | 95th-percentile latency (ms) | 0 | 10 | 1 |
| Best fixed-profile Dijkstra | Voice/video latency (ms) | 0 | 4 | 7 |
| Best fixed-profile Dijkstra | Packet loss (%) | 0 | 10 | 1 |
| Best fixed-profile Dijkstra | SLA violations (% of flows) | 0 | 8 | 3 |
| Best fixed-profile Dijkstra | Jain's fairness of link load | 0 | 3 | 8 |
| Hybrid path-selection QL (v2, ablation) | Mean latency (ms) | 1 | 9 | 1 |
| Hybrid path-selection QL (v2, ablation) | 95th-percentile latency (ms) | 1 | 10 | 0 |
| Hybrid path-selection QL (v2, ablation) | Voice/video latency (ms) | 0 | 11 | 0 |
| Hybrid path-selection QL (v2, ablation) | Packet loss (%) | 1 | 10 | 0 |
| Hybrid path-selection QL (v2, ablation) | SLA violations (% of flows) | 1 | 10 | 0 |
| Hybrid path-selection QL (v2, ablation) | Jain's fairness of link load | 8 | 3 | 0 |
