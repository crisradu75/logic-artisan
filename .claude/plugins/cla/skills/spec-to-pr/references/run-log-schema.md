# spec-to-pr — per-run JSONL log schema

Handoff step 5 serializes the in-context phase outcomes as a single JSON object and pipes it to
`lib/log_run.py`, which appends it to `cla.io/retro/spec-to-pr-runs.jsonl`. This file is the
data source for `/cla:spec-to-pr-retro`.

`aggregate.py` is the consumer. **The schema below lists every field it actually reads** — adding
fields the aggregator doesn't consume is dead weight (drop them rather than carry them). Exception:
`change`, `mode`, and `args` are identification-only fields — not read by the aggregator, kept so a
human (or a future heuristic) can attribute a ledger line to a specific run. The
producer (this skill) is the contract: `aggregate.py` silently absorbs missing fields, so a missing
field is a silent loss of retro signal, not an error.

## Invocation

```bash
python3 .claude/plugins/cla/lib/log_run.py spec-to-pr-runs.jsonl <<'JSON'
{
  "ts": "<ISO-8601 UTC, e.g. 2026-05-28T14:32:11Z>",
  "change": "<change-name>",
  "mode": "<description|explore-result|existing-change>",
  "args": {"review_rounds": N, "test_rounds": N, "pr_rounds": N, "auto": true|false},
  "phases": [
    {"name": "Propose",   "status": "ok|warn|skip|fail", "reason": "<required iff warn/fail>",
     "report_chars": N},
    {"name": "Review",    "status": "...", "rounds_used": N, "rounds_cap": N,
     "size_gate": "small|large", "verdict": "READY|FIX FIRST|RETHINK",
     "verified_claims_count": N,
     "agents": ["design", "task", "spec"],   /* large mode only — omit in small */
     "reason": "<iff warn/fail>", "report_chars": N},
    {"name": "Implement", "status": "...", "reason": "<iff warn/fail>", "report_chars": N},
    {"name": "Test",      "status": "...", "rounds_used": N, "rounds_cap": N,
     "reason": "<iff warn/fail>", "report_chars": N},
    {"name": "Ship",      "status": "...", "version_bumped": true,
     "reason": "<iff warn/fail>", "report_chars": N},
    {"name": "Revise",    "status": "...", "rounds_used": N, "rounds_cap": N,
     "agents": ["code-reviewer", "silent-failure-hunter", ...],
     "reason": "<iff warn/fail>", "report_chars": N},
    {"name": "Archive",   "status": "...", "reason": "<iff warn/fail>", "report_chars": N},
    {"name": "Handoff",   "status": "ok", "report_chars": N}
  ],
  "asks": [{"header": "<header>", "choice": "<chosen-option-label>"}],
  "deferred_to_todo": N,
  "routing": {
    "models": {"opus": N, "sonnet": N, "haiku": N},
    "implement_delegated": true|false,
    "escalate_up_fired": true|false,
    "revise_findings_by_tier": {
      "code-reviewer":         {"found": N, "phantom": N},
      "silent-failure-hunter": {"found": N, "phantom": N},
      "type-design-analyzer":  {"found": N, "phantom": N},
      "pr-test-analyzer":      {"found": N, "phantom": N},
      "comment-analyzer":      {"found": N, "phantom": N}
    }
  }
}
JSON
```

Counts only, no prose — prose lives in the transcript and the PR body. The record must stay under
4 KiB so the direct `open("ab")` append remains atomic against concurrent runs (the script enforces
this; oversize records exit 1).

## Field obligations

- `reason` is REQUIRED on any phase with `warn`/`fail` status — the only signal `aggregate.py` has
  into *why* a phase warned. `/cla:spec-to-pr-retro` cannot propose a fix for an unnamed reason.
- On Ship: `version_bumped` reflects whether this repo has a version-bump preflight (e.g. a
  `plugin.json`/version-manifest artifact bumped in-PR) as part of Ship. When the repo has no such
  artifact, Ship has no version-bump preflight and the field is retained at a constant value only so
  `aggregate.py`'s `version_bump_misses` metric stays schema-compatible. See `references/project-context.md`
  for this repo's concrete answer.
- On Review: `size_gate` (`"small"` or `"large"`) and `verdict` (`"READY"` / `"FIX FIRST"` /
  `"RETHINK"`) are ALWAYS required, in both small and large mode. Unknown strings get bucketed into
  `review_size_gate_unknown` / `review_verdicts_unknown` and surface as drift.
