## 1. Restore notes from the run's own write

- [x] 1.1 Both chains restore notes from the commit that added them; `multi-lite` takes no head from notes edited on the PR since; the head check needs a recorded head and fails closed (`test_run_records_ride_the_work_pr.py`, `requirement: small-change-chains / A resumed small-change chain merges only commits it checked`).
- [x] 1.2 `multi-pr` takes back out only its own chain's notes; a failed pull or a PR no longer open pushes nothing (`test_run_records_ride_the_work_pr.py`, `requirement: run-ledgers / Chain run notes ride the last open pull request`).

## 2. Gate

- [x] 2.1 Mutation batch over every touched recipe, all killed; the full suite parallel and serial on one tree with matching counts; `openspec validate --specs --strict`.
