## 1. Notes stay local

- [x] 1.1 Delete every step that stages, commits, takes back out or restores run notes, in both chains; no recipe line stages or commits a notes file (`test_run_notes_stay_local.py`, `requirement: run-ledgers / Chain run notes stay local`).
- [x] 1.2 A multi-lite resume merges only its recorded head; without notes it merges nothing (`test_run_notes_stay_local.py`, `test_multi_lite_policy_names_agree.py`, `requirement: small-change-chains / A resumed small-change chain merges only the head it checked`).
- [x] 1.3 `cla-init` item 8 appends the ignore line once, never changing other lines (`test_run_notes_stay_local.py`, `requirement: repo-context / Setting up a repo's cla.io directory`).

## 2. Gate

- [x] 2.1 Mutation batches over every touched guard, all killed; the full suite parallel and serial on one tree with matching counts; `openspec validate --specs --strict`.
