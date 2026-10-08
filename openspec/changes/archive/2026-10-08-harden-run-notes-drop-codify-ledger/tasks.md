## 1. Run notes on the PR

- [x] 1.1 One notes commit message per chain, only the run's own notes file added, the PR state re-read after the pull, no push once it merged (`test_run_records_ride_the_work_pr.py`, `requirement: run-ledgers / Chain run notes ride the last open pull request`).
- [x] 1.2 The resume head check needs the rename-blind diff to name only the run's notes file and every subject since to be the notes message (`test_run_records_ride_the_work_pr.py`, `requirement: small-change-chains / A resumed small-change chain merges only checked commits`).
- [x] 1.3 spec-to-pr's record commit is unchanged and re-pinned (`test_run_records_ride_the_work_pr.py`, `requirement: run-ledgers / The spec-to-pr run record rides its pull request`).

## 2. Drop the codify ledger line

- [x] 2.1 `codify-learnings` Step 5 keeps only the lessons-log entry; `log_run.py` accepts only the spec-to-pr ledger (`test_log_run.py`, `requirement: run-ledgers / Only checked spec-to-pr run records are written`).
- [x] 2.2 `cla-init` seeds only `spec-to-pr-runs.jsonl` and lists `codify-runs.jsonl` as retired (`test_cla_init_retired_ledgers.py`, `requirement: repo-context / Reporting retired ledgers`).

## 3. Gate

- [x] 3.1 Mutation batches over every touched guard, all killed; the full suite parallel and serial on one tree with matching counts; `openspec validate --specs --strict`.
