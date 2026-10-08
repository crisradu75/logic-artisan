## Why

A review of the spec-level rules change found the new rules at odds with OpenSpec's own authoring
instruction, a rule kept only for the retired per-scenario proof, `--strict` left off the edits it
should check, an update in cla-init that could delete a repo's own rule, and copies of the rules
the change meant to remove.

## What Changes

- `openspec/config.yaml` `rules.specs`, and cla-init's copy: a MODIFIED block keeps every live
  scenario; a live requirement is cut or brought within the limits by REMOVED plus ADDED under a new
  heading, overriding OpenSpec's keep-it-whole instruction; a full spec gets a new capability. The
  scenario-heading uniqueness rule goes, with its review finding and tests.
- lite-pr validates each spec it edits with `--strict`; archive and multi-pr say why whole-tree
  `validate --specs` stays non-strict (recorded under S2 in
  `cla.io/decisions/spec-level-and-style-2026-10-08.md`).
- cla-init lists the exact lines it would add and remove, removes only earlier wordings of shipped
  rules, and asks for a yes on that diff.
- project-review's spec agent grades spec level; duplicated rule and fix-routing text is cut.

## Impact

- `change-authoring`, `change-review`: the two scenario-heading requirements are removed.
