# spec-to-pr — per-run JSONL record

Handoff pipes one JSON object per run to `lib/log_run.py`, which appends it to
`cla.io/retro/spec-to-pr-runs.jsonl`; `/cla:spec-to-pr-retro` reads it through
`spec_to_pr_aggregate.py`. Build the record from the example below. `log_run.py` checks it against
`SHAPES` in that file and refuses an off-shape record, naming every field that is off; the retry
rule is in `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/handoff.md` §5. This file says what
each field MEANS; where the two disagree, the code is right.

## Invocation

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/log_run.py spec-to-pr-runs.jsonl <<'JSON'
{
  "ts": "2026-05-28T14:32:11Z",
  "change": "<change-name>",
  "mode": "description",
  "flags": ["--inherits", "--pr-rounds"],
  "phases": [
    {"name": "Propose",   "status": "ok"},
    {"name": "Review",    "status": "ok", "rounds_used": 1, "rounds_cap": 1},
    {"name": "Implement", "status": "ok"},
    {"name": "Test",      "status": "warn", "rounds_used": 2, "rounds_cap": 3,
     "reason": "<why it warned>"},
    {"name": "Ship",      "status": "ok"},
    {"name": "Revise",    "status": "ok", "rounds_used": 2, "rounds_cap": 2,
     "findings_by_round": [{"round": 1, "found": 3}, {"round": 2, "found": 1}]},
    {"name": "Archive",   "status": "ok"},
    {"name": "Handoff",   "status": "ok"}
  ],
  "escalated_to_diagnose": 0,
  "asks": [{"header": "<header>", "choice": "<chosen-option-label>"}],
  "routing": {
    "revise_findings_by_tier": {
      "code-reviewer":         {"found": 2, "phantom": 0},
      "silent-failure-hunter": {"found": 1, "phantom": 0}
    }
  }
}
JSON
```

Shapes the check holds you to, most often missed from memory: `ts` is a date-time with a zone, never
a bare date and never a `date` key; `phases` is a LIST of objects in run order, each with `name`
(capitalised, as above) and `status` (`ok` / `warn` / `skip` / `fail`); counts are integers, never
strings or booleans; `flags` and `asks` are lists. Counts only — no prose, and under 4 KiB, so the
append stays atomic against a concurrent run.

## What each field means

- `ts` — when the run ended, UTC. `change`, `mode` — the change and how it was entered
  (`description`, `explore-result` or `existing-change`).
- `flags` — every flag the run was invoked with, by name as typed and without its value
  (`"--pr-rounds"`, not `"--pr-rounds 1"`); `[]` when there were none. The retro counts how often
  each flag is used.
- `reason` — on every `warn` / `fail` phase: the retro's only signal into *why*, grouped by exact text.
- `rounds_used` / `rounds_cap` — always as a pair. Required on Test and Revise whenever their status
  is not `skip`; optional on Review. A phase that used its whole cap, with a cap above 1, is a cap
  exhaustion — on Revise, whose round 2 is routine, only when it also ended `warn` or `fail`.
- Revise: `findings_by_round` — one entry per round, built as each round closes, never
  reconstructed at Handoff. `found` is that round's deduplicated Critical+Important count after
  triage. The retro's round-2 yield reads it.
- `escalated_to_diagnose` — how many times the run escalated to `/cla:diagnose` (Test's
  same-cause rule, or anywhere else); `0` when it never did.
- `asks` — every user ask in the run, by header and chosen label.
- `routing.revise_findings_by_tier` — per Revise agent dispatched, by canonical id:
  `code-reviewer`, `silent-failure-hunter`, `pr-test-analyzer`, `comment-analyzer`,
  `type-design-analyzer` (bare — not the `pr-review-toolkit:` form you pass to `Agent`) and
  `plugin-dev:skill-reviewer` (prefixed; it has no bare form); the check refuses any other key.
  `found` = Critical+Important findings it surfaced — Suggestions excluded — and `phantom` = how
  many of those triage disproved. It credits a finding to every agent that raised it, so its
  `found` total is usually at least `findings_by_round`'s; a finding the orchestrator raised itself
  lands only in the latter.
