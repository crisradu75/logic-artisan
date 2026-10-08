## Why

A fifth of the fleet's spec-to-pr run records (40 of 201) are in shapes the retro cannot read:
`phases` written as an object, `date` in place of `ts`, `asks` as an object. The records are
written by a model following prose, and nothing checked them. A write-time check was proposed on
2026-09-05 and dropped because no producer was in scope and it checked keys, not values; this
change includes the producers and checks value shapes
(`cla.io/decisions/retro-and-learning-loop-simplification-2026-10-08.md`, D3 and D3a).

## What Changes

- `lib/log_run.py` holds the record shape of `spec-to-pr-runs.jsonl` and `codify-runs.jsonl` and
  refuses a record that does not match, with one line naming the field. Other ledgers keep the
  name and size checks only.
- Producers: spec-to-pr's Handoff, `run-log-schema.md` (now field meanings only; the shape lives in
  code) and codify-learnings Step 7 build the record from the reference, and on a refusal fix the
  named field and retry once, then continue. multi-pr writes no record of its own; its runs go
  through spec-to-pr's Handoff.
- `plugin-tests/scripts/migrate_run_records.py` rewrites old-shape spec-to-pr records once, per
  repo; this repo's ledger is migrated here. Consumer repos run it in their own PRs.

## Impact

- `run-ledgers`: one added requirement. The codify record shape changes again in the next change
  (`slim-codify-learnings`), which edits only the shape in `log_run.py` and its producer.
