## 1. One shared merge file

- [x] 1.1 Write `skills/_shared/references/chain-merge.md` from `multi-lite`'s merge steps, with `multi-pr`'s worktree and follow-up-fix cases; point both skills at it and delete their copies (`test_chain_merge_shared.py`, `test_multi_lite_policy_names_agree.py`).
- [x] 1.2 `multi-pr` records each PR's head, merges only through the shared checks with `--match-head-commit`, and halts when a needed merge cannot happen (`test_chain_merge_shared.py`, `requirement: change-chains / An OpenSpec change chain merges only a later change's prerequisite, on the head it checked`).

## 2. Delete multi-pr's stacked and open-all policies

- [x] 2.1 Remove the policies from `multi-pr`'s skill, references, README row, DEVELOPER-GUIDE §6 and `spec-to-pr`'s `--pr-base` attribution (`test_chain_merge_shared.py`).

## 3. Gate

- [x] 3.1 Mutation batches over every touched file, all killed; the full suite parallel and serial on one tree with matching counts; `openspec validate --specs --strict`.
