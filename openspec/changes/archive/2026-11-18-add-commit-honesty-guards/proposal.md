# Proposal

## Why

Two shipped rules about a commit's record (no `Measured-by: none`, no empty review-round commit) and one about leaked `/cla:diagnose` debug tags lived in prose only.

## What Changes

- `block-dishonest-commit` refuses a `Measured-by: none` trailer and an empty review-round commit; other `--allow-empty` only warns.
- `ask-staged-debug-tag` asks before a commit that would add a debug tag.

## Capabilities

### Modified Capabilities

- `git-guards`: three requirements.

## Impact

Two hooks, their tests, the dispatcher list and the guard tables. No new dependency.
