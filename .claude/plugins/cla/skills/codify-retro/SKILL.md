---
name: codify-retro
description: "Review recent /cla:codify-learnings runs and propose concrete improvements to the loop itself (codify-learnings/SKILL.md, references/failure-modes.md, the escalation ladder). Reads the project's codify-runs JSONL log, aggregates deterministic metrics (suggestion apply-rate, lessons that re-offend across runs, escalation-rung distribution, repeatedly-rejected lessons, failure-modes bloat, codify-process-issue rate), then surfaces patterns and proposes specific edits. Triggers on /cla:codify-retro or natural language like 'review my recent codify runs', 'how is codify-learnings doing', 'what should I fix in codify-learnings'."
argument-hint: "[N (last N runs, default 10)]"
---

# /cla:codify-retro — retrospective on the learning loop

Reviews the repo's `cla.io/retro/codify-runs.jsonl` log and proposes targeted improvements to `/cla:codify-learnings` itself. The data is captured by `codify-learnings`'s final step via `log_run.py` — one JSON line per run, counts-only (no prose; prose lives in `lessons-learned.md` and transcripts). The ledger is committed to the repo so it syncs across machines via git (override the dir with `CLAUDE_RETRO_DIR`).

This closes the loop's outer loop: `codify-learnings` learns from sessions; `codify-retro` learns whether `codify-learnings` is actually working — whether its escalations reduce re-offenses, which suggestions keep getting rejected, and whether its own machinery is drifting.

## When to invoke

- After ~5+ /cla:codify-learnings runs have accumulated (smaller windows are noisy).
- When the loop feels off (re-offenses keep recurring, suggestions keep getting rejected, failure-modes.md is bloating).
- Periodically as part of repo hygiene.

## Workflow

**Read `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/retro-skeleton.md` first** — it carries the
five workflow steps, the report shape, the apply-gate, and the sources-of-truth list that every
retro shares. This body supplies only what is specific to the codify loop: the aggregate command
and the interpretation heuristics.

### 1. Read the aggregated metrics

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/codify-retro/scripts/codify_aggregate.py --limit <N>
```

Where `<N>` is the value from `$ARGUMENTS`, or `10` if empty. Substitute the literal number before
invoking — the script does not expand shell variables.


**Reading more than one repo's ledger.** `--log` takes several paths, and the records aggregate together:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/codify-retro/scripts/codify_aggregate.py --limit 0 \
  --log <repo-a>/cla.io/retro/codify-runs.jsonl <repo-b>/cla.io/retro/codify-runs.jsonl
```

Worth doing whenever one repo's ledger is thin, which is the usual case — a five-record sample put one round-cap exhaustion rate at 4 of 5 where 156 records put it at 6 of 129. Three things change in fleet mode, and each is visible in the output rather than assumed: `--limit` applies PER LEDGER, so `runs_analyzed` can reach N x ledgers; `ledgers` carries per-path provenance, and a path that did not resolve shows `found: false` with `records: 0` — check it before trusting the sample size; and `log_path` is omitted, since no single path describes the result.

One caveat specific to this loop: the per-repo maintenance fields — `failure_modes_bullets_latest`, its trend, `live_log_entries_latest`, and `output_chars` — describe ONE repo's own files, so they are suppressed in fleet mode and the output carries `per_repo_fields_suppressed: true`. The loop-hygiene heuristics below need a single-ledger run; the effectiveness and rung heuristics do not.

Output is a single JSON object on stdout — suggestion apply-rate, re-offending lessons, escalation-rung
distribution, repeatedly-rejected lessons, failure-modes bullet trend, codify-process-issue rate.

### 2. Identify the load-bearing patterns

Don't list every metric. Pick the 2-4 patterns that would actually change the loop. Heuristics:

