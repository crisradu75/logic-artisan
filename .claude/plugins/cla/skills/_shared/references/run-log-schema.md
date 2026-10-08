# spec-to-pr — per-run JSONL record

Handoff step 5 pipes one JSON object per run to `lib/log_run.py`, which appends it to
`cla.io/retro/spec-to-pr-runs.jsonl`. `/cla:spec-to-pr-retro` reads it through
`spec_to_pr_aggregate.py`.

**The shape lives in code, not here.** `log_run.py` checks every record against `SHAPES` in that
file — required keys and value shapes — and refuses one that does not match, printing one line that
names every field that is off, `; `-separated (`log_run: spec-to-pr-runs.jsonl record refused:
<field> must be ...; <field> is required`), and writing nothing. On a refusal, rebuild the record
from the example below, fixing every field named, and pipe it again, **once**. If it is refused again,
or the write fails for any other reason, put the stderr line in the Handoff Issues section and
finish the run: a missing ledger line never halts it, and never marks it `warn`. This file says
what each field MEANS; where the two disagree, the code is right.

**Every field earns its place by a reader.** Add a field only when something reads it. The
aggregator reads `ts`, `change`, each phase's `status`, `reason` and rounds pair, Revise's
`findings_by_round`, `asks`, and `routing.revise_findings_by_tier`; `mode` and `args` identify the
run for a human. The rest — the Review fields, `version_bumped`, `report_chars`,
`deferred_to_todo`, `cost`, and the other `routing` keys — no aggregator reads; they serve someone
reading one run's record by hand. The check refuses a wrong shape, not a missing optional field —
leaving one out passes, and silently costs the retro that signal.

## Invocation

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/log_run.py spec-to-pr-runs.jsonl <<'JSON'
{
  "ts": "2026-05-28T14:32:11Z",
  "change": "<change-name>",
  "mode": "description",
  "args": {"review_rounds": 1, "test_rounds": 3, "pr_rounds": 2, "auto": true},
  "phases": [
    {"name": "Propose",   "status": "ok", "report_chars": 140},
    {"name": "Review",    "status": "ok", "rounds_used": 1, "rounds_cap": 1,
     "size_gate": "large", "verdict": "FIX FIRST", "verified_claims_count": 12,
     "agents": ["design", "task", "spec"]},
    {"name": "Implement", "status": "ok"},
    {"name": "Test",      "status": "warn", "rounds_used": 2, "rounds_cap": 3,
     "reason": "<why it warned>"},
    {"name": "Ship",      "status": "ok", "version_bumped": false},
    {"name": "Revise",    "status": "ok", "rounds_used": 2, "rounds_cap": 2,
     "agents": ["code-reviewer", "silent-failure-hunter"],
     "findings_by_round": [{"round": 1, "found": 3, "sibling_instance": 0},
                           {"round": 2, "found": 1, "sibling_instance": null}]},
    {"name": "Archive",   "status": "ok"},
    {"name": "Handoff",   "status": "ok"}
  ],
  "asks": [{"header": "<header>", "choice": "<chosen-option-label>"}],
  "deferred_to_todo": 0,
  "cost": {"wall_clock_minutes": 95, "model": "<the session model>",
           "agents_dispatched": 8, "escalations": 0},
  "routing": {
    "models": {"opus": 2, "sonnet": 5, "haiku": 1},
    "implement_delegated": false,
    "escalate_up_fired": false,
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
strings or booleans; `asks` is a list. Counts only — no prose, and under 4 KiB, so the append stays
atomic against a concurrent run.

## What each field means

- `ts` — when the run ended, UTC. `change`, `mode`, `args` — the change, how it was entered
  (`description`, `explore-result` or `existing-change`), and the caps it ran under.
- `reason` — on every `warn` / `fail` phase: the retro's only signal into *why*, grouped by exact text.
- `rounds_used` / `rounds_cap` — always as a pair. Required on Test and Revise whenever their status
  is not `skip`; optional on Review. A phase that used its whole cap, with a cap above 1, is a cap
  exhaustion — on Revise, whose round 2 is routine, only when it also ended `warn` or `fail`.
- `report_chars` (optional, any phase) — characters in that phase's printed report: a verbosity
  proxy, not token spend. Omit rather than estimate.
- Review: `size_gate` and `verdict` whenever the checklist ran, and `verified_claims_count`.
  `agents` lists the Review agents that ran in large mode and is omitted or `[]` in small mode —
  set it from what actually dispatched, at the moment you record `size_gate`. On an `ok` Review the
  two must agree. A gate that called for agents none could dispatch is recorded as it happened —
  `size_gate: "large"`, `agents: []` — on a `warn` Review whose `reason` says why.
- Ship: `version_bumped` — whether Ship bumped a version manifest. A repo with no version-bump
  preflight writes a constant; `cla.io/overlays/spec-to-pr.md` says which.
- Revise: `agents` lists every agent dispatched, once each, by canonical id: `code-reviewer`,
  `silent-failure-hunter`, `pr-test-analyzer`, `comment-analyzer`, `type-design-analyzer` (bare —
  not the `pr-review-toolkit:` form you pass to `Agent`) and `plugin-dev:skill-reviewer` (prefixed;
  it has no bare form). Nothing else goes in it — work the orchestrator did itself is not an agent,
  and the check refuses any other id.
- Revise: `findings_by_round` — one entry per round, built as each round closes, never
  reconstructed at Handoff. `found` is that round's deduplicated Critical+Important count after
  triage. `sibling_instance` is, of that `found`, how many were a defect the previous round's fix
  introduced or a sibling the fix missed (`revise.md`'s round-≥2 question): `0` on round 1, and
  `null` — not `0` — on a round that was never asked or whose enumeration stayed uncited. The
  retro's round-2 yield reads `round` and `found`.
- `asks` — every user ask in the run, by header and chosen label. `deferred_to_todo` — items
  persisted to `TODO.md`.
- `cost` — measured wall-clock minutes, the session model, sub-agent dispatches (the real cost
  driver), and how many were escalate-ups. Token counts are not recorded: the orchestrator cannot
  observe them, and a guessed total would poison the comparison.
- `routing` — `models`: one count per routed dispatch (the Revise fan-out and later rounds, the
  Implement delegate, any escalate-up) by `opus` / `sonnet` / `haiku`; `implement_delegated`
  (omit only if Implement did not run) and `escalate_up_fired` per `model-routing.md`.
  `revise_findings_by_tier`: per canonical agent id (the same ids as Revise `agents`; only agents
  dispatched), `found` = Critical+Important findings it surfaced — Suggestions excluded — and
  `phantom` = how many of those triage disproved. This is the per-agent yield the retro reads.
  It credits a finding to every agent that raised it, so its `found` total is usually at least
  `findings_by_round`'s; a finding the orchestrator raised itself lands only in the latter.
