| Strategy | Mean latency (ms) | 95th-percentile latency (ms) | Voice/video latency (ms) | Packet loss (%) | SLA violations (% of flows) | Peak link utilization (%) | Jain's fairness of link load | Decision time per flow (µs) |
|---|---|---|---|---|---|---|---|---|
| Static Dijkstra | 32.71 | 91.72 | 31.68 | 12.89 | 29.18 | 90.17 | 0.35 | 7.85 |
| ECMP | 15.62 | 49.88 | 14.69 | 4.98 | 14.54 | 77.46 | 0.48 | 10.07 |
| Load-aware Dijkstra | 8.86 | 21.81 | 8.72 | 0.35 | 3.00 | 55.26 | 0.63 | 226.59 |
| Q-Routing (RL only) | 49.08 | 142.46 | 45.93 | 15.14 | 37.66 | 91.53 | 0.64 | 86.50 |
| Hybrid Dijkstra+QL (proposed) | 8.63 | 21.47 | 8.41 | 0.28 | 2.41 | 56.71 | 0.59 | 259.24 |
