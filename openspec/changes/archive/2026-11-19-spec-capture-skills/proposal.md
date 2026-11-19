# Proposal

Budget: protected

## Why

Five more skills have no spec: `/cla:checkpoint`, `/cla:feedback`, `/cla:shape-decision`, `/cla:project-review` and `/cla:right-model`. With the previous change this leaves no shipped skill outside the specs, so the "Skills without a spec" section of the spec map goes away. Four live specs also name file paths that no consumer depends on.

## What Changes

- New `session-records`: a checkpoint is a resumable briefing that is checked against the tree before it is followed; feedback notes are captured one at a time into a new dated file that never overwrites; a decision is shaped one question at a time and written only on a yes.
- New `project-review`: baseline checks first, five concurrent reviewers, a verdict from the grades, and no change to the repo.
- New `model-advice`: the cheapest model and effort that clear the bar, and a start only on the user's yes.
- Path audit: two `spec-proof` requirements and one `repo-context` requirement lose a path that is not an interface; the other paths in `instruction-files`, `spec-proof`, `cla-setup` and `repo-context` are files a consuming repo writes or reads, and stay. No requirement in `change-chains`, `change-workflow` or `run-ledgers` is over 500 characters (longest 494).
- `openspec/spec-map.md` links every new spec and drops the unspecced-skills section.

## Capabilities

### New Capabilities

- `session-records`, `project-review`, `model-advice`.

### Modified Capabilities

- `spec-proof`: two budget requirements reworded, scenarios kept.
- `repo-context`: the recorded-paths requirement reworded, scenarios kept.

## Impact

Three new specs, two reworded, tests and the spec map. No shipped plugin file changes.