- On Review: `verified_claims_count` is required (the retro skill's "Verified-claims section going
  silent" heuristic depends on it).
- `report_chars` (every phase, optional-additive) — the character count of THIS phase's final
  user-facing report text (the printed summary shown to the user for that phase, not the internal
  reasoning or any sub-agent transcript). A cheap verbosity proxy that `aggregate.py` computes per
  phase (`report_chars.<Phase>.mean`) — it approximates the phase's *printed-report* cost, not full
  session token spend (which isn't observable from in-context). Omit entirely rather than guess; a
  missing value is silently excluded from that phase's mean, same as every other optional field (a
  present-but-malformed value is excluded too, but counted separately under `report_chars_coerced`
  so the two cases stay distinguishable). Most phases run under this skill's one-sentence-per-phase-
  transition rule (no headers/bullets outside the Handoff terminal report — see `SKILL.md`), so
  Implement/Ship/Archive should sit near a small, near-constant floor; only Propose/Review/Handoff
  carry substantial variable-length content. A climbing mean on a low-narration phase more likely
  signals that one-sentence rule being violated than genuine prose growth.
- On Review: `agents` is REQUIRED in large mode (must contain `["design", "task", "spec"]` or
  equivalent) and MUST be omitted (or empty `[]`) in small mode. Inconsistency between `size_gate`
  and `agents` is counted as `review_gate_pair_mismatches` — non-zero means the producer is buggy.
- On Revise: `agents` lists every agent dispatched. Duplicates within a list are counted once
  (deduped with a stderr warning) — emit each agent once. **Log each agent under its EXACT canonical
  id from this fixed list** (do NOT log the `pr-review-toolkit:`-prefixed `subagent_type` you pass to
  `Agent` — the ledger key is the bare name for those): `code-reviewer`, `silent-failure-hunter`,
  `pr-test-analyzer`, `comment-analyzer`, `type-design-analyzer` (all **bare**), and
  `plugin-dev:skill-reviewer` (**prefixed** — it has no bare form). Inconsistent names (e.g.
  `code-reviewer` in some runs, `pr-review-toolkit:code-reviewer` in others) split one agent across
  two ledger keys and corrupt `/cla:spec-to-pr-retro`'s dispatch counts.

### `routing` object (model-routing telemetry)

Added by `references/model-routing.md`'s routing rules. **Entirely optional and additive** — records
predating it omit it and `aggregate.py` absorbs their absence silently (each rate's denominator counts
only records that carried the relevant field, NOT `runs_analyzed`, so legacy runs never dilute the
ratios). Emit it whenever any routed dispatch happened in the run.

- `models`: per-dispatch tally of which model ran each dispatched agent across the whole run —
  **every routed dispatch counts**: the Revise round-1 `Workflow` fan-out, every Revise round-≥2
  `Agent` dispatch, the Implement delegate, and any escalate-up dispatch. (Same scope as the hoisted
  routing rule in SKILL.md — if it got a `model:`, it gets counted, whether via `Agent(model:)` or
  `Workflow`'s `agent(..., {model})`.) Keys are canonical model names — **`opus` / `sonnet` / `haiku`
  only**; any other string lands in `routing_models_unknown` and reads as producer drift. Count each
  dispatch once. All counts in `routing` are non-negative — the aggregator rejects negatives with a
  warning.
- `implement_delegated`: `true` iff the Implement phase delegated to a coding sub-agent (the sized
  trigger fired — see `model-routing.md`); `false` iff it ran inline. Omit only if Implement did not
  run at all.
- `escalate_up_fired`: `true` iff the session was below Opus AND the Review-verdict escalate-up
  dispatch happened (a RETHINK-borderline verdict seconded by an opus `Agent`); `false` on an Opus
  session or when no escalation was needed.
- `revise_findings_by_tier`: **per-AGENT** count of Revise findings, keyed by the SAME canonical
  agent ids the Revise `agents` list uses (`code-reviewer`, `silent-failure-hunter`,
  `type-design-analyzer`, `pr-test-analyzer`, `comment-analyzer`, `plugin-dev:skill-reviewer`) —
  emit only the agents that were dispatched. Per agent: `found` = the Critical+Important findings it
  surfaced (Suggestions are NOT counted — they flow to `TODO.md` and are not a per-agent quality
  signal); `phantom` = of those `found`, how many were disproven during triage (the agent claimed a
  bug that verification refuted). This is the load-bearing signal `/cla:spec-to-pr-retro`'s per-agent
  YIELD heuristic reads (`aggregate.py`'s `revise_findings`): an agent dispatched on ~every run but
  with near-zero `found`/run is a trim-the-trigger candidate, and a phantom rate concentrated on one
  agent flags a bug-hunter whose accuracy is slipping.
  **Schema pin (2026-07-18):** this field is keyed per-AGENT. It previously appeared in two other,
  mutually-incompatible shapes — legacy **model-tier** (`opus`/`sonnet`/`haiku`) and legacy
  **severity** (`critical`/`important`/`suggestion`/`phantom_rejected`) — which made the field
  impossible to aggregate (its keys changed meaning row to row). `aggregate.py` now consumes ONLY the
  per-agent shape and counts every genuine legacy-shape record (all keys drawn from the model-tier or
  severity sets) under `revise_findings_legacy_records` so the drift stays visible; do not emit either
  legacy shape. Anything that is NEITHER per-agent NOR a genuine legacy shape — a non-dict field, an
  unknown/misspelled agent key, or an agent key with a non-dict value — counts under
  `revise_findings_malformed_records` with a stderr warning (it is current-producer drift, not benign
  history, so it must not hide in the legacy bucket). An empty `{}` (a Revise round that found nothing)
  counts in NO bucket — legitimate "no data," not a shape error. Underscore agent keys (`code_reviewer`)
  are tolerated by the aggregator (normalized to hyphens) but hyphens are canonical — match the `agents`
  list. `found`/`phantom` are trusted as producer-filtered to Critical+Important; the aggregator does
  not re-derive severity, so honoring the "Suggestions excluded" rule above is a producer obligation.

(The orchestrator's runtime handling of a `log_run.py` failure — non-fatal, capture stderr but do
not warn the whole run — is stated inline in `SKILL.md` Handoff step 5.)
