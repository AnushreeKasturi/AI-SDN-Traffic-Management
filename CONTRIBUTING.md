# Contributing

Thank you for helping improve Flowstate.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make test
```

## Ground rules

- **Keep comparisons fair.** Every strategy must see the same arrivals and
  ML predictions. Tune only on validation seeds and report on test seeds.
- **Commit the evidence.** If a change moves a number in the README or the
  dashboard, commit the regenerated `results/` files in the same PR. For the
  routing study, run `make export` so that `index.html` stays in sync. The
  dashboard tests fail if it is out of sync.
- **Report negative results.** If a new strategy does not win, say so.
- **Keep the dashboard self-contained.** `index.html` must work when opened
  as a local file, with no build step and no server.

## Pull requests

1. Branch from `main`.
2. Run `make test` before you push. CI runs the same checks.
3. Say in the PR description which numbers changed, and why.
