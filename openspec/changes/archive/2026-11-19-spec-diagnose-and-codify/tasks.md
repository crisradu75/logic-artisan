# Tasks

## 1. Specs

- [x] 1.1 Add `failure-diagnosis` and `session-learnings`. `openspec validate --specs --strict` passes after archive.

## 2. Tests

- [x] 2.1 Test each `failure-diagnosis` requirement: the skill text carries the loop-first stop, the mode rule and written hypotheses, the test-before-fix order with the no-seam finding, the clean-up grep, and the cause-naming commit.
- [x] 2.2 Test each `session-learnings` requirement: the whole-session scan, the three-fix cap with quoted failures, tools before docs, the one-rung escalation, the single prompt before any write, upstream routing when read-only, and the log entry with its archive rule.
- [x] 2.3 Regression test for the debug-tag mismatch: `/cla:diagnose` and the ship reference both name the guard hook that holds the same tag.

## 3. Docs

- [x] 3.1 docs and spec map: `openspec/spec-map.md` (both specs linked from a workflow step), `docs/rule-ledger.md` (the reworded tag lines); `CHANGELOG.md`, `README.md`, `DEVELOPER-GUIDE.md` and `.claude/plugins/cla/README.md` left to the orchestrator's PR.
