# Per-step mechanics (Step 3.5, Step 7, Prefer-fixes triggers)

Read the relevant section below before executing that step in full; `SKILL.md`'s own stub for each carries only the correctness-gating one-liner and a pointer here.

## Step 3.5 triggers (codify-process self-check)

Trigger a self-improvement suggestion when any of these hold:

- A **re-offense** (Step 2.5) was mis-routed by the escalation ladder — e.g. a hook-able behavioral rule that the ladder sent to memory again, or a lesson the ladder had no rung for.
- The **Step 2.5 effectiveness check produced no classification** for most bullets (the check is going through the motions without reading back real outcomes) — the check itself needs sharpening.
- A **suggestion type keeps getting rejected** across runs (visible in the log / the Step 7 ledger) — the heuristic that proposes it is miscalibrated.
- The **workflow hit a snag this run** — an ambiguous step, a missing instruction, a scope/routing rule that didn't cover the case you hit.
- A **failure-modes bullet has graduated** to a hook/script and should be retired (Step 2.6), but the maintenance pass didn't catch it.

If nothing misfired, write one line to that effect in the log's `### Codify-process notes` — a clean run is a valid outcome, not a reason to invent a self-edit.

## Step 7 ledger schema

Record schema (counts-only — NO prose; the script rejects records ≥ 4 KiB). `log_run.py` checks this shape — it is defined once, in that file's `SHAPES` — and refuses a record that does not match with one line naming every field that is off. Every key below is required except `effectiveness`, `output_chars` and a re-offense's `failing_artifact`; `re_offenses` and `rejected_lessons` are lists even when empty, counts are integers, and `trimmed` / `process_issue` are `true` / `false`. The example is a record the check accepts as written — build yours from it, replacing each value with this run's:

```json
{
  "ts": "2026-05-28",
  "scope": "repo-wide",
  "suggestions": {"proposed": 2, "applied": 2, "rejected": 0},
  "memory": {"proposed": 1, "applied": 1},
  "effectiveness": {"prevented": 3, "re_offended": 1, "not_exercised": 9},
  "re_offenses": [
    {"lesson": "stale-port", "failing_artifact": "CLAUDE.md", "escalated_to": "hook"}
  ],
  "rejected_lessons": [],
  "maintenance": {"failure_modes_bullets": 51, "live_log_entries": 30, "trimmed": false},
  "process_issue": false,
  "output_chars": 900
}
```

- `ts` is today's date, `YYYY-MM-DD`, from the currentDate context. `scope` is `repo-wide` or a
  short subsystem scope note. A re-offense's `lesson` and each `rejected_lessons` entry are short
  slugs; `failing_artifact` names the artifact that failed to prevent it.
- `effectiveness` is the **Step 2.5 tally** — the three buckets that step already
  produces, one count each, over every `failure-modes.md` bullet and memory entry it
  classified. It is the loop's only outcome measure: every other field counts what this
  run WROTE, and these count whether what earlier runs wrote actually held.
  `re_offended` MUST equal `len(re_offenses)` — the same events, once as a count and
  once in detail. Omit the whole field only if Step 2.5 genuinely classified nothing;
  do NOT write zeros to fill it, because a zero denominator and a real one are read
  differently downstream.
- `escalated_to` MUST be one of the six escalation-ladder rungs — `checklist`, `memory`, `claude_md`, `skill_md`, `hook`, `script` — (the aggregator buckets anything else under `escalation_rungs_unknown`).
- `rejected_lessons` lists the slugs of any suggestions marked REJECTED this run — `/cla:codify-retro` flags a slug rejected ≥2× for retirement.
- `process_issue` is `true` when the Step 3.5 self-check found a codify-process problem (mis-routing, weak effectiveness check, workflow snag), else `false`.
- `output_chars` (optional) — the character count of the report this run appended to
  `lessons-learned.md` (the Step 6 rolling-log entry). A verbosity proxy `/cla:codify-retro` trends
  over time — a climbing mean signals the report template itself is ballooning, not a full
  session-token-spend measure. Count the appended entry text only; omit rather than estimate.
- This step is best-effort. If `log_run.py` refuses the record, rebuild it from the example above, fixing every field its one-line message names, and pipe it again, **once**. If it is refused again, or fails for any other reason (write failure, the size ceiling), note it and continue — a missing ledger line never blocks the run. Do NOT halt.

## Prefer-fixes trigger examples

Triggers — if any of these match, propose a config/tooling-level fix (not just a doc/memory entry):

- The dev server "started" but wasn't actually serving on its expected port, or a stale process / port kept serving outdated state → capture the recovery steps (identify the stale listener, kill it, restart) so the next run doesn't rediscover them, rather than re-diagnosing by hand each time. See `cla.io/project-facts.md` ("Dev / build / test commands", "Ports") for this repo's own dev-server command + port (falls back to `cla.io/overlays/codify-learnings.md` if absent).
- A type or lint error slipped through because the workspace-wide build/lint gate wasn't run before declaring done → make the verification step explicit in the relevant doc/skill so it can't be skipped. See `cla.io/project-facts.md` ("Dev / build / test commands") for this repo's own build/lint commands (falls back to `cla.io/overlays/codify-learnings.md` if absent).
- A scripted UI smoke test drifted from the UI (e.g. it keys off a string that a copy change renamed) → propose the fix to the smoke script itself so it tracks the UI, not just a note about it. See `cla.io/project-facts.md` ("Test-file locations") for this repo's own smoke-script names (falls back to `cla.io/overlays/codify-learnings.md` if absent).
- (Only where `references/plugin-writability.md` answers writable — a fan-out of `SKILL.md` edits is exactly what a read-only install discards.) A SKILL.md edit is justified by a *shared* tool reference or shared workflow → grep sibling SKILL.md / command files for the same reference and propose the edit for **all** matching artifacts in one batch, not just the one in scope. Don't wait for the user to ask "would the same change apply to others?"
