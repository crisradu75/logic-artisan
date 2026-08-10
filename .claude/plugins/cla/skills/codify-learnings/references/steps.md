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

Record schema (counts-only — NO prose; the script rejects records ≥ 4 KiB):

```json
{
  "ts": "<today's date, YYYY-MM-DD, from the currentDate context>",
  "scope": "<'repo-wide' or an optional subsystem scope note>",
  "suggestions": {"proposed": N, "applied": N, "rejected": N},
  "memory": {"proposed": N, "applied": N},
  "re_offenses": [
    {"lesson": "<short slug>", "failing_artifact": "<artifact that failed to prevent it>",
     "escalated_to": "checklist|memory|claude_md|skill_md|hook|script"}
  ],
  "rejected_lessons": ["<short slug>", "..."],
  "maintenance": {"failure_modes_bullets": N, "live_log_entries": N, "trimmed": true|false},
  "process_issue": true|false,
  "output_chars": N
}
```

- `escalated_to` MUST be one of the six escalation-ladder rungs (the aggregator buckets anything else under `escalation_rungs_unknown`).
- `rejected_lessons` lists the slugs of any suggestions marked REJECTED this run — `/cla:codify-retro` flags a slug rejected ≥2× for retirement.
- `process_issue` is `true` when the Step 3.5 self-check found a codify-process problem (mis-routing, weak effectiveness check, workflow snag), else `false`.
- `output_chars` (optional) — the character count of the report this run appended to
  `lessons-learned.md` (the Step 6 rolling-log entry). A verbosity proxy `/cla:codify-retro` trends
  over time — a climbing mean signals the report template itself is ballooning, not a full
  session-token-spend measure. Count the appended entry text only; omit rather than estimate.
- This step is best-effort: if `log_run.py` exits non-zero (malformed record, write failure), note it and continue — a missing ledger line never blocks the run. Do NOT halt.

## Prefer-fixes trigger examples

Triggers — if any of these match, propose a config/tooling-level fix (not just a doc/memory entry):

- The dev server "started" but wasn't actually serving on its expected port, or a stale process / port kept serving outdated state → capture the recovery steps (identify the stale listener, kill it, restart) so the next run doesn't rediscover them, rather than re-diagnosing by hand each time. See `cla.io/project-facts.md` ("Dev / build / test commands", "Ports") for this repo's own dev-server command + port (falls back to `cla.io/overlays/codify-learnings.md` if absent).
- A type or lint error slipped through because the workspace-wide build/lint gate wasn't run before declaring done → make the verification step explicit in the relevant doc/skill so it can't be skipped. See `cla.io/project-facts.md` ("Dev / build / test commands") for this repo's own build/lint commands (falls back to `cla.io/overlays/codify-learnings.md` if absent).
- A scripted UI smoke test drifted from the UI (e.g. it keys off a string that a copy change renamed) → propose the fix to the smoke script itself so it tracks the UI, not just a note about it. See `cla.io/project-facts.md` ("Test-file locations") for this repo's own smoke-script names (falls back to `cla.io/overlays/codify-learnings.md` if absent).
- A SKILL.md edit is justified by a *shared* tool reference or shared workflow → grep sibling SKILL.md / command files for the same reference and propose the edit for **all** matching artifacts in one batch, not just the one in scope. Don't wait for the user to ask "would the same change apply to others?"
