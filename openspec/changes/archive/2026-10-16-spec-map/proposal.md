# Proposal

## Why

OpenSpec specs are granular, one capability slice each. Nobody can see how they add up to what the
product does, or which workflow a change touches, and a hand-kept overview drifts from the specs.
Issue #376 asks for a spec map that bridges the levels, with a guard against drift. Decisions:
`cla.io/decisions/docs-currency-and-spec-map-2026-10-15.md` (4 to 7, 8 change B). Change A (the docs
task, already merged) made the map one entry in every change's docs task.

## What Changes

- A repo declares its map in `cla.io/project-facts.md` under `## Spec map`: one path or glob per
  bullet, any layout. No declaration means no map, and nothing fires.
- The map has three layers: capabilities, the workflows that deliver them, and the specs each
  workflow step links. Links only: no configurable values, no restated rules.
- `/cla:cla-setup` offers a default scaffold for a repo with `openspec/`. It writes only on a yes, at a
  path the user picks, and never seeds it silently.
- `check_spec_proof.py` gains one rule inside the script. Once a map is declared it reports
  `PROBLEM spec-map` (exit 1) for a spec (live, or added by the change) no map file links, a map link to a spec that does not
  exist, and a declared path that matches no file. A malformed declaration exits 2. With no
  declaration the output does not change.
- This repo declares `openspec/spec-map.md`, which links every spec, and lists it in "Doc-sweep
  paths". The `check_spec_proof.py` row in DEVELOPER-GUIDE section 11 mentions the rule.

## Capabilities

### New Capabilities

- `spec-map`: the declaration fact and the scaffold setup offers. After archive its Purpose gets a
  `**Serves:**` line, and this repo's map links the new spec.

### Modified Capabilities

- `spec-proof`: one added requirement for the map rule (it holds 6 of 8).

## Impact

`check_spec_proof.py`, `cla-setup/SKILL.md`, `project-facts.md`, `openspec/spec-map.md`,
`DEVELOPER-GUIDE.md` (one table row), tests under `plugin-tests/tests/`. Out of scope: any change to
the docs task wording, the release files, and a rule that a workflow step must link a spec.
