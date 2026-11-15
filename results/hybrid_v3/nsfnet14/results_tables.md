# Results — nsfnet14

Means over test seeds (and over loads within a scenario).

## Normal (loads 2, 3, 4, 6, 8)

| Strategy | Mean latency (ms) | 95th-percentile latency (ms) | Voice/video latency (ms) | Packet loss (%) | SLA violations (% of flows) | Peak link utilization (%) | Jain's fairness of link load | Decision time per flow (µs) |
|---|---|---|---|---|---|---|---|---|
| Static Dijkstra | 40.54 | 103.85 | 38.79 | 11.20 | 32.27 | 84.47 | 0.29 | 34.19 |
| ECMP | 29.94 | 68.59 | 28.83 | 7.61 | 26.99 | 85.80 | 0.32 | 35.55 |
| Load-aware Dijkstra | 18.80 | 32.05 | 18.69 | 0.27 | 9.97 | 58.53 | 0.50 | 296.35 |
| Telemetry-aware Dijkstra | 19.03 | 32.58 | 18.92 | 0.26 | 10.47 | 58.36 | 0.51 | 317.02 |
| Q-Routing (RL only) | 75.67 | 199.76 | 72.18 | 15.10 | 61.32 | 89.74 | 0.61 | 118.72 |
| Hybrid path-selection QL | 18.81 | 35.85 | 18.18 | 0.31 | 8.84 | 60.59 | 0.44 | 524.52 |
| Hybrid QL-tuned Dijkstra | 19.58 | 33.86 | 19.51 | 0.35 | 11.54 | 58.32 | 0.52 | 405.61 |
| Best fixed-profile Dijkstra | 18.26 | 31.99 | 17.42 | 0.20 | 8.05 | 55.40 | 0.53 | 369.60 |

## Link failures (loads 3, 6)

| Strategy | Mean latency (ms) | 95th-percentile latency (ms) | Voice/video latency (ms) | Packet loss (%) | SLA violations (% of flows) | Peak link utilization (%) | Jain's fairness of link load | Decision time per flow (µs) |
|---|---|---|---|---|---|---|---|---|
| Static Dijkstra | 38.56 | 104.05 | 36.90 | 9.72 | 32.23 | 82.60 | 0.36 | 83.11 |
| ECMP | 31.95 | 78.84 | 30.68 | 6.49 | 28.15 | 83.45 | 0.38 | 70.09 |
| Load-aware Dijkstra | 20.14 | 33.73 | 20.01 | 0.33 | 11.98 | 61.93 | 0.54 | 287.12 |
| Telemetry-aware Dijkstra | 20.46 | 36.49 | 20.41 | 0.29 | 12.45 | 61.57 | 0.55 | 308.94 |
| Q-Routing (RL only) | 69.95 | 193.29 | 66.04 | 13.85 | 60.49 | 90.92 | 0.62 | 114.15 |
| Hybrid path-selection QL | 20.08 | 37.46 | 19.50 | 0.33 | 10.50 | 63.41 | 0.48 | 570.59 |
| Hybrid QL-tuned Dijkstra | 20.60 | 36.16 | 20.62 | 0.40 | 12.71 | 61.49 | 0.56 | 373.73 |
| Best fixed-profile Dijkstra | 19.78 | 35.45 | 19.03 | 0.26 | 10.29 | 59.12 | 0.57 | 343.13 |

## Flash-crowd hotspot (loads 3, 6)

| Strategy | Mean latency (ms) | 95th-percentile latency (ms) | Voice/video latency (ms) | Packet loss (%) | SLA violations (% of flows) | Peak link utilization (%) | Jain's fairness of link load | Decision time per flow (µs) |
|---|---|---|---|---|---|---|---|---|
| Static Dijkstra | 45.75 | 125.00 | 43.52 | 14.50 | 37.24 | 96.55 | 0.33 | 29.80 |
| ECMP | 32.28 | 90.26 | 30.57 | 9.76 | 30.26 | 96.39 | 0.37 | 30.57 |
| Load-aware Dijkstra | 19.57 | 43.93 | 19.11 | 0.72 | 12.04 | 65.92 | 0.57 | 266.15 |
| Telemetry-aware Dijkstra | 20.41 | 46.91 | 20.02 | 0.73 | 13.62 | 66.00 | 0.58 | 291.38 |
| Q-Routing (RL only) | 101.42 | 276.49 | 95.30 | 24.85 | 66.57 | 108.99 | 0.66 | 106.42 |
| Hybrid path-selection QL | 19.73 | 44.22 | 18.93 | 0.67 | 11.65 | 68.30 | 0.49 | 491.86 |
| Hybrid QL-tuned Dijkstra | 20.57 | 46.76 | 20.10 | 0.68 | 14.18 | 65.93 | 0.59 | 344.91 |
| Best fixed-profile Dijkstra | 19.65 | 45.48 | 18.39 | 0.53 | 11.10 | 63.36 | 0.59 | 314.43 |

