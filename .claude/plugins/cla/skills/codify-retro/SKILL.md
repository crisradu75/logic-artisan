---
name: codify-retro
description: "Review recent /cla:codify-learnings runs and propose concrete improvements to the loop itself (codify-learnings/SKILL.md, references/failure-modes.md, the escalation ladder). Reads the project's codify-runs JSONL log, aggregates deterministic metrics (the prevention rate — whether the lessons earlier runs wrote actually held — plus suggestion apply-rate, lessons that re-offend across runs, escalation-rung distribution, repeatedly-rejected lessons, failure-modes bloat, codify-process-issue rate), then surfaces patterns and proposes specific edits. Triggers on /cla:codify-retro or natural language like 'review my recent codify runs', 'how is codify-learnings doing', 'what should I fix in codify-learnings'."
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


**Reading more than one repo's ledger.** Prefer `--fleet`, which resolves the paths from `cla.io/fleet.local.md` — one repo root per `- ` bullet, curated per machine, never synced:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/codify-retro/scripts/codify_aggregate.py --limit 0 --fleet
```

`--log` still takes several explicit paths, and the two are mutually exclusive — both resolve the same argument, so accepting both would make precedence a guess the caller cannot see:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/codify-retro/scripts/codify_aggregate.py --limit 0 \
  --log <repo-a>/cla.io/retro/codify-runs.jsonl <repo-b>/cla.io/retro/codify-runs.jsonl
```

**Why the file exists rather than just typing the paths.** The multi-path form came first, and the list lived nowhere — so the cross-repo view existed only when someone remembered every repo and spelled each one right. A path that resolves to nothing contributes silently, which is the same sample-size error fleet mode exists to remove. If `--fleet` reports a missing file or one with no bullets, it refuses rather than analysing nothing: `runs_analyzed: 0` is what this skill tells you to read as a cold start.

Worth doing whenever one repo's ledger is thin, which is the usual case — this repo's 8 spec-to-pr records put one round-cap exhaustion rate at 4 of 5 where the fleet's 156 put it at 6 of 129. Three things change in fleet mode, and each is visible in the output rather than assumed: `--limit` applies PER LEDGER, so `runs_analyzed` can reach N x ledgers; `ledgers` carries per-path provenance, and a path that did not resolve shows `found: false` with `records: 0` — check it before trusting the sample size; and `log_path` is omitted, since no single path describes the result.

One caveat specific to this loop: the per-repo maintenance fields — `failure_modes_bullets_latest`, its trend, `live_log_entries_latest`, and `output_chars` — describe ONE repo's own files, so they are suppressed in fleet mode and the output carries `per_repo_fields_suppressed: true`. The loop-hygiene heuristics below need a single-ledger run.

The effectiveness and rung heuristics do not, and here is the argument rather than the assertion this line used to carry. Those fields count **events** — a rule was exercised and held, or it failed; a lesson was escalated to a rung — and events from different repos add up, where file sizes do not. What pooling costs is the weighting, which you must read alongside the number: the total is dominated by whichever repo contributed the most runs, so a pooled `prevention_rate` describes **the fleet's sessions**, never a typical repo. Two consequences: one repo's problem can hide inside a healthy fleet number, and a fleet number cannot justify an edit aimed at one repo. When a heuristic fires on a fleet run, re-run the ledgers singly before acting, and check the `ledgers` provenance rows for a path that resolved to nothing.

Output is a single JSON object on stdout — the prevention rate, suggestion apply-rate, re-offending lessons, escalation-rung
distribution, repeatedly-rejected lessons, failure-modes bullet trend, codify-process-issue rate.

**Reading the commit-provenance ledger.** `--provenance` takes one or more `cla.io/retro/commit-provenance.jsonl` paths and adds a `commit_provenance` block:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/codify-retro/scripts/codify_aggregate.py --limit 0 \
  --provenance <repo-a>/cla.io/retro/commit-provenance.jsonl <repo-b>/cla.io/retro/commit-provenance.jsonl
```

Given **bare**, it resolves for you: with `--fleet`, every listed repo's provenance ledger; without it, this repo's.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/codify-retro/scripts/codify_aggregate.py --limit 0 --fleet --provenance
```

That ledger is written automatically by a guard hook on every commit, at no cost in anyone's attention, and until this flag existed nothing read it. It is independent of `--log` — pass either, or both — and it is never sliced by `--limit`, because adoption of a commit-message rule is a property of the whole history rather than of the last N runs.

### 2. Identify the load-bearing patterns

Don't list every metric. Pick the 2-4 patterns that would actually change the loop. Heuristics:

