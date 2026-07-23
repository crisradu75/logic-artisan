# multi-spec — per-run JSONL log schema

The Report phase serializes the whole batch run's in-context outcomes as a single JSON object and pipes it to `scripts/log_run.py`, which appends it to `cla.io/retro/multi-spec-runs.jsonl`. This is the deliberate sibling of `spec-to-pr/references/run-log-schema.md` (per-change) and `multi-pr/references/run-log-schema.md` (per-chain) — sized for the facts a proposal-authoring **batch** produces that neither sibling schema captures: which grouping source was trusted, how many review findings surfaced per change, and whether a prior interrupted run was resumed.

**Log-only — there is deliberately NO `multi-spec-retro` analyzer skill yet**, mirroring `multi-pr`'s own "revisit once ~8-10 chains accumulate" posture and `codify-retro`/`spec-to-pr-retro`'s shared "before ~5 runs, noise > signal" rule. This schema is written now so the data exists when the sample justifies building one. Every field is optional-additive, so a future aggregator counts each metric's denominator only over records that carry it.

## Invocation

```bash
python3 .claude/plugins/cla/skills/multi-spec/scripts/log_run.py <<'JSON'
{"ts":"<ISO-8601>","decisions_file":"cla.io/decisions/<stem>.md","batch_slug":"<slug>","sequence_source":"file-sequencing-section|derived-judgment","escalate_up_fired":false,"resumed":false,"changes":["<name-in-authored-order>"],"review":{"verdicts":{"<name>":"READY|FIX FIRST|RETHINK"},"critical":0,"important":0,"suggestion":0},"pr_number":0,"final_branch_head":"<sha>","output_chars":0}
JSON
```

`log_run.py` `json.loads`-validates, size-checks the 4-KiB atomic-append ceiling, and appends UTF-8 bytes directly — so a malformed line can't silently poison the ledger and there's no raw-shell quoting / `printf` / UTF-16-BOM footgun (same as its `spec-to-pr` and `multi-pr` siblings).

**Replace every placeholder with a real value before sending.** Counts/flags + small arrays only, **no prose** (prose lives in the PR body and the decisions file itself; an oversize record exits 1).

## Field intent

- `decisions_file` / `batch_slug` — identify which input produced this run, so a future aggregator can tell whether the same decisions file was re-run (a resume) versus a genuinely new batch.
- `sequence_source` — `file-sequencing-section` (Phase 1 trusted the decisions file's own grouping) or `derived-judgment` (no such section existed; the skill derived grouping itself). If `derived-judgment` shows up disproportionately, that's a signal `shape-decision`'s own output should more consistently include a sequencing section, not that `multi-spec`'s fallback is broken.
- `escalate_up_fired` — did the sub-Opus escalate-up rule fire for the Phase 1 grouping judgment. Mirrors `spec-to-pr`'s own `routing.escalate_up_fired` field.
- `resumed` — was this invocation a resume of a prior interrupted run (Phase 1's plan-file-already-exists check, or Phase 3's per-change tracked-file check, found prior state) rather than a fresh start. A `resumed: true` rate worth investigating over time tells you whether the durability mechanism is actually being exercised for real, not just built for a hypothetical.
- `changes` — the change names in the order they were actually authored (which reflects the dependency order Phase 1 derived).
- `review.verdicts` — the per-change verdict from Phase 4's batch review dispatch (`READY` / `FIX FIRST` / `RETHINK`, same rubric as `review-change/references/checklist.md`). `review.critical`/`.important`/`.suggestion` are the aggregate counts across the whole batch dispatch (Critical+Important is the applied-fix count; Suggestion is informational only, same severity split `spec-to-pr`'s own schema uses).
- `pr_number` / `final_branch_head` — the shipped PR and the branch-head sha at the point this record was logged, for attributing a ledger line to a concrete tree state (mirrors `multi-pr`'s `final_master_commit` field, scoped to this batch's own branch instead of `master` since this skill never merges).
- `output_chars` (optional) — total character count of the user-facing reports printed across the
  whole batch run (the Report phase's own summary plus every per-change proposal report, summed). A
  verbosity proxy for a future `multi-spec-retro` to trend, NOT a full token-spend measure — it
  covers only printed report text.

**Best-effort, non-fatal.** If `log_run.py` exits non-zero (invalid JSON, oversize, or write failure — the stderr names which), note it in the Handoff Issues equivalent and continue: a missing log line never blocks the run, the same non-fatal posture as every sibling in this family.

## Committing the log line onto the batch branch

So it ships with the PR instead of dangling as an uncommitted file (same reasoning `/cla:spec-to-pr`'s Handoff step 6 gives for its own run-log commit):
```
python3 .claude/plugins/cla/skills/spec-to-pr/scripts/git_state.py --expect-branch docs/propose-<batch-slug>
python3 .claude/plugins/cla/skills/spec-to-pr/scripts/commit.py --message "chore: multi-spec run log" cla.io/retro/multi-spec-runs.jsonl
git push
```
Then run the push post-check (`references/phases.md`). **Skip this commit entirely if `CLAUDE_RETRO_DIR` points outside the repo** — nothing tracked to commit.
