---
name: spec-to-pr-retro
description: "Review recent /cla:spec-to-pr runs and propose concrete improvements to the orchestrator (SKILL.md, hooks, memory). Reads the project's runs JSONL log, aggregates deterministic metrics (phase warn rates, cap exhaustion, Review size-gate distribution, Review verdict mix, agent dispatch frequency, ask choice distribution), then surfaces patterns and proposes specific edits. Triggers on /cla:spec-to-pr-retro or natural language like 'review my recent spec-to-pr runs', 'how is spec-to-pr doing', 'what should I fix in spec-to-pr'."
argument-hint: "[N (last N runs, default 10)]"
---

# /cla:spec-to-pr-retro — retrospective on the orchestrator

Reviews the repo's `cla.io/retro/spec-to-pr-runs.jsonl` log and proposes targeted improvements. The data is captured by `spec-to-pr`'s Handoff phase via `log_run.py` — one JSON line per run, counts-only (no prose; prose lives in transcripts and PR bodies). The ledger is committed to the repo so it syncs across machines via git (override the dir with `CLAUDE_RETRO_DIR`).

## When to invoke

- After ~5+ /cla:spec-to-pr runs have accumulated (smaller windows are noisy).
- When the orchestrator's behavior feels off (too many warns, too many cap exhaustions, too many user asks).
- Periodically as part of repo hygiene.

## Workflow

**Read `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/retro-skeleton.md` first** — it carries the
five workflow steps, the report shape, the apply-gate, and the sources-of-truth list that every
retro shares. This body supplies only what is specific to the orchestrator loop: the aggregate
command and the interpretation heuristics.

### 1. Read the aggregated metrics

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr-retro/scripts/spec_to_pr_aggregate.py --limit <N>
```

Where `<N>` is the value from `$ARGUMENTS` (passed through by the command wrapper), or `10` if `$ARGUMENTS` is empty. Substitute the literal number before invoking — the script does not expand shell variables.

Output is a single JSON object on stdout — phase outcomes, warn reasons, cap exhaustion rates, mean rounds used, per-agent finding rates, ask choice distribution, version-bump miss count, deferred-to-TODO totals.

If `runs_analyzed: 0`, the log doesn't exist yet — say so, stop. The user needs to run `/cla:spec-to-pr` a few times first.

### 2. Identify the load-bearing patterns

Don't list every metric. Pick the 2-4 patterns that would actually change orchestrator behavior. Heuristics for what counts as load-bearing:

**Workflow heuristics:**
- Cap exhaustion ≥30% on a loop (`cap_exhaustion.<phase>.hit / .total`) → default cap too low for the changes this project ships. Note: the aggregator only counts a hit when `cap > 1` (a single-pass phase like Review with default cap 1 reaches its cap trivially every run — that is not exhaustion and is excluded), so a high `review` rate here is real, not an artifact.
- A phase warns on ≥40% of runs (`phase_outcomes.<phase>.warn / runs_analyzed`) → the warn reason in `warn_reasons` tells you what to harden.
- An agent dispatches on <20% of runs (`revise_agents.<name>.dispatches / runs_analyzed`) → narrow trigger; decide whether by design or drift.
- An agent dispatches on every run → expected baseline (`code-reviewer`, `silent-failure-hunter`); no action on dispatch count alone — check its *yield* (next).
- **Per-agent yield (dispatch vs. found).** An agent dispatched on ~every run BUT with low per-run yield (`revise_findings.<name>.found / .runs` well below the two bug-hunters') is a trim-the-trigger candidate — it's spending tokens for little severity-weighted signal. This is exactly how the `type-design-analyzer` / `comment-analyzer` triggers were narrowed (they ran on every change but produced mostly precedent-noise on purely-additive ones). Trust this only over `revise_findings_records` — if `revise_findings_legacy_records` dominates the window (older runs, pre-schema-pin), the yield sample is too thin to act on. And `found` is producer-filtered to **Critical+Important only** (Suggestions are excluded at the producer, per the run-log schema) but is not split *between* those two: a high count can be all Important with zero Critical, so spot-check one PR before recommending a trim.
- One ask answered the same way ≥80% of times (`asks[].choices`) → make the default silent, remove the prompt.
- `version_bump_misses` recurring → preflight check should be stricter or auto-bump. (Inert when the repo has no `plugin.json`/version manifest to bump: Ship then logs `version_bumped: true` every run and this metric stays 0 — ignore it in that case.)
- Same warn reason recurring (`warn_reasons` top entries) → feature request, not a per-run issue.

**Routing heuristics (telemetry → concrete `model-routing.md` edits).** The `routing` object exists so metrics can *steer routing*, not just describe it — turn these into specific table edits, not vague "consider tuning." Each rule names a threshold and the edit it justifies:

- **Non-bug-hunter phantom rate ≥ 0.4 over ≥5 dispatches** (`revise_findings.<agent>.phantom / .found` for `comment-analyzer` / `pr-test-analyzer` / `type-design-analyzer` / `plugin-dev:skill-reviewer`) → that agent is spending triage cost on wrong findings at its current tier. Propose either **demoting it one tier** in `model-routing.md`'s Revise table (if it isn't already at haiku) OR **tightening its trigger** (the yield lever above) — pick demotion when its `found` yield is otherwise healthy, trigger-tightening when yield is also low.
- **Bug-hunter phantom rate ≥ 0.3 over ≥5 dispatches** (`code-reviewer` / `silent-failure-hunter`) → these are **never demoted** (phantom-finding economics), so this instead flags an *accuracy* problem: propose a manual spot-check of 2 recent runs and, if confirmed, a prompt/diff-slice tightening — NOT a model change. A rising bug-hunter phantom rate is the standing check on the never-demote bet (see `model-routing.md` rationale); surface it explicitly rather than letting it hide.
- **`escalate_up_fired: true` on ≥50% of sub-Opus runs** (of runs where it *could* fire — the denominator is runs that reached the FIX-FIRST/RETHINK boundary, not `runs_analyzed`) → borderline verdicts are common enough on this project that the escalate-up dispatch is effectively always-on when sub-Opus. Propose either making the Design-Reviewer `opus` dispatch the default for large changes regardless of session model, or noting that this project's runs should just launch at Opus (the escalate-up cost is being paid every run anyway).
- **A tier is never exercised** (`routing.models.opus == 0` across the window while large-change reviews ran, or `haiku == 0` while `comment-analyzer` dispatched) → the producer may not be routing per the table (models emitted don't match the table's tiers). Cross-check against `routing_models_unknown`; if that's clean, the routing rule itself is being skipped — restate it in the hoisted SKILL.md rule.

(Effort itself is only dialable on the Revise round-1 `Workflow` fan-out — see `model-routing.md`'s mechanism table — so an "effort too low" pattern can only be acted on there; everywhere else the lever is the *model* tier or the session model, not effort.)

**Review-phase heuristics:**
- `review_size_gate.large / runs_analyzed ≥ 0.6` → small-change gate (a≤5 ∧ b≤20 ∧ c=1) no longer captures modal change shape. Bump thresholds.
- `review_verdicts.READY / runs_analyzed ≥ 0.8` with low aggregate `important` counts → checklist may be weakening. Spot-check 2 recent READY PRs by hand; restate any retired check.
- `review_verdicts.RETHINK / runs_analyzed ≥ 0.2` → design conversations starting too late. Hoist recurring RETHINK triggers into a `/opsx:propose` pre-check.
- `review_verified_claims.mean < 3` AND `review_verified_claims.n ≥ runs_analyzed / 2` → `### Verified claims` section going silent. Restate "≥3 positive verifications" rule. (Ignore when `n` is small — mostly nulls poisoning the mean.)

