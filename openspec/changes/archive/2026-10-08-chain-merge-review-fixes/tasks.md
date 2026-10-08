## 1. Skills

- [x] 1.1 `multi-pr` merges a resumed change only from `status: enforced`, compares a resumed head before re-running `spec-to-pr`, records the head after every `spec-to-pr` call, and states the outcome of a failed commit check (`test_chain_merge_shared.py`, `requirement: change-chains / Running a batch of OpenSpec changes in dependency order`).
- [x] 1.2 `multi-pr`'s running-notes row and final report; `chain-merge.md`'s dropped rules restored; stack landing moved to `spec-to-pr`'s `branch-and-pr-base.md` (`test_chain_merge_shared.py`).

## 2. Gate

- [x] 2.1 Mutation batches over every touched file, all killed; the full suite parallel and serial on one tree with matching counts; `openspec validate --specs --strict`.
