## Why

The spec-to-pr ledger carries real signal — round-cap hits, per-agent Revise yield, recurring warn
reasons, `findings_by_round` — but its reader is mostly drift handling: a 2,000-word skill over a
927-line script, one heuristic that reads a field the script never emits, four emitted fields
nothing reads, and a reversal condition left to be judged by hand. Records are now checked when
written, so the drift buckets have nothing left to catch, and the retro has run once since July
because nothing prompts it (`cla.io/decisions/retro-and-learning-loop-simplification-2026-10-08.md`,
D7, D12).

## What Changes

- **`spec_to_pr_aggregate.py`** reads the fleet by default (`cla.io/fleet.local.md`), falling back
  to this repo's ledger with a stated reason when the file is missing or none of its per-machine
  roots exists here. It emits only provenance, warn reasons, cap exhaustion, per-agent Revise
  yield, ask answers, and the `--pr-rounds` reversal condition computed outright. A record it
  cannot read is skipped, named and counted; the drift buckets go.
- **`--nudge`**: one line or nothing, from this repo's last five records. spec-to-pr's Handoff
  prints it after appending the run record.
- **`spec-to-pr-retro/SKILL.md`** to about 300 words; `retro-skeleton.md` folds in and is deleted.
- `run-log-schema.md`: `findings_by_round` described like any other field.
- `run-ledgers`: the retro-report requirement rewritten; a Handoff-nudge requirement added.

**Dropped, and why it is safe** (check 2): see `tasks.md` 1.3.

## Impact

- `run-ledgers`: one requirement removed, two added.
- Consumers: a ledger not yet migrated by `migrate_run_records.py` shows as skipped records rather
  than drift counts; each consuming repo migrates its ledger in its own PR before the release.