**Schema-integrity heuristics (act before trusting the others):**
- `skipped_records > 0` → producer is writing malformed JSONL; the rest of the analysis runs on a shrunken sample.
- `review_size_gate_unknown` / `review_verdicts_unknown` non-empty → producer is emitting values outside the whitelist; rates above are computed against the whitelisted subset only.
- `review_gate_pair_mismatches > 0` → producer is emitting size_gate/agents inconsistently; agent dispatch counts may be miscounted on the affected runs.
- `review_agents_unknown_types` / `revise_agents_unknown_types` non-empty → producer is putting non-strings in the `agents` list.
- `revise_findings_malformed_records > 0` → the producer is emitting `routing.revise_findings_by_tier` in a shape that's neither the pinned per-agent form nor a known legacy shape (a non-dict field, an unknown/misspelled agent key, or an agent key with a non-dict value). Unlike `revise_findings_legacy_records` (benign pre-pin history), this is CURRENT drift — fix the producer's serialization (`run-log-schema.md`). Each malformed record also printed a stderr warning naming the record index.

If schema-integrity rows are non-zero, fix the producer (`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/run-log-schema.md` field obligations or the orchestrator's serialization) BEFORE acting on workflow heuristics — those rates may be computed against a partly-poisoned window.

(Per-agent finding YIELD is now logged and surfaced — `revise_findings.<agent>` carries `found`/`phantom`/`runs` from the pinned per-agent shape of `routing.revise_findings_by_tier` (schema pinned in `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/run-log-schema.md`; before the pin the field appeared in two other, mutually-incompatible shapes — model-tier and severity — which `spec_to_pr_aggregate.py` counts under `revise_findings_legacy_records` and excludes from yield). Join `revise_findings` with `revise_agents.<agent>.dispatches` for the dispatch-vs-yield picture. `found` is Critical+Important combined (Suggestions excluded at the producer) but not split between the two — a high count could be all Important, so verify the actual severity in the PR before acting on a low-yield trim.)

Single-digit run counts in a category mean "interesting anecdote, not a pattern" — call them out as such, don't propose changes.

### 3-5. Propose, report, and optionally apply

Per the shared skeleton. Worked examples in this loop's own vocabulary:

- ❌ "Review is too slow."
- ✅ "In `spec-to-pr/SKILL.md`'s Review size gate, lower the large-change threshold to `a > 4` — 7 of 12 runs gated Small and then surfaced Important findings in Revise (`review_gate: small` with `revise_findings >= 3`)."

The usual apply targets are `spec-to-pr/SKILL.md`, its `references/*.md`, and the shared
`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`.

## When NOT to use

Per the shared skeleton's "When NOT to use a retro". This loop's threshold is ~5 `/cla:spec-to-pr` runs.
