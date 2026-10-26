# Tasks

## 1. Remove the agents

- [x] 1.1 Delete the three reviewer agents and their three Copilot copies. Done when `agents/` holds only `doc-sweeper` and `fact-gatherer`, and the Copilot agreement and sync tests pass for those two.
- [x] 1.2 Drop the reviewer cases from the agent-definition conformance test and its mutation batch, and delete the sizing-names test and batch. Done when the remaining conformance tests pass for the two helpers.

## 2. Dispatch wiring

- [x] 2.1 Every reviewer dispatch in `lite-pr`, `revise.md` and `model-routing.md` uses `pr-review-toolkit:<name>` and passes `model:`. Done when a grep for `cla:` plus a reviewer name in shipped files finds nothing.
- [x] 2.2 Put the diff-review rule verbatim in `subagent-brief.md`, `lite-pr` Review and `revise.md`. Done when the consistency test finds it, with every forbidden verb, at all three sites. Test: `test_reviewer_dispatch.py`, carrying `requirement: review-agents / A reviewer is dispatched with a diff file, a ban on state changes and a named model`.
- [x] 2.3 Break each site by hand once (drop a verb, restore a `cla:` name, drop the model phrase). Done when the test fails each time, then restore.

## 3. Check the unchanged parts

- [x] 3.1 Confirm the run-log ledger keys stay bare and `run_ledgers` and the aggregation are untouched. Done when `git diff` shows only a comment change in `log_run.py` and the ledger tests pass.

## 4. Gate

- [x] 4.1 Run the full suite and `openspec validate --specs --strict` once each on the final commit. Done when both pass and the debris check is clean. measured: 2747 passed, 8 skipped (-n 2 --dist loadfile); validate 12 passed

## 5. Docs

- [x] 5.1 docs and spec map: README.md, DEVELOPER-GUIDE.md, .claude/plugins/cla/README.md, `openspec/specs/review-agents/spec.md` Purpose (after archive); `openspec/spec-map.md` (link text for review-agents); none affected: CLAUDE.md (names no reviewer).
