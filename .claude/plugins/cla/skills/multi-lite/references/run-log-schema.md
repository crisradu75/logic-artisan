# multi-lite — per-run JSONL log schema

The "Log the run" step serializes the whole chain's in-context outcomes as a single JSON object and pipes it to `scripts/log_run.py`, which appends it to `cla.io/retro/multi-lite-runs.jsonl`. This is the `/cla:lite-pr`-chain analogue of `/cla:multi-pr`'s `references/run-log-schema.md` — it captures the chain-level facts a single `/cla:lite-pr` run's view can't see (whether the derived order held, how many candidates shipped/merged/were-left-open/failed/were-blocked, how many needed the deferred-review enforcement round).

**Log-only — there is deliberately NO analyzer skill over this yet** (see SKILL.md "What this skill deliberately does not do"). The schema is written now so the data exists when the sample justifies building a `multi-lite-retro` (~8–10 runs, the same threshold the sibling chain skills use). Every field is optional-additive, so a future aggregator counts each metric's denominator only over records that carry it.

## Invocation

```bash
python3 .claude/plugins/cla/skills/multi-lite/scripts/log_run.py <<'JSON'
{"ts":"<ISO-8601>","source_doc":"<decisions-or-feedback-doc-slug>","candidates":0,"sequence_source":"dependency-then-doc-order|user-corrected","sequence_held":true,"merge_policy":"merge-before-dependents-else-open","gate":{"autonomy_override":false},"counts":{"merged":0,"open":0,"failed":0,"failed_review":0,"blocked":0,"out_of_scope":0},"review_enforcement":{"rounds_run":0,"rounds_resolved":0},"reactive_worktree_pivot":false,"final_master_commit":"<sha-or-null>","output_chars":0}
JSON
```

`log_run.py` `json.loads`-validates, size-checks the 4-KiB atomic-append ceiling, and appends UTF-8 bytes directly — so a malformed line can't silently poison the ledger and there's no raw-shell quoting / `printf` / UTF-16-BOM footgun.

**Replace every placeholder with a real value before sending.** The script rejects invalid JSON with exit 1 (non-fatal — note and continue), but a record full of literal `<...>` / enum-alternation placeholders is *valid* JSON that logs garbage. Counts / flags + small strings only, **no prose** (prose lives in the per-run notes file `cla.io/retro/multi-lite-run-notes-<date>.md`; an oversize record exits 1).

## Field intent

- `ts` — ISO-8601 timestamp of when the run finished (record-assembly time).
- `source_doc` — the decisions/feedback doc slug the candidates were extracted from (its filename stem is fine), so a record is self-describing without cross-referencing the transcript.
- `candidates` — total lite-pr-sized candidates extracted in Phase 1a (excludes the out-of-scope items, which are counted separately under `counts.out_of_scope`).
- `sequence_source` — how the order was decided: `dependency-then-doc-order` (the Phase 1b default — dependency edges first, document order for ties) or `user-corrected` (the confirmation gate reordered/fused/dropped candidates).
- `sequence_held` — did the shipped order match the confirmed one? `false` iff a candidate had to run before a dependency actually landed, or the order was revised mid-run — a `false` flags a Phase 1 sequencing miss worth investigating.
- `merge_policy` — echoed for a self-describing record; `multi-lite` has one policy (merge a candidate only when something depends on it, otherwise leave the PR open).
- `gate.autonomy_override` — did the explicit-autonomy path apply the derived plan without the Phase 1c confirmation?
- `counts` — the terminal disposition of every candidate, one bucket each: `merged` (a dependency merged to unblock dependents), `open` (an independent PR left for the user; includes any flagged `open — unresolved finding`), `failed` (a Test-phase halt), `failed_review` (an unresolved Critical/Important finding after the enforcement round, on a candidate something depended on), `blocked` (skipped because an upstream candidate failed), `out_of_scope` (a non-lite item Phase 1a routed to `spec-to-pr`/`multi-spec`). These plus `candidates` are the primary health signal a future retro reads.
- `review_enforcement` — the deferred-finding enforcement layer's activity: `rounds_run` (how many candidates needed the Phase 3 step 7 additional round) and `rounds_resolved` (how many of those the single round actually cleared). A persistent gap between the two would signal the one-round budget is too tight for this repo's review findings.
- `reactive_worktree_pivot` — did a mid-chain `guard-worktree-isolation.py` block force the reactive worktree pivot? When `true`, `final_master_commit` is `null` (the run couldn't return to `master` to commit the log).
- `output_chars` (optional) — total character count of the user-facing reports printed across the
  whole chain (every `/cla:lite-pr` run's terminal report, summed). A verbosity proxy for a future
  `multi-lite-retro` to trend, NOT a full token-spend measure — it covers only printed report text.
- `final_master_commit` — the `master` HEAD sha the run-log commit is built on: the tip produced by the run's merged dependencies plus the `git pull`, read at record-assembly time. It is deliberately the tip *before* the log commit itself — that commit's own sha isn't knowable yet, since the record is appended (see "Invocation") before the commit that will contain it. `null` **only** when the run can't reach `master` to log at all (the reactive-worktree pivot, or a `CLAUDE_RETRO_DIR`-outside-repo skip). An all-independent run — where nothing merged — still records a real tip here, because the "Log the run" step returns to `master` and commits the log unconditionally regardless of whether any candidate merged; "nothing merged" is not a null case.

**Best-effort, non-fatal.** If `log_run.py` exits non-zero (invalid JSON, oversize, or write failure — the stderr names which), note it and continue: a missing log line never blocks the run, the same non-fatal posture as the sibling chain skills' own run-log steps.
