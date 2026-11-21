# Proposal

Budget: protected

## Why

Four gaps in shipped `/cla:spec-to-pr` and `/cla:multi-pr` behaviour. Under `Full gate: final-commit-only`, a run whose prompt names `/cla:multi-pr` skips its full gate, but `/cla:multi-pr` merges only a change a later one needs, so an independent change gets no full gate. Base drift shows up only at merge, after review. One Implement delegate runs out of context on an 80-task change. A correction re-dispatch starts from zero. The owner decided Q1–Q3 in `cla.io/decisions/open-issues-2026-11-21.md` and Q6 in `cla.io/decisions/autocraft-adoptions-2026-11-21.md`.

## What Changes

- **Full gate (Q1).** Under `Full gate: final-commit-only`, spec-to-pr runs its one full gate after Archive whenever source changed, including on a resume, and its report names the commit it ran on. The caller skip goes. The chain's merge step reuses that run when the head is the gated commit, or the gated commit plus only Handoff's `TODO.md` and run-log commits, unless the gate may read `TODO.md` (owner decision).
- **Base drift (Q2).** When Revise round 1 will run, spec-to-pr fetches the PR's base after Ship. Overlapping base changes are merged in (never a rebase) and the touched tests run, so Revise reviews the merged code. A resumed run's review-round count leaves out merged-in base commits.
- **Implement split (Q3).** Above 40 subtasks, one delegate per `tasks.md` group, in order, each briefed with a summary of the earlier groups.
- **Corrections (Q6).** A correction continues the same agent when the host can message it and the agent returned a report with a named gap. An empty return or exhausted context gets a fresh scoped dispatch. Review rounds after a fix stay fresh.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `change-workflow`: seven ADDED requirements (gate, drift, round count, large builds).
- `change-chains`: one MODIFIED requirement (the prerequisite merge accepts Handoff's closing commits after the gated one).

## Impact

Shipped prose in `spec-to-pr` (SKILL.md, revise, implement-delegate, handoff, workflow-diagram), `multi-pr/references/change-loop.md`, `_shared/references/chain-merge.md` and `subagent-brief.md`. One edit to `probe_state.py`'s round counter, with a regression test. One consistency test is updated. No new script or hook. Third after `lite-pr-red-gate-and-pr-notes` and `spec-size-and-review-tiers`: an ordering dependency for `CHANGELOG.md`, the rule ledger and the docs sweep only; it shares no shipped file or requirement with them.

## Risks noted

- Drift that lands during Revise fix rounds or Archive is still found only at merge. The decisions accept this.
- A later group's delegate works from a summary of the earlier groups. The decisions accept this.
- A flat `tasks.md`, or one group holding most of the tasks, gets no benefit from the split.
- Continuing an agent saves cost by an amount nobody has measured.
- An interrupted drift merge leaves a merge in progress. The existing in-progress-op check catches it when the run resumes.
- An independent chain change whose head moved through a `/cla:multi-pr` deferred-finding fix ends with no full gate on its final head (open question 5).
- The round-count fix covers only runs against the default branch: for a stacked run the probe still ranges from the default branch, so the parent's own review-fix commits stay in range.
- A test that reads `TODO.md` or the run log directly would be missed by the reuse check.

## Open questions

1. **The fetch does not protect the round count.** The probe counts `fix: review round N` subjects over the *local* base name (`main..branch`), and `git fetch` leaves that ref stale. **Recommend:** count against `origin/<base>` when it resolves (tasks 3.1–3.2).
2. **Red tests after the drift merge.** **Recommend:** Test turns ⚠, the report names the failing test, and the run does not loop to fix it.
3. **Drift when Revise is skipped.** **Recommend:** the check runs only when Revise round 1 runs, so no merge commit goes unreviewed.
4. **A continuation that fails.** **Recommend:** one fresh dispatch, never a third try.
5. **A chain fix after the gate.** Under `Full gate: final-commit-only`, `/cla:multi-pr`'s deferred-finding fix re-verifies narrowly and leaves the full run to the pre-merge gate, which runs only for a change a later one needs. **Recommend:** the chain report names such a change as not fully gated at its final head.