**Effectiveness heuristics (the whole point):**
- A lesson in `re_offenses` with `count ≥ 2` → the artifact it was escalated to is **too weak**; the escalation isn't working. Bump it UP the ladder (memory → hook/script). This is the single most important signal — a re-offense means the prior fix failed.
- A lesson in `rejected_lessons` with `count ≥ 2` → stop proposing it; **retire** it from `${CLAUDE_PLUGIN_ROOT}/skills/codify-learnings/references/failure-modes.md` (the SKILL.md's Step 6 already says to flag these — verify it's actually happening).
- `suggestions.apply_rate < 0.5` over the window → the proposal bar is too low (too much rejected noise); tighten what qualifies as a suggestion (SKILL.md "Style": every suggestion tied to a concrete this-session event).

**Routing heuristics:**
- `escalation_rungs` concentrated in `checklist`/`memory` with zero `hook`/`script` despite recurring `re_offenses` → behavioral re-offenders are never getting enforced (stuck in the **Instructional** tier). The routing rule (SKILL.md "Lesson routing and escalation") says a re-offending hook-able rule MUST become a hook — check whether that's being honored, and whether the graduation picked the right enforcement tier (a **Prompted** warn-hook for a rule with legitimate exceptions vs a **Mechanical** block-hook for an always-wrong one, per codify-learnings' "Enforcement tiers" overlay).
- `escalation_rungs_unknown` non-empty → the producer is emitting `escalated_to` values outside the rung whitelist; fix the codify-learnings log record before trusting the distribution.

**Loop-hygiene heuristics:**
- `maintenance.failure_modes_bullets_latest > 60`, or `failure_modes_bullets_trend` only ever rising → the checklist is bloating and silently stops being read. Force a Step 2.6 consolidation/retire pass.
- `maintenance.trim_runs == 0` over a long window while `live_log_entries_latest > 12` → the live-log trim isn't firing; the log is growing unbounded.
- `process_issue_runs / runs_analyzed ≥ 0.4` → the codify workflow itself keeps misfiring (Step 3.5 self-check flagging issues); read the recent `### Codify-process notes` in `lessons-learned.md` and fix the workflow.

**Schema-integrity (act before trusting the others):**
- `skipped_records > 0` → producer is writing malformed JSONL lines; the rest of the analysis runs on a shrunken sample. Fix the log record shape first.
- `coerced_fields > 0` → some count fields were present but the wrong type (string/bool where an int was expected) and were dropped from the sums; the rates above are computed over a thinned sample. Check the producer's Step 7 serialization.
- `escalation_rungs_unknown` non-empty → the producer emitted `escalated_to` values outside the rung whitelist; the distribution above excludes them.
- `shape_drift_records > 0` → some records lost a field the metrics are computed from, so `runs_analyzed` overstates the sample those metrics actually ran on. `shape_drift_fields` names which field drifted and how often — that name IS the producer edit to make. Read this before any ratio below: a rate over a thinned sample reads exactly like a rate over a whole one.

Single-digit counts in a category mean "interesting anecdote, not a pattern" — call them out as such, don't propose changes.

### 3-5. Propose, report, and optionally apply

Per the shared skeleton. Worked examples in this loop's own vocabulary:

- ❌ "The cross-platform lessons keep failing."
- ✅ "A recurring rule re-offended 3x (re_offenses count: 3) while only ever escalated to `memory` — promote it to a `PreToolUse` hook, per the routing rule's 'hook-able re-offender' clause."
- ✅ "`${CLAUDE_PLUGIN_ROOT}/skills/codify-learnings/references/failure-modes.md` at 64 bullets (trend 58->61->64); run a Step 2.6 consolidation."

The usual apply targets are `codify-learnings/SKILL.md` and
`${CLAUDE_PLUGIN_ROOT}/skills/codify-learnings/references/failure-modes.md`.

**If applied edits changed that file's bullet count** (a retire or a consolidation), state the new count in the closing summary — e.g. "failure-modes.md now at 47 bullets (was 51)". This retro writes nothing to `codify-runs.jsonl` (its sole producer is codify-learnings' Step 7), so without that line the newest ledger record keeps claiming a count the file no longer has and the trend reads as flat. Recount with `grep -c '^- \[ \]' ${CLAUDE_PLUGIN_ROOT}/skills/codify-learnings/references/failure-modes.md`.

## When NOT to use

Per the shared skeleton's "When NOT to use a retro". This loop's threshold is ~5 `/cla:codify-learnings` runs.
