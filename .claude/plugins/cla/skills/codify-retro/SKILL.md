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

### 1. Read the aggregated metrics

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/codify-retro/scripts/aggregate.py --limit <N>
```

Where `<N>` is the value from `$ARGUMENTS` (passed through by the command wrapper), or `10` if `$ARGUMENTS` is empty. Substitute the literal number before invoking — the script does not expand shell variables.

Output is a single JSON object on stdout — suggestion apply-rate, re-offending lessons, escalation-rung distribution, repeatedly-rejected lessons, failure-modes bullet trend, codify-process-issue rate.

If `runs_analyzed: 0`, the log doesn't exist yet — say so, stop. The user needs to run `/cla:codify-learnings` a few times first (the log starts accruing only once `log_run.py` is wired, so early windows may be short).

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

Single-digit counts in a category mean "interesting anecdote, not a pattern" — call them out as such, don't propose changes.

### 3. Propose specific edits

For each pattern, name the artifact and the edit, not a vague direction. Examples:

- ❌ "The cross-platform lessons keep failing."
- ✅ "A recurring rule re-offended 3× (re_offenses count: 3) while only ever escalated to `memory` — promote it to a `PreToolUse` hook, per the routing rule's 'hook-able re-offender' clause."

- ❌ "failure-modes is too long."
- ✅ "`${CLAUDE_PLUGIN_ROOT}/skills/codify-learnings/references/failure-modes.md` at 64 bullets (trend 58→61→64); run a Step 2.6 consolidation — merge the 3 cross-platform stdout bullets, retire line 35 (now enforced by the skill-consumed-script honesty memory)."

Cite the metric in parentheses so the user can sanity-check the recommendation.

### 4. Output shape

Render a Markdown report with three sections, in this order:

1. **Window** — runs analyzed, date range.
2. **Patterns** — the 2-4 load-bearing patterns, one paragraph each, with the metric in parens.
3. **Proposed edits** — numbered list. Each entry: target file + section, the specific change, the metric that justifies it.

Keep the whole report under ~40 lines. Long retros don't get acted on.

### 5. Optional: invite the user to apply edits

**Check first whether the plugin is writable here** — the procedure is in `${CLAUDE_PLUGIN_ROOT}/skills/codify-learnings/references/plugin-writability.md`. Every target this retro proposes — `codify-learnings/SKILL.md`, `${CLAUDE_PLUGIN_ROOT}/skills/codify-learnings/references/failure-modes.md` — lives inside the plugin. When the plugin is installed from a marketplace that tree is a read-only, version-keyed cache: an edit either fails or lands somewhere the next update discards, while reporting as applied. If it is read-only, do not offer to apply; present the findings and route them to **`/cla:report-upstream`**, which files them against the canonical source where they can actually change the loop for every repo.

End with: "Want me to apply any of these? Say `apply 1,3` or list the numbers."

Do NOT apply edits without explicit confirmation — retros are advisory. `codify-learnings/SKILL.md` and `${CLAUDE_PLUGIN_ROOT}/skills/codify-learnings/references/failure-modes.md` are the usual targets, and both are editable **only where the writability check above says so**; in a repo that installed the plugin they are read-only and the findings go upstream instead. `openspec/**`, `**/scripts/**/*.py`, and vendored frameworks stay excluded per codify-learnings' own rules.

**If applied edits changed `${CLAUDE_PLUGIN_ROOT}/skills/codify-learnings/references/failure-modes.md`'s bullet count** (a retire or a consolidation), state the new count in the closing summary — e.g. "failure-modes.md now at 47 bullets (was 51)". This retro writes nothing to `codify-runs.jsonl` (its sole producer is codify-learnings' Step 7), so without that line the newest ledger record keeps claiming a count the file no longer has and the trend data reads as flat. Recount with `grep -c '^- \[ \]' ${CLAUDE_PLUGIN_ROOT}/skills/codify-learnings/references/failure-modes.md`; the next `/cla:codify-learnings` run uses it for `maintenance.failure_modes_bullets`.

## Sources of truth

- **Output schema:** see `aggregate.py`'s module docstring for exact field names emitted.
- **Log format:** see `lib/log_run.py` for what gets written per run.
- **What to log:** see `codify-learnings/SKILL.md` "Step 7 — Log the run" for the record schema.

## When NOT to use

- For a one-off codify issue ("why did this run propose that?") — read the `lessons-learned.md` entry + transcript, don't aggregate.
- Before ~5 runs accumulate — noise > signal.
- To debug a specific bug in `aggregate.py`/`log_run.py` — that's a code-reading task, not a metrics task.
