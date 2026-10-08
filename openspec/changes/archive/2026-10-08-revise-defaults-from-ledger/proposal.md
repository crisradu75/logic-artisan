## Why

Revise's second round was left optional until `findings_by_round` covered eight changes across two
chains. It now covers 37 changes across 16 chains, and in all 37 the second round found a Critical
or Important (`cla.io/decisions/retro-and-learning-loop-simplification-2026-10-08.md`, D8a). The
same ledgers give `comment-analyzer` the lowest Critical/Important yield per run of the six
Revise agents, 23 in 38 runs against `code-reviewer`'s 172 in 47 (D8b).

## What Changes

- **Revise**: round 2 runs whenever round 1 committed fixes, scoped to that fix diff; the cap
  stays 2 and `--pr-rounds 1` opts out. The reversal condition and its deferral prose go.
  `PREV_FIX_SHA` is captured just before the fix commit, so `PREV_FIX_SHA..HEAD` is that diff.
- **`comment-analyzer`**: dispatched only when the diff adds or changes substantial comments,
  docstrings or prose files; never on a code-only diff.
- **Retro**: the reversal check becomes `round_2_yield`, over the `--limit` window like every
  other metric. Revise counts as cap exhaustion, in the retro and in the Handoff nudge, only when
  it ended at its cap still `warn` or `fail`.

## Impact

- `change-workflow`: one requirement modified. `run-ledgers`: two requirements removed, two added.
- The nudge stops firing on a routine round 2; see `tasks.md` 2.2 for the replay.
