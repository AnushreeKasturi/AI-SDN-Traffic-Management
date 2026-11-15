# Audit

The [repository audit](AUDIT.md) covers correctness, performance,
reproducibility, and maintenance opportunities in this project. It contains
11 findings, measured evidence, verification limits, and suggested fixes.
Source links are pinned to the reviewed commit so their line numbers remain useful.

Finding 1, high-DPI chart growth, was fixed in [merged PR #2](https://github.com/AnushreeKasturi/AI-SDN-Traffic-Management/pull/2).
The report retains the original diagnosis and marks it resolved. The other
findings remain open in the report.

## Reproduce the original findings

The focused scripts use only Python 3 and Node.js built-in modules. They do
not install packages, start Mininet, or modify the source checkout they inspect.

Run these commands from the project root. The separate worktree preserves
your current code and gives the scripts the historical version being audited:

```bash
git worktree add --detach ../AI-SDN-Traffic-Management-audit-source c208eb3b69b7028ca79ebf2ad0993c2f27d1e2c7
python3 audit/scripts/reproduce_findings.py ../AI-SDN-Traffic-Management-audit-source
node audit/scripts/reproduce_dashboard.mjs ../AI-SDN-Traffic-Management-audit-source
```

- `reproduce_findings.py` confirms the original controller-cache, flow-match,
  directional-telemetry, and ping-check bugs using extracted source methods
  and stubbed OpenFlow objects. A successful exit means the historical bugs
  were reproduced; it is not a general health check.
- `reproduce_dashboard.mjs` runs the target page's canvas-sizing function.
  It reports `BUG REPRODUCED` for the original version and `FIX VERIFIED`
  for the corrected version from PR #2.

To verify the chart fix in the current checkout, run:

```bash
node audit/scripts/reproduce_dashboard.mjs .
```

Real Mininet and Open vSwitch integration still needs verification on Linux.
