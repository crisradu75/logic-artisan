# Proposal

Budget: protected

## Why

Four gaps in shipped `/cla:spec-to-pr` and `/cla:multi-pr` behaviour. Under `Full gate: final-commit-only`, a run whose prompt names `/cla:multi-pr` skips its full gate, but `/cla:multi-pr` merges only a change a later one needs. So an independent change gets no full gate at all. Base drift shows up only at merge, after review. One Implement delegate runs out of context on an 80-task change. A correction re-dispatch starts from zero. The owner decided Q1–Q3 in `cla.io/decisions/open-issues-2026-11-21.md` and Q6 in `cla.io/decisions/autocraft-adoptions-2026-11-21.md`.

## What Changes

- **Full gate (Q1).** Under `Full gate: final-commit-only`, spec-to-pr always runs its one full gate after Archive, and its report names the commit that run passed or failed on. The caller skip and multi-pr's "name the caller" sentence go. The chain's merge step reuses a green run on exactly the recorded head. Otherwise it runs its own gate, as today.
- **Base drift (Q2).** After Ship opens the PR and before Revise round 1, spec-to-pr fetches the PR's base. When files changed on the base since the branch point overlap the PR's files, it merges the base into the feature branch (never a rebase) and runs the touched area's tests. Revise then reviews the merged code. A resumed run's review-round count leaves out the base commits that merge brought in.
- **Implement split (Q3).** Above 40 subtasks, Implement dispatches one delegate per `tasks.md` group, in order. Each delegate's brief summarises what the earlier groups built. The unfinished-work recovery applies to each group.
- **Corrections (Q6).** Three kinds of correction continue the same agent when the host can message it, and fall back to a fresh dispatch when it cannot: an empty reviewer reply, an uncited enumeration, and an implementer's unfinished work. Review rounds after a fix use fresh reviewers. The rule is written once, in `_shared/references/subagent-brief.md`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `change-workflow`: seven ADDED requirements (gate, drift, round count, split, corrections).
- `change-chains`: one ADDED requirement (merge-step gate reuse).
- `review-agents`: one ADDED requirement (fresh later rounds).

## Impact

Shipped prose in `spec-to-pr` (SKILL.md, revise, implement-delegate, handoff, workflow-diagram), `multi-pr/references/change-loop.md`, `_shared/references/chain-merge.md` and `subagent-brief.md`. One edit to `probe_state.py`'s round counter, with a regression test. One existing consistency test is updated. No new script or hook. Depends on `lite-pr-red-gate-and-pr-notes` and `spec-size-and-review-tiers`. It modifies none of their requirements and shares no shipped file with them.

## Risks noted

- Drift that lands during Revise fix rounds or Archive is still found only at merge. The decisions accept this.
- A later group's delegate works from a summary of the earlier groups. The decisions accept this.
- A flat `tasks.md`, or one group holding most of the tasks, gets no benefit from the split.
- Continuing an agent saves cost by an amount nobody has measured.
- An interrupted drift merge leaves a merge in progress. The existing in-progress-op check catches it when the run resumes.

## Open questions

1. **Handoff moves the head after the gate.** Handoff commits and pushes `docs: TODO.md` and `chore: spec-to-pr run log` after the post-Archive gate. So the PR head never equals the gated commit, and the merge step always runs a second full gate. That is safe but wastes the saving Q1 counted on. **Recommend:** the merge step also reuses the run when every commit after it is one of that run's two Handoff commits, and those touch only `TODO.md` and the run log.
2. **The fetch does not protect the round count.** The probe counts `fix: review round N` subjects over the *local* base name (`main..branch`), and `git fetch` leaves that ref stale. Merged-in base commits can then inflate the count in a non-squash repo. **Recommend:** count against `origin/<base>` when it resolves (tasks 3.1–3.2).
3. **Red tests after the drift merge.** **Recommend:** Test turns ⚠, the report names the failing test, and the run does not loop to fix it.
4. **Drift when Revise is skipped.** **Recommend:** the check runs only when Revise round 1 runs, so no merge commit goes unreviewed.
5. **A continuation that fails.** **Recommend:** treat it as "host cannot message the agent": one fresh dispatch, never a third try.
