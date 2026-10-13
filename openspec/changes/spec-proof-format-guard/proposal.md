# Proposal

## Why

The owner added the format guard from #319's second comment to PR #365, limited to the three
limits `openspec/config.yaml` `rules.specs` already states: 500 characters per requirement
statement, 3 scenarios per requirement, 8 requirements per spec. No Purpose check and no migration
lists (the comment and the config disagree on Purpose, and this repo has no migration lists).

## What Changes

- `check_spec_proof.py` gains a separate function that reads those three numbers from the
  `rules.specs` text in the repo's `openspec/config.yaml` (never copied into the script) and reports
  each live spec or active delta over them. A limit the config does not state is not enforced, and
  the output says so.
- Same PR, change `trim-retro-summary-scenarios`: the one live requirement over the scenario limit
  is rewritten as `rules.specs` directs.

## Capabilities

### Modified Capabilities

- `spec-proof`: one requirement added (5 requirements in all).

## Impact

The script, its tests and mutation batch, the DEVELOPER-GUIDE row, `spec-to-pr`'s one Implement line.
