## Why

The live specs describe how CLA's own skills and agents work inside, not what the plugin promises the repos that install it. Decision S7 (`cla.io/decisions/spec-level-and-style-2026-10-08.md`) rewrites them at the level `openspec/config.yaml` `rules.specs` now sets: outcomes a user or owner would recognise, and interfaces others depend on.

## What Changes

- Every live requirement is removed and the plugin's promises are restated under new headings, one sentence each, at most 3 scenarios, at most 8 per spec.
- The capabilities are regrouped around what a consumer meets: `plugin-distribution`, `repo-context`, `guard-hooks`, `change-workflow`, `change-chains`, `run-ledgers`, `annotate`.
- `change-authoring`, `change-review`, `orchestration` and `plugin-architecture` are retired; what they held about skill internals stays in the skills' own files and tests.
- Test `requirement:` markers are re-pointed to the new headings, and the proof-format guard now also scans the live specs for the retired per-scenario marker.

## Impact

- `openspec/specs/**` (rewritten), tests carrying `requirement:` markers, the proof-format guard and its mutation batch, and four shipped references that cited a retired requirement by name.
- No skill behaviour changes.
