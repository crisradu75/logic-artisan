## Why

Specs in every CLA repo are too detailed. They record implementation choices and how CLA's own
skills work, and most requirements are longer than OpenSpec's 500-character limit. The authoring
rules and the reviews push them that way: per-scenario proof rewards narrow scenarios, a review
fix lands as spec text, and a MODIFIED requirement is exempt from the size check. The owner agreed
the fix on 2026-10-08 (`cla.io/decisions/spec-level-and-style-2026-10-08.md`, S1–S6).

## What Changes

- `openspec/config.yaml` `rules:`, and the copy cla-init seeds: a spec states only outcomes and
  interfaces; each requirement, ADDED or MODIFIED, is one sentence within 500 characters, with at
  most 3 scenarios, and a spec holds at most 8 requirements. Each new or changed requirement is
  proven by a test carrying a `requirement: <spec> / <heading>` line, or by a `manual:` line;
  scenarios are examples.
- review-change: a code name, file path or skill-internal rule in a spec is a finding; the level
  and size check applies the config rules to MODIFIED requirements too; fixes go to design.md,
  tasks or code, and to spec text only for an outcome or interface. "Pinning a wording detail" and
  the delta-spec ask for an inherited field are gone.
- spec-to-pr and multi-spec apply the config rules instead of carrying copies, and route review
  fixes the same way. project-review grades spec level and plain words.
- lite-pr edits a live spec only to change an outcome or interface, applying the config rules.
- cla-init compares an existing config's rules with the shipped block, lists the missing or
  outdated ones, and updates them only when the user agrees.
- Tests: the proof-format guard checks requirement markers, the existing markers name their
  requirements, and cla-init's seed script runs against scratch repos.

## Impact

- `plugin-architecture`: the cla-init seeding requirement now lists outdated rules and offers an
  update.
- Left for the live-spec rewrite that follows: `change-authoring` and `change-review` still
  describe per-scenario proof, the MODIFIED length exemption and the brief's restated limits. That
  rewrite removes those requirements and switches validation to `--strict`.
