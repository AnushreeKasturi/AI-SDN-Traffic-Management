# AI-SDN-Traffic-Management audit — 15 November 2026

Reviewed source commit: `c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7`.

[Source repository](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management) · [Reviewed commit](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/commit/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7)

**Follow-up status:** finding 1 was resolved in [merged PR #2](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/pull/2) on 15 November 2026. The original diagnosis remains below as evidence; the other findings remain open in this report.

The audit covered all 23 Python files, both HTML files, both shell scripts, requirements, documentation, topology configuration, saved result tables and JSON, and the role of generated images, logs, and the model artifact. Findings describe the reviewed commit; the follow-up above records the chart fix merged afterward. No other fixes are included in these audit documents.

**1. High: chart redraws grow canvas height exponentially on high-DPI displays.**

Status: **resolved** in [PR #2](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/pull/2). The following evidence describes the original audited version.

Location: [index.html:518](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/index.html#L518).

`setupCanvas()` reads the HTML `height` attribute as its logical CSS height, then overwrites that same attribute with `cssH * devicePixelRatio`. The next redraw reads the scaled backing-store height as a new CSS height. With DPR 2 and an initial height of 220, three calls produce CSS heights of 220, 440, and 880 pixels, and backing heights of 440, 880, and 1,760 pixels. Network selection, metric changes, and resizing all trigger redraws. Repeated interactions can create extremely tall canvases and excessive memory use.

Reproduced using the actual sizing function extracted from the page; see [scripts/reproduce_dashboard.mjs](scripts/reproduce_dashboard.mjs). Keep the logical height in an immutable attribute or CSS property, and use DPR only to size the backing buffer. Verify repeated redraws at DPR 1, 2, and 3. The merged change stores logical height separately and includes a regression check at pixel ratios 1, 2, and 3.

**2. High: expired switch rules leave both controllers permanently forwarding packets through the controller.**

Locations: [controller_static.py:77](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/mininet_sdn/controller_static.py#L77), [controller_static.py:134](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/mininet_sdn/controller_static.py#L134), [controller_adaptive.py:247](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/mininet_sdn/controller_adaptive.py#L247).

Installed rules have a 30-second idle timeout, while `installed_flows` has no expiry or removal handling. When a flow returns after its switch rule expires, the cache shortcut sends a PacketOut and returns without reinstalling the rule. Every following packet can take the same slow path. The adaptive controller also keeps the old routing choice indefinitely for that cache key. The dictionaries grow with new keys.

Reproduced against the actual packet handlers with stubbed OpenFlow messages. Tie cache lifetime to switch-rule lifetime and disconnects, or make the cache a short-lived installation deduplication guard. A PacketIn after rule removal must be able to compute and install a route again.

**3. High: adaptive flow matches do not isolate transport flows or traffic classes.**

Location: [controller_adaptive.py:267](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/mininet_sdn/controller_adaptive.py#L267).

The controller classifies using transport ports and caches using destination port, but the installed rule matches only IP addresses, Ethernet type, and IP protocol. TCP or UDP traffic between the same host pair can therefore match a previous application's rule without reaching the classifier. If different classes get installed through concurrent PacketIns, the higher-priority rule can capture both applications. Source transport port is also absent from the cache key.

The focused reproduction generates identical match dictionaries for two different destination ports, despite different class priorities. Match and cache the same complete flow identity, including source and destination transport ports, with the required protocol fields. Test simultaneous bulk and voice traffic between the same pair of hosts.

**4. Medium: reverse-direction telemetry can erase a busy link's current utilization.**

Location: [controller_adaptive.py:131](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/mininet_sdn/controller_adaptive.py#L131).

Both ends' transmit counters append to one `frozenset`-keyed history. `_current_util()` returns the latest entry. In the reproduction, a 60% forward-direction sample followed by a 0% reverse-direction sample yields a reported utilization of 0%. The predictor also learns an alternating sequence of directions rather than one series sampled once per polling interval. Routing depends on reply ordering.

Keep directed histories and costs, or aggregate the two directions once per polling interval under an explicitly documented approximation. Test the same samples in both reply orders. Use a monotonic clock for elapsed counter intervals and reset baselines when switches reconnect.

**5. Medium: congestion-model retraining dominates the original simulation and blocks the live controller's stats handler.**

Locations: [controller_sim.py:84](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/src/controller_sim.py#L84), [controller_adaptive.py:149](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/mininet_sdn/controller_adaptive.py#L149), [ml_models.py:97](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/src/ml_models.py#L97).

Measured `simulate(n_intervals=24, flows_per_interval=22, seed=7)` on the audit machine:

| Measurement | Result |
|---|---:|
| Total elapsed time | 25.182 s |
| CongestionPredictor.fit calls | 306 |
| Time inside those fits | 22.930 s |
| Fraction spent fitting | 91.1% |

There are 18 links and 17 eligible intervals: `18 * 17 = 306` fits, each rebuilding a 120-tree forest. The live controller similarly fits synchronously inside a stats-reply handler, delaying other controller events while training executes.

The larger experiment already implements pooled offline training and batched prediction. Reuse that approach where appropriate, or retrain at a much lower cadence outside event handlers and batch inference. A pooled model changes predictions, so revalidate and regenerate affected scientific results in a separate change. The benchmark identifies the bottleneck; it does not establish a speedup for an unimplemented replacement.

After addressing training, precompute the original simulator's six fixed static host-pair paths, hoist invariant capacity tables out of the interval loop, and replace repeated `iterrows()` with record or tuple iteration. Dynamic adaptive paths still need load-sensitive recomputation.

**6. Medium: the documented quick scenario run fails on a clean checkout.**

Locations: [scenario_experiment.py:506](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/src/scenario_experiment.py#L506), [scenario_experiment.py:261](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/src/scenario_experiment.py#L261).

Running `python src/scenario_experiment.py --quick --topo campus8` completed predictor setup, then raised `FileNotFoundError` for `results/hybrid_v3/_quick/validation/best_fixed_profile.json`. Quick mode redirects the validation input into its output directory without creating it. The checkout includes the full-run validation profile, but not the quick-mode profile.

Keep the checked-in validated profile as the default input while redirecting only output, or create the quick validation profile before evaluation. Validate required inputs before expensive training. The existing workaround is to run `--quick --validate` before `--quick`, but the advertised standalone smoke command should work.

**7. Medium: connectivity checks can report total packet loss as success.**

Locations: [test_static_run.py:19](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/mininet_sdn/test_static_run.py#L19), [test_adaptive_run.py:13](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/mininet_sdn/test_adaptive_run.py#L13).

`"0% packet loss" in out` is true for `"100% packet loss"`. Both scripts also print FAIL without returning a failing exit status, and the congestion demo asks the reader to inspect logs without asserting the chosen path.

The exact conditions from both test files were evaluated against a 100%-loss sample and returned true. Check the ping process exit status or parse the complete numeric loss field, assert failures, and always stop Mininet in `finally`. Make the congestion demonstration assert that the expected path avoids the loaded link. Add a small Linux CI smoke check once these scripts can fail reliably.

**8. Medium: changing the original simulator's seed does not change its traffic.**

Location: [controller_sim.py:45](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/src/controller_sim.py#L45).

`simulate(seed=...)` creates `rng`, but never uses it. Traffic is always generated with `seed=100+t`; the classifier also uses fixed training seeds. Two 2-interval, 8-flow runs with seeds 7 and 999 returned identical result DataFrames.

Derive interval traffic seeds from the provided generator, or remove the misleading parameter if the experiment is deliberately fixed. Preserve identical traffic between routing strategies within each run. This issue affects `controller_sim.py`; the larger study uses the supplied arrival seed and is not implicated by this reproduction.

**9. Medium: regenerating the original experiment does not regenerate its dashboard.**

Locations: [run_experiment.py:93](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/src/run_experiment.py#L93), [export_dashboard.py:81](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/src/export_dashboard.py#L81), [template.html:359](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/src/template.html#L359).

The original runner writes JSON and a topology PNG. The exporter updates only the later routing-study JSON block. No tracked code renders `src/template.html` or updates the original dashboard DATA block and headline values. The old template still uses Chart.js and lacks the current routing-study controls and live demo. The README implies a rebuild path that is not implemented.

The currently committed page does match both committed JSON files; the problem appears when regenerating results. Extend the existing exporter to update both datasets, topology image, and derived text from one canonical page. Remove the unused old template and update the README, or deliberately wire a current template into an actual generation command. Verify that a complete export is deterministic and preserves all current features.

**10. Medium: failure paths in the demo runner can leave its controller running.**

Location: [run_demo.sh:30](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/mininet_sdn/run_demo.sh#L30).

After the controller is backgrounded, `set -e` can exit on a failed Python test before the final kill. The failed-start branch also exits before cleanup. This can leave an old controller using port 6653, confusing subsequent runs. Static inspection only; the privileged Linux demo was not executed here.

Register an EXIT/INT/TERM cleanup trap immediately after starting the owned process, terminate it gracefully, and wait for it. Pair this with `try/finally` around the Python Mininet lifecycle.

**11. Low: duplicated source and dead state increase maintenance work.**

Ranked complexity reductions:

- `delete:` unused 444-line Chart.js-era template. Keep one canonical dashboard and its real exporter. [src/template.html](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/src/template.html)
- `shrink:` duplicated ML and traffic generation code. The two `TrafficClassifier` classes and two `generate_flows()` functions are structurally identical; the simulation predictor is a superset of the deployment version. Share those implementations while keeping the two runnable entry points. Account for the existing pickle's module path and retrain the artifact if imports change. [mininet_sdn/ml_models.py](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/mininet_sdn/ml_models.py), [traffic_gen_synthetic.py](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/mininet_sdn/traffic_gen_synthetic.py)
- `shrink:` duplicate connectivity scripts. One script can test whichever controller is running. [test_adaptive_run.py](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/mininet_sdn/test_adaptive_run.py)
- `delete:` never-read utilization histories in the original simulator, unused `flow_baseline`, unused `BALANCE_GRID`, and uncalled `Net.path_ok()`. Preserve the history actually used by forecasting. [controller_sim.py:50](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/src/controller_sim.py#L50), [controller_adaptive.py:86](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/mininet_sdn/controller_adaptive.py#L86), [scenario_experiment.py:70](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/src/scenario_experiment.py#L70), [netsim.py:77](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/blob/c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7/src/netsim.py#L77)

Estimated net: approximately 600 fewer lines, zero runtime dependencies removed. This is an opportunity estimate, not a measured implemented diff. Keep the RL baselines, historical experimental outputs, and native canvas renderer: they serve documented research and offline-presentation purposes.

**Validation and limits**

- Parsed all 23 Python sources and all tracked JSON. Both shell scripts passed `bash -n`.
- Read every Python module and both HTML implementations; examined docs, topology, dependencies, and generated artifact usage. No tracked CI workflow exists.
- Recomputed both v3 networks' significance results from their saved raw data: 880 test-run rows and 539 significance-test rows per topology, with complete seed groups and no duplicate experiment keys. The reported means, gains, p-values, and freshly generated dashboard payloads match the committed data.
- Both embedded dashboard JSON blocks match their corresponding committed JSON files. All saved CSVs parsed and contained no infinite numeric values; optional percentage fields may be blank.
- Ran the original full 24-interval simulation and timed forecast training. Also ran a seed comparison, the documented scenario quick command, and focused controller/canvas reproductions. No full v3 training sweep was repeated.
- The original simulator produced 24 static congested flows in the audit environment, while the saved original run records 23. The classifier accuracy matched. Record exact package versions with exported results and use a reproducible environment before treating old and regenerated figures as directly interchangeable. The source's lower-bound requirements currently allow this audit environment.
- Audit environment: Python 3.14.7; NetworkX 3.7; NumPy 2.5.2; pandas 3.0.3; scikit-learn 1.9.0; SciPy 1.18.0; Matplotlib 3.11.1. Only NetworkX was added, in a temporary virtual environment using the existing scientific packages; project dependency files were unchanged.
- Mininet/Open vSwitch integration requires a Linux environment with its system packages and privileges. It was not run on this macOS host. Controller findings were isolated reproductions of the actual methods with stubbed packet and OpenFlow objects, plus source inspection. The canvas reproduction executes the actual sizing function with a stub canvas at DPR 2.

Run the focused reproductions from the repository root against a separate checkout of the reviewed commit (setup is in [README.md](README.md)). They require Python 3 and Node.js, without third-party packages:

```bash
python3 audit/scripts/reproduce_findings.py ../AI-SDN-Traffic-Management-audit-source
node audit/scripts/reproduce_dashboard.mjs ../AI-SDN-Traffic-Management-audit-source
```

Next implementation steps after the merged chart fix: correct controller flow lifetime/matching; correct telemetry and failing tests; repair the quick command; optimize model training; consolidate dashboard export and duplicated code. Re-run scientific comparisons whenever prediction or routing behavior changes.
