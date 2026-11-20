# Tasks

Settle the proposal's `## Open questions` with the owner before group 1. Tasks 1.2, 1.4, 2.1, 2.2, 3.1 and 5.1 follow the recommended answers unless the owner picks otherwise.

**Shipped edits.** These files are under `.claude/plugins/cla/`: `spec-to-pr/SKILL.md`, and in `spec-to-pr/references/` the files `revise.md`, `implement-delegate.md`, `handoff.md` and `workflow-diagram.md`, plus `spec-to-pr/scripts/probe_state.py`, `multi-pr/references/change-loop.md`, and in `_shared/references/` the files `chain-merge.md` and `subagent-brief.md`. **None of them may cite an issue or pull request number of this repo.** State the lesson in words. Check (e) of `check_no_project_tokens.py` fails on a `#NNN`.

## 1. One full gate per run (Q1)

- [ ] 1.1 `spec-to-pr/SKILL.md`, the `Full gate: final-commit-only` paragraph: delete the "Skip that run when the invocation names `/cla:multi-pr` as its caller" sentence. Say that the run always happens and that Handoff names the commit it ran on. A grep for "as its caller" in shipped files finds nothing.
- [ ] 1.2 `handoff.md`: the Test row carries `full gate: green|red on <sha>` when the post-Archive run happened, per design decision 1. Leave the merge-line gating unchanged.
- [ ] 1.3 `change-loop.md` step 4: delete "Name `/cla:multi-pr` as the caller …". Step 3: after the call returns, read the full-gate line from the report. A grep for "as the caller" in `multi-pr/` finds nothing.
- [ ] 1.4 `chain-merge.md` "Pre-merge checks" step 3: replace "this is the run `/cla:spec-to-pr` skipped …". The step reuses a green run when the report's commit equals `head_sha` in this session. A red run on `head_sha` means do not merge and do not re-run. Every other case gets its own gate.
- [ ] 1.5 Update `plugin-tests/tests/consistency/test_full_gate_final_commit_only.py`. Drop the "names `/cla:multi-pr` as its caller" expectation. Replace the caller test with one that asserts neither caller sentence remains and that the paragraph names the commit. Add a `requirement:` line for each of the two Q1 requirements. Then run the consistency area.

requirement markers in 1.5: `change-workflow / One full gate on every run, naming its commit` and `change-chains / A chain merge reuses the change's own full gate only on the head it ran on`.

## 2. Base drift before review (Q2)

- [ ] 2.1 `revise.md`: add a first section, "Before round 1: base drift", per design decision 2. It fetches, intersects the two file lists, merges only on overlap, runs the touched tests, pushes and checks the push. A red test is a Test ⚠ naming the test, with no fix loop.
- [ ] 2.2 In the same section: only a merge, never a rebase or force-push, and writes go only to `<branch>`. A conflict goes through `conflict-resolution.md`, with the sides named first. The report names each conflicted file. A failed fetch or compare reports "base drift not checked" and merges nothing.
- [ ] 2.3 `SKILL.md` Revise stub: one sentence pointing at the new section. `workflow-diagram.md` REVISE box: one line for the drift merge. The phase order line is unchanged.

manual: change-workflow / Base changes that overlap the pull request are merged in before review: a model follows skill prose against a live remote. Checked in a scratch repo whose base gains an overlapping commit after Ship, and once with a non-overlapping one.
manual: change-workflow / The drift merge keeps history and stays on the run's own branch: checked in the same scratch repo with a conflicting base commit, comparing every other branch's head before and after, and reading the report.
manual: change-workflow / A base that could not be read is never reported as unchanged: checked by one scratch run whose `origin` points at an unreachable path when Revise starts.

## 3. Review-round count (Q2, decisions' resume note)

- [ ] 3.1 In `probe_state.py`, `_fix_rounds_applied` ranges over `origin/<base>..<branch>` when that ref resolves, and falls back to the local name otherwise (design decision 3). Edit no other range or field.
- [ ] 3.2 In `test_probe_state.py`, add a regression test where a stale local `main` sits behind `origin/main`, whose `fix: review round 1` commit is merged into the branch. The count is 0, and a branch-own round still counts 1. The test fails on the pre-edit code. Run the spec-to-pr area.
- [ ] 3.3 Real-file check: run `probe_state.py` read-only on a change in this repo before and after 3.1, and confirm its JSON is identical. measured:

requirement marker in 3.2: `change-workflow / Merged-in base commits are not counted as review rounds`.

## 4. Implement split (Q3)

- [ ] 4.1 `implement-delegate.md`: add a subsection per design decision 4. Above 40 subtasks there is one delegate per `## N.` group, in order. Each brief enumerates its own group, marks the other groups held, and carries a summary of the earlier groups. The miss handling runs before the next dispatch.
- [ ] 4.2 `SKILL.md` Implement step 3: one clause naming the over-40 split and pointing at 4.1's subsection. A resume restarts at the first group with an unticked task.

manual: change-workflow / A large change is implemented one task group at a time: delegate sequencing is model behaviour. Checked by one run on a scratch change with 45 subtasks in three groups, interrupted after group 2 and resumed.

## 5. Corrections continue the agent (Q6)

- [ ] 5.1 In `subagent-brief.md`, add a section, "Correcting a reply", per design decision 5: continue with the gap named, use a fresh full-brief dispatch when the host cannot message the agent or the call errors, keep each case's attempt limit, and never continue an agent into a later review round.
- [ ] 5.2 Add one pointer sentence each to: `revise.md` "Round 1 always happens" (a reviewer returned nothing), `revise.md` step 1 (uncited enumeration), and `implement-delegate.md` (unfinished-work re-dispatch). A grep shows the rule's wording only in `subagent-brief.md`.
- [ ] 5.3 `revise.md` "Round N": one clause saying its reviewers are new dispatches.

manual: change-workflow / A correction continues the same agent: whether the host offers agent messaging varies by session. Checked by one Revise run with a reviewer forced to return nothing, with messaging available and once without it.
manual: review-agents / A review round after a fix uses fresh reviewers: checked in the same run's round 2 by confirming that every reviewer call is a new dispatch.

## 6. Ledger, changelog, gate, docs

- [ ] 6.1 Run `python3 .claude/plugins/cla/skills/_shared/scripts/check_no_project_tokens.py`. It exits 0.
- [ ] 6.2 Add a `docs/rule-ledger.md` line for each new shipped `never`, `always` or `must` (the deleted caller-skip sentence has no entry). Use `keep` only for the drift merge's no-rebase and own-branch rules (`user's files`) and "never reported as unchanged" (`honesty`). Everything else is guidance. `test_rule_ledger.py` passes.
- [ ] 6.3 Append a `CHANGELOG.md` `[Unreleased]` bullet for this patch below the siblings' bullets, leaving theirs unchanged. Edit no version and not the "Current release" line.
- [ ] 6.4 Run `pytest plugin-tests -q -n 4 --dist loadfile` and `openspec validate --specs --strict` once each, on the final commit. Both pass.
- [ ] 6.5 docs and spec map: grep `DEVELOPER-GUIDE.md` §5–§6, root `CLAUDE.md`, `README.md`, the plugin `README.md` phase table, `docs/` and `cla-setup/references/facts-file.md` for the caller skip, the single delegate and the merge-time-only drift, and update each hit. `openspec/spec-map.md` none affected: no workflow step or spec link changes.