## Silent link degradation (loads 3, 6)

| Strategy | Mean latency (ms) | 95th-percentile latency (ms) | Voice/video latency (ms) | Packet loss (%) | SLA violations (% of flows) | Peak link utilization (%) | Jain's fairness of link load | Decision time per flow (µs) |
|---|---|---|---|---|---|---|---|---|
| Static Dijkstra | 43.13 | 119.43 | 41.02 | 14.36 | 47.88 | 104.17 | 0.28 | 29.89 |
| ECMP | 30.19 | 72.24 | 28.65 | 8.89 | 34.81 | 96.32 | 0.32 | 31.06 |
| Load-aware Dijkstra | 21.76 | 46.37 | 21.37 | 3.20 | 27.70 | 79.19 | 0.46 | 291.46 |
| Telemetry-aware Dijkstra | 19.75 | 39.84 | 19.52 | 1.07 | 21.09 | 66.61 | 0.51 | 317.03 |
| Q-Routing (RL only) | 75.97 | 222.86 | 71.62 | 17.89 | 69.62 | 108.18 | 0.59 | 114.80 |
| Hybrid path-selection QL | 20.52 | 46.36 | 19.88 | 1.75 | 25.34 | 72.04 | 0.43 | 503.73 |
| Hybrid QL-tuned Dijkstra | 20.56 | 40.46 | 20.31 | 1.48 | 23.65 | 68.97 | 0.52 | 385.29 |
| Best fixed-profile Dijkstra | 18.80 | 33.32 | 17.87 | 1.01 | 19.26 | 64.65 | 0.52 | 354.63 |

## Best fixed-profile Dijkstra vs. the other adaptive strategies (paired Wilcoxon, p < 0.05)

Cells = scenario × load (11 in total). 'wins' = Best fixed-profile Dijkstra is significantly better, 'losses' = significantly worse.

| Compared with | Metric | wins | ties | losses |
|---|---|---|---|---|
| Load-aware Dijkstra | Mean latency (ms) | 5 | 6 | 0 |
| Load-aware Dijkstra | 95th-percentile latency (ms) | 2 | 9 | 0 |
| Load-aware Dijkstra | Voice/video latency (ms) | 10 | 1 | 0 |
| Load-aware Dijkstra | Packet loss (%) | 2 | 9 | 0 |
| Load-aware Dijkstra | SLA violations (% of flows) | 10 | 1 | 0 |
| Load-aware Dijkstra | Jain's fairness of link load | 9 | 2 | 0 |
| Telemetry-aware Dijkstra | Mean latency (ms) | 6 | 5 | 0 |
| Telemetry-aware Dijkstra | 95th-percentile latency (ms) | 2 | 9 | 0 |
| Telemetry-aware Dijkstra | Voice/video latency (ms) | 11 | 0 | 0 |
| Telemetry-aware Dijkstra | Packet loss (%) | 0 | 11 | 0 |
| Telemetry-aware Dijkstra | SLA violations (% of flows) | 9 | 2 | 0 |
| Telemetry-aware Dijkstra | Jain's fairness of link load | 6 | 5 | 0 |
| Hybrid path-selection QL | Mean latency (ms) | 2 | 9 | 0 |
| Hybrid path-selection QL | 95th-percentile latency (ms) | 2 | 7 | 2 |
| Hybrid path-selection QL | Voice/video latency (ms) | 4 | 7 | 0 |
| Hybrid path-selection QL | Packet loss (%) | 3 | 8 | 0 |
| Hybrid path-selection QL | SLA violations (% of flows) | 2 | 8 | 1 |
| Hybrid path-selection QL | Jain's fairness of link load | 10 | 1 | 0 |
| Hybrid QL-tuned Dijkstra | Mean latency (ms) | 10 | 1 | 0 |
| Hybrid QL-tuned Dijkstra | 95th-percentile latency (ms) | 4 | 7 | 0 |
| Hybrid QL-tuned Dijkstra | Voice/video latency (ms) | 10 | 1 | 0 |
| Hybrid QL-tuned Dijkstra | Packet loss (%) | 3 | 8 | 0 |
| Hybrid QL-tuned Dijkstra | SLA violations (% of flows) | 11 | 0 | 0 |
| Hybrid QL-tuned Dijkstra | Jain's fairness of link load | 2 | 7 | 2 |
