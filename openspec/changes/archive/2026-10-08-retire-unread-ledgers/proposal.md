## Why

Three skills log runs no decision reads (`lite-pr`, `shape-decision`, `feedback`), their generic
reader exists only for them, and the spec-to-pr record carries a dozen fields no aggregator reads.
Chains record their run notes in a direct commit to the base branch, which the pre-push guard
refuses, and repos onboarded earlier still hold ledgers nothing writes
(`cla.io/decisions/retro-and-learning-loop-simplification-2026-10-08.md`, D9–D11; the `flags`
and diagnose count are `plugin-surface-simplification-2026-10-08.md` P1a and P4b).

## What Changes

- `lite-pr`, `shape-decision` and `feedback` stop logging; `lib/ledger_summary.py` and its tests
  are deleted. `log_run.py` accepts only `spec-to-pr-runs.jsonl` and `codify-runs.jsonl` and
  refuses any other ledger name.
- The spec-to-pr record keeps only what `spec_to_pr_aggregate.py` reads, plus `mode`, and gains
  `flags` and `escalated_to_diagnose`, which the aggregator now counts. Older records keep their
  extra fields; nothing reads them.
- `multi-lite` and `multi-pr` commit their run notes onto the chain's last open PR at the end,
  never the base branch; with no PR open they leave them uncommitted and say so. A re-run takes
  committed notes back out of that PR first.
- `cla-init` lists the retired ledgers a repo holds and deletes them only on an explicit yes.

## Impact

- `run-ledgers`: the spec-to-pr record requirement modified; the write-check requirement replaced
  by one that also refuses unknown ledgers; flag and diagnose summaries and notes-ride-the-PR
  added. `repo-context`: retired-ledger reporting added.
- Consumers: a skill or overlay still invoking `log_run.py` with another ledger name gets a
  refusal line, which never halts the run. `cla-init` offers to delete their orphan ledgers.
