# Proposal

Budget: protected

## Why

Review's rejected-alternatives snapshot has no input unless the change's design lists its rejected alternatives. A build that departs from a requirement can leave the delta spec describing what was not built. The pull request body is written once at open, so after the review fix rounds its risk level and checks can be stale. The owner decided Q2, Q8, Q14, Q16 and Q17 in `cla.io/decisions/warp-patterns-adoption-2026-11-21.md`; the wording fixes come from the spec-path section of `cla.io/feedback/plugin-analyzers-2026-11-21.md`.

## What Changes

- `/cla:spec-to-pr` Propose asks that a change touching a protected area list its rejected alternatives in `design.md`, one line each; `none considered` is valid.
- Implement edits the change's delta spec in the same commit when the build departs from a requirement on purpose, then re-validates it.
- Handoff, after the review fix rounds, checks the pull request body still describes the branch and that its `Risk:` and `Checks:` lines are current, and updates only those.
- Wording and placement: the check count excludes the overlay's labels, checks 0a to 0c are stack-neutral, the autonomy exceptions list the `git_state` halt and the precheck ask, the full gate rule moves to Handoff's gate rules, Implement's post-checks move to a reference, the reference list is corrected, and overlay pointers are added.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `change-workflow`: three ADDED requirements.

## Impact

Shipped: `spec-to-pr/SKILL.md`, `spec-to-pr/references/handoff.md`, a new `spec-to-pr/references/implement-checks.md`, `review-change/SKILL.md` and its `checklist.md`, and the rule ledger. No script or hook changes.

## Risks noted

- A rewrite of the body could drop the `Risk:` format `revise.md` reads; the rule keeps it.
- The `<inherits>` detail stays in `SKILL.md` because a consistency test pins that region there.
