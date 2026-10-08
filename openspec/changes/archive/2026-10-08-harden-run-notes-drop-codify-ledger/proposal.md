## Why

Review of `retire-unread-ledgers` found its run-notes mechanism loose: a resumed `multi-lite` run
forgave any head move whose net diff named a notes file (a rename into the notes path included),
the resume lookup took the newest notes commit of any doc, chains committed every notes file by
glob, and nothing stopped a push that recreates a just-merged branch. The spec also promised more
than the recipes do. Separately, `codify-runs.jsonl` has no reader, and the lessons-log entry
already records the same fixes, rungs and re-offenses
(`cla.io/decisions/retro-and-learning-loop-simplification-2026-10-08.md`, D4 and D10).

## What Changes

- `multi-lite` and `multi-pr` give their notes commits one fixed message each, commit only their
  own notes file, re-check the last PR is open after pulling, and never push once it merged.
- A `multi-lite` re-run forgives a head move only when every commit since carries that message and
  the rename-blind diff names nothing but its notes file; both chains find earlier notes by that
  message, not by recency, and return to the base branch after taking them out.
- `codify-learnings` stops writing a ledger line; `log_run.py` accepts only
  `spec-to-pr-runs.jsonl`; `cla-init` stops seeding `codify-runs.jsonl` and lists it as retired.
- spec-to-pr's Test phase counts each escalation to `/cla:diagnose` when it happens.

## Impact

- `run-ledgers`: the write-check and ride-the-PR requirements rewritten (codify gone; spec-to-pr's
  record and the chains' notes stated apart). `small-change-chains`: the resume requirement
  rewritten to allow exactly the run's own notes commits. `repo-context`: the codify ledger
  reported as retired.
- Consumers: `cla-init` offers to delete `codify-runs.jsonl`; a stale overlay writing it gets a
  refusal line, which never halts the run.
