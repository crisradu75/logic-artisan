# Proposal

Budget: protected

## Why

Three skills that touch repository state, the user's settings and another repo's issue tracker have no spec: `/cla:new-worktree`, `/cla:report-upstream` and `/cla:save-permissions`. The project review graded requirements and specs below A for this gap, and reverses the earlier owner decision to leave eight skills unspecced. These three carry the most risk, so they go first.

## What Changes

- New `worktree-setup`: a ready worktree, setup-only inside an existing one, writes kept inside the worktree, a casing fallback that deletes nobody's files, and removal that lists what it would delete.
- New `upstream-reports`: only defects wrong in every repo are reported, from facts read this run, to the target the plugin's manifest names, as a comment on a known issue rather than a second issue, changing nothing else.
- New `permission-saving`: only new permissions are listed, existing settings survive, and a wildcard needs the user's yes.
- Two mismatches found while writing the specs are fixed with regression tests: the save script crashed on a settings file with no `permissions` key and its write was not atomic; `/cla:report-upstream` told the model to write a body file but held no tool to write one.

## Capabilities

### New Capabilities

- `worktree-setup`, `upstream-reports`, `permission-saving`.

## Impact

Three new specs, two skill files, tests and `openspec/spec-map.md`. Needs a plugin patch release.
