# Proposal

## Why

Repo docs outside `openspec/` drift because nothing names them when a change is planned and nothing
checks them when it is reviewed. `review-sweeps.md` already reads a "Doc-sweep paths" list, but only
when a change retires something, and this repo's facts file has no such list. Issue #387 asks for a
docs task on every change. Decisions: `cla.io/decisions/docs-currency-and-spec-map-2026-10-15.md`
(1-3, 8 change A, 9). Change B (the spec map itself) follows after this merges.

## What Changes

- This repo's `cla.io/project-facts.md` gains a "Doc-sweep paths" list.
- `rules.tasks` in `openspec/config.yaml`, and the same rule in the `cla-setup` seed script, gain the
  docs task: `docs and spec map: <files updated>, or none affected: <reason>`.
- `/cla:spec-to-pr`: the review before implementation flags a missing or empty docs task; the
  Implement post-check confirms it exists, is ticked and names files the branch changed; Revise round
  1 compares the named docs and the doc list with the diff. The orchestrator makes that comparison
  itself, because the diff reviewers read only the diff. A stale doc is an Important finding in that
  round's triage. Both checks apply only where the repo's `rules.tasks` carries the docs rule, so a
  repo that has not re-seeded sees no new Issue. Without a doc list, judgement picks the docs.
- `/cla:lite-pr` carries the same duty as one Plan line and one Review check.
- `cla-setup`'s description of the doc list says it serves every change and leaves out the spec tree.
- New capability `docs-currency` holds the requirement (`change-workflow` is full at 8). After
  archive its Purpose gets a `**Serves:**` line.

## Capabilities

### New Capabilities

- `docs-currency`: one requirement.

## Impact

`openspec/config.yaml`, `seed_openspec_rules.py`, `project-facts.md`, `spec-to-pr/SKILL.md` and
`references/revise.md`, `review-change/references/checklist.md` and `dispatch.md`, `lite-pr/SKILL.md`,
`cla-setup/SKILL.md`, one new consistency test. Out of scope: the spec map, its location fact and the
`check_spec_proof.py` guard (change B). A fix to a stale doc is a doc edit, so the mutation gate has
nothing to break there; the report says so.
