# Tasks

The owner settled open question 1: the chain merge also reuses the run across Handoff's two later commits (design decision 1). Settle the proposal's remaining `## Open questions` before group 1; tasks 2.1, 2.2, 3.1 and 5.1 follow their recommended answers unless the owner picks otherwise.

**Order.** This change is third in its batch, after `lite-pr-red-gate-and-pr-notes` and `spec-size-and-review-tiers`. It shares no shipped file with them; the dependency is an ordering one for `CHANGELOG.md`, `docs/rule-ledger.md` and the docs sweep.

**Shipped edits.** These files are under `.claude/plugins/cla/`: `spec-to-pr/SKILL.md`, and in `spec-to-pr/references/` the files `revise.md`, `implement-delegate.md`, `handoff.md` and `workflow-diagram.md`, plus `spec-to-pr/scripts/probe_state.py`, `multi-pr/references/change-loop.md`, and in `_shared/references/` the files `chain-merge.md` and `subagent-brief.md`. **None of them may cite an issue or pull request number of this repo**; state the lesson in words. `check_no_project_tokens.py` check (e) catches only "issue/PR/pull request #N" and this repo's GitHub URLs, so task 6.1 also greps for a bare `#N`.

## 1. One full gate per run (Q1)

- [x] 1.1 `spec-to-pr/SKILL.md`, the `Full gate: final-commit-only` paragraph: delete the caller-skip sentence; say the run happens whenever a source-affecting path changed, and Handoff names its commit. A grep for "as its caller" in shipped files finds nothing.
- [x] 1.2 `SKILL.md` "Resume / dry-run": a resume that reaches Handoff under `Full gate: final-commit-only` with no run-log commit on the branch runs the full gate first, or Handoff's Test row says it did not run and why.
- [x] 1.3 `handoff.md` Test row: `full gate: green|red on <sha>` when the post-Archive run happened, else `full gate: skipped (<reason>)`, per design decision 1. Leave the merge-line gating unchanged.
- [x] 1.4 `change-loop.md`: in step 4 delete "Name `/cla:multi-pr` as the caller …"; in step 3, after the call returns, read the full-gate line before "Record the head". A grep for "as the caller" in `multi-pr/` finds nothing.
- [x] 1.5 `chain-merge.md` "Pre-merge checks" step 3: reuse a same-session green run on `head_sha`, or on a commit followed only by that run's two Handoff commits changing only `TODO.md` and the run log (design decision 1).
- [x] 1.6 Same step: the allowance is void when a gate command may read `TODO.md` (unknown means run); a red reused run is neither merged nor re-run; every other case runs the gate. Delete "this is the run `/cla:spec-to-pr` skipped".
- [x] 1.7 Update `plugin-tests/tests/consistency/test_full_gate_final_commit_only.py`: drop the caller expectation; assert neither caller sentence remains, the paragraph names the commit, and "Resume / dry-run" runs or reports the gate.
- [x] 1.8 Same file, a test asserting `chain-merge.md` step 3: reuse only on the gated commit or the two Handoff commits touching only `TODO.md` and the run log; red is neither merged nor re-run; no "the run `/cla:spec-to-pr` skipped" left. Run the consistency area.

requirement markers: 1.7 carries `change-workflow / One full gate on every run, naming its commit`; 1.8 carries `change-chains / An OpenSpec change chain merges only a later change's prerequisite, on the head it checked`.

## 2. Base drift before review (Q2)

Edit order for `revise.md`: write 2.1–2.3 first, then group 5's pointer sentences.

- [x] 2.1 `revise.md`, new first section "Before round 1: base drift" (design decision 2), detection: it runs only when round 1 runs; fetch, the two file lists and their intersection. A failed fetch or compare reports "base drift not checked" and merges nothing.
- [x] 2.2 Same section, the merge: on overlap, merge `origin/<pr-base>`, run the touched tests, push, check it with `ship_check.py pushed`. A red test is a Test ⚠ naming it, no fix loop. A refused or failed merge is aborted and reported not merged.
- [x] 2.3 Same section, safety: only a merge, never a rebase or force-push; writes only to `<branch>`. A conflict goes through `conflict-resolution.md` with the sides named first, and the report names each conflicted file.
- [x] 2.4 `SKILL.md` Revise stub: one sentence pointing at the new section; a skipped Revise makes Handoff say base drift was not checked. `workflow-diagram.md` REVISE box: one line for the drift merge. The phase order line is unchanged.

manual: change-workflow / Base changes that overlap the pull request are merged in before review: a model follows skill prose against a live remote. Checked in a scratch repo whose base gains an overlapping commit after Ship, and once with a non-overlapping one.
manual: change-workflow / No base-drift merge lands without review: checked by one scratch run with `--pr-rounds 0` after an overlapping base commit, confirming no fetch-driven merge and the report line.
manual: change-workflow / The drift merge keeps history and stays on the run's own branch: checked in the same scratch repo with a conflicting base commit, comparing every local and remote branch head before and after, and reading the report.
manual: change-workflow / A base that could not be checked or merged is never reported as clean: checked by one scratch run whose `origin` is unreachable when Revise starts, and one with an untracked file the merge would overwrite.

