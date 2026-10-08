## Why

A repo's facts have two homes by design: 25 skill lines say "read project-facts, fall back to the
overlay", and most consumer overlays are untouched template stubs, so review-change's "mandatory"
overlay injection injects nothing. Onboarding takes two skills, `cla-init` (structure) and
`sync-context` (facts), where one would do
(`cla.io/decisions/plugin-surface-simplification-2026-10-08.md`, P3 and P4).

## What Changes

- **`/cla:cla-setup` replaces `/cla:cla-init` and `/cla:sync-context`.** Part 1 creates whatever is
  missing of `cla.io/` (never overwriting), seeds the OpenSpec rules, reports retired ledgers and
  keeps chain run notes out of git; Part 2 proposes and, on a yes, writes `cla.io/project-facts.md`.
  It is slash-command only (`disable-model-invocation: true`). **BREAKING:** consumers type a new
  command; no alias skill is kept, and the 2.0.0 release notes say so.
- The run-notes `.gitignore` check ignores this machine's global excludes file, so a machine whose
  global excludes already hide the notes still writes the repo line other clones need.
- **Overlays become optional and hold only a skill's own rules.** Every "fall back to the overlay"
  clause goes; commands, paths, ports, install and env come from `cla.io/project-facts.md` only.
  review-change's and project-review's named overlay sections and "mandatory" injection go. No stub
  is ever written; `cla-setup` proposes moving facts out of existing overlays, dated incidents to
  `cla.io/lessons-learned/`, and deleting overlays that hold only template headings.
- This repo: the six content-free overlays are deleted; `cla.io/project-facts.md` is created with
  the verification commands that sat in the codify-learnings overlay.

## Impact

- `repo-context`: five requirements replaced (REMOVED and ADDED under new headings); still eight.
- Every shipped skill that read an overlay, the plugin README, CLAUDE.md, DEVELOPER-GUIDE, and the
  tests and mutation batches that read `cla-init/SKILL.md` or `sync-context/`.
