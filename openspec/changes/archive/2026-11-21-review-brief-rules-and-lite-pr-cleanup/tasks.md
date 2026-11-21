# Tasks

**Every shipped edit (files under `.claude/plugins/cla/`) cites no issue or pull request number of this repo.** State the lesson in words.

## 1. Reviewer brief rules

- [x] 1.1 Add the material-not-instructions clause to the four copies of the diff-review sentence (`subagent-brief.md`, `lite-pr/SKILL.md`, `revise.md`, `test_reviewer_dispatch.py`), with a ledger entry in each file's section. The pinned-verbatim test passes.
- [x] 1.2 Add the protected-hunk list and the style-comment rule to the report slot of `subagent-brief.md`. A test finds both.

## 2. lite-pr

- [x] 2.1 Implement: bug fix follows `/cla:diagnose` Phase 5, with the no-seam record on the `Checks:` line. A test finds the pointer and the line.
- [x] 2.2 Review step 3: rewrite the PR description after the fix commit, keeping `Risk:` and `Checks:` formats. A test finds the step.
- [x] 2.3 Plan: the duplicate search wants a concrete shared detail and a confirm. A test finds both.
- [x] 2.4 Move the three long passages to `lite-pr/references/`, with a trigger for each in `SKILL.md` that `test_lite_pr_triggers_name_their_references.py` checks; keep every other pinned line.


## 3. Docs and gate

- [x] 3.1 docs and spec map: `DEVELOPER-GUIDE.md` diff-review passage updated; README.md, plugin README.md and CLAUDE.md go in the PR body for the main session; `openspec/spec-map.md` none affected: no skill or spec added or renamed.