**Effectiveness heuristics (the whole point):**
- **Read `effectiveness.records` first.** It is how many runs carried a Step 2.5 tally at all. If it is `0`, the loop is not yet reporting outcomes and every rate below is unmeasured — say so plainly rather than reading `prevention_rate: null` as bad news. If it is well under `runs_analyzed`, the rate is drawn from that subset, not the window.
- `effectiveness.prevention_rate` is the share of rules that were actually exercised and **held** — the loop's one outcome measure. Below `0.5` over a window with `records ≥ 5` → escalations are not sticking; the lessons are landing on rungs too weak to change behaviour. Falling across two windows is the same signal, earlier. Rising while `suggestions.proposed` stays flat is the loop working.
- **Rows written before 2026-09-06 UNDERSTATE the rate, and by a lot — do not trend across that boundary.** The hook read `Measured-by:` as a git trailer, and git recognises only the LAST contiguous `Key: value` block; every commit ends with attribution lines, so a blank line between the measurements and those made the measurements invisible. Measured on the day it was found, by re-reading the commit messages themselves: the fleet's ledger said 59 of 228 (0.26) where the messages said 133 (0.58), and one repo logged 0.0 against a real 0.67. The hook now scans the whole message. A rate that appears to jump at that date is the fix landing, not behaviour changing.
- **`commit_provenance.measurement_rate`** (only present when you pass `--provenance`) is the same effectiveness question asked of a rule the loop already escalated — "name the command behind a measurement claim" — but counted by a hook rather than self-reported, which is what makes it worth reading beside `prevention_rate`. Below `0.5` → the rule is stated in `CLAUDE.md` and a consistency guard and is still not reaching commits; that is a routing problem, not a reminder problem. Read `no_trailer_field` next to it: those rows predate the trailer and are excluded from the denominator on purpose. `by_skill` shows which skill drove each commit, so a rate that is poor only where `skill` is `none` means the orchestrated paths are fine and hand-driven commits are the gap.
- **`apply_rate` is not an effectiveness signal, and reading it as one is the failure this metric exists to correct.** It says the user agreed, not that the writing worked. Measured 2026-09-05 with `codify_aggregate.py --limit 0 --fleet` over seven listed repo roots, five of which held records: 219 proposed, 219 applied, 0 rejected — a perfect score that measured nothing. Quote `prevention_rate` where you would once have quoted `apply_rate`.
- A lesson in `re_offenses` with `count ≥ 2` → the artifact it was escalated to is **too weak**; the escalation isn't working. Bump it UP the ladder (memory → hook/script). This is the single most important signal — a re-offense means the prior fix failed.
- A lesson in `rejected_lessons` with `count ≥ 2` → stop proposing it; **retire** it from `${CLAUDE_PLUGIN_ROOT}/skills/codify-learnings/references/failure-modes.md` (the SKILL.md's Step 6 already says to flag these — verify it's actually happening).
- `suggestions.apply_rate == 1.0` with `suggestions.proposed ≥ 10` → **the gate is not gating.** This reads as the alarm, not the target — inverted deliberately when codify-learnings' Step 4 dropped its "apply all" default, because a gate that never refuses anything is measuring the prompt's shape rather than the suggestions' quality. Check that Step 4 is still prompting for indices with no default, and that Step 3's 3-item cap and cite-a-this-session-failure bar are actually being applied. A rate somewhere below 1.0 is the healthy state; a low rate is only a problem if `prevention_rate` is also poor, which means the ones being applied are not working either.
- `suggestions.proposed / runs_analyzed > 3` → Step 3's cap is being exceeded. The cap is a hard ceiling on ranking, not a target to fill.

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
- `shape_drift_records > 0` → some records lost a field the metrics are computed from, so `runs_analyzed` overstates the sample those metrics actually ran on. `shape_drift_fields` names which field drifted and how often. **This aggregator can only ever report eight of them** — `suggestions`, `memory`, `effectiveness`, `re_offenses`, `rejected_lessons`, `maintenance`, `process_issue` and `ts` — and each is a real key you can grep for in `codify-runs.jsonl`. (Derive it rather than trusting this list: `grep -n 'drifted_fields.add\|drifted.add' codify_aggregate.py`. The list said seven and omitted `process_issue` for one commit, which is the failure the sentence below describes, committed inside the sentence describing it.) (This sentence used to list `phases`, `asks`, `warn_reasons`, `review_agents`, `revise_agents`, `review_size_gate` and `review_verdicts`, copied from the spec-to-pr retro. None of them is a codify field, and `codify_aggregate.py` cannot emit one — a reader who went looking for them found nothing and had no way to tell whether that meant clean or broken.) Read the stderr line beside the count for the record index. Read this before any ratio below: a rate over a thinned sample reads exactly like a rate over a whole one.

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