## 3. Review-round count (Q2, decisions' resume note)

- [x] 3.1 In `probe_state.py`, `_fix_rounds_applied` ranges over `origin/<base>..<branch>` when that ref resolves, else the local name (design decision 3). Edit no other range or field; stacked runs are out of scope.
- [x] 3.2 In `test_probe_state.py`, a regression test: a stale local `main` behind `origin/main`, whose `fix: review round 1` commit is merged into the branch, counts 0; a branch-own round still counts 1. It fails on the pre-edit code. Run the spec-to-pr area.
- [x] 3.3 Real-file check: run `probe_state.py` read-only on a change in this repo before and after 3.1, and confirm its JSON is identical. measured: identical stdout JSON on 3 changes (see below).

measured: `probe_state.py` run read-only from the worktree on `chain-gate-drift-and-delegates`, `lite-pr-red-gate-and-pr-notes` and `spec-size-and-review-tiers`, the HEAD copy (`git show HEAD:<path>`, in a scratch dir with `_git_common.py`) against the edited one: stdout JSON identical for all three (stderr differs only in naming `origin/main` instead of `main` in a failed-range note for the change with no branch). 3.2: with the 3.1 edit reverted, `test_fix_rounds_ignores_a_review_round_merged_in_from_a_stale_local_base` fails; restored, `test_probe_state.py` 57 passed.

requirement marker in 3.2: `change-workflow / Merged-in base commits are not counted as review rounds`.

## 4. Implement split (Q3)

- [x] 4.1 `implement-delegate.md`, new subsection (design decision 4), dispatch and order: above 40 subtasks with two or more `## N.` groups, one delegate per group in order; miss handling precedes the next dispatch, sent in the same message. A flat `tasks.md` keeps one delegate.
- [x] 4.2 Same subsection, brief contents: each brief enumerates its own group, marks other groups `held by orchestrator`, and carries a summary of at most about 150 words of earlier groups, built from earlier returns, ticked boxes and `git diff --stat`.
- [x] 4.3 `SKILL.md` Implement step 3: one clause naming the over-40 split, pointing at 4.1's subsection. A resume restarts at the first group with an unticked task.

manual: change-workflow / A large change's build is never left half-done by one helper running out of context: delegate sequencing is model behaviour. Checked by one run on a scratch change with 45 subtasks in three groups, interrupted after group 2 and resumed, and one with a flat 45-subtask list.

## 5. Corrections continue the agent (Q6)

- [x] 5.1 `subagent-brief.md`, new section "Correcting a reply" (design decision 5): continue the agent only after a non-empty report with a named gap; an empty return or exhausted context gets one fresh scoped dispatch; a failed continuation, one fresh dispatch, never a third.
- [x] 5.2 One pointer sentence each in `revise.md` "Round 1 always happens" (a reviewer returned nothing), `revise.md` step 1 (uncited enumeration) and `implement-delegate.md` (unfinished-work re-dispatch). A grep finds the rule's wording only in `subagent-brief.md`.
- [x] 5.3 `revise.md` "Round N": one clause saying its reviewers are new dispatches, never continued agents.

## 6. Ledger, changelog, pull request, docs

- [x] 6.1 Run `python3 .claude/plugins/cla/skills/_shared/scripts/check_no_project_tokens.py`; it exits 0. Run `git diff <base>...HEAD -- .claude/plugins/cla | grep -nE '#[0-9]'` over the changed shipped files; it finds no hit.
- [x] 6.2 Append a `docs/rule-ledger.md` line below the siblings' lines for each new shipped `never`, `always` or `must`. `keep` only for the drift merge's no-rebase and own-branch rules (`user's files`) and "never reported as clean" (`honesty`); the rest are guidance. `test_rule_ledger.py` passes.
- [x] 6.3 Append a `CHANGELOG.md` `[Unreleased]` bullet for this patch below both siblings' bullets, leaving theirs unchanged. Edit no version and not the "Current release" line.
- [ ] 6.4 The implementation PR body carries `Closes #568`, `Closes #569` and `Closes #570`, written to a file and passed with `--body-file`.
- [ ] 6.5 Post one comment on #569: declined are a checkpoint hand-off and a one-worker-per-change mode; already covered are a coordinator waiting for its own background jobs (`spec-to-pr/SKILL.md`'s turn-ending rule, `subagent-brief.md`); the Implement split by task group is this change's fix.
- [ ] 6.6 (docs sweep done: no hit for "as its caller", "ONE coding" (SKILL.md and implement-delegate.md reworded) or a stale "base moved" in DEVELOPER-GUIDE.md, root CLAUDE.md, both README.md, docs/ or facts-file.md; final gate left to the orchestrator) docs and spec map: `DEVELOPER-GUIDE.md` §5–§6, root `CLAUDE.md`, both `README.md` files, `docs/` and `cla-setup/references/facts-file.md`, updating each hit for "as its caller", "ONE coding" and "base moved"; `openspec/spec-map.md` none affected: no step or link changes. Then run the final gate once on the final commit (`pytest plugin-tests -q -n 4 --dist loadfile`, `openspec validate --specs --strict`).
