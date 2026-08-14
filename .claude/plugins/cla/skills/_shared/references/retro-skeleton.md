# The retro skeleton

The workflow every `*-retro` skill follows. A retro reads one loop's run ledger,
aggregates it deterministically, and proposes edits to the loop itself.

Read this file first; then read the calling skill's own body for the two things
that are genuinely per-loop: **its aggregate script path** and **its
interpretation heuristics** (which metrics matter, and what a given value means).
Everything below is identical across retros by design — when it drifts, the two
loops start giving contradictory advice about the same kind of evidence.

## 1. Read the aggregated metrics

Run the calling skill's `aggregate.py` over its ledger. Pass a window when the
caller supplies one (`$ARGUMENTS` = a run count `<N>`); otherwise take the
script's default window.

**`runs_analyzed: 0` is not a finding.** It means the ledger is empty or the
window excluded everything. Say so plainly and stop — do not manufacture
patterns from no data, and do not read it as evidence the loop is healthy.

**Check schema integrity before interpreting anything.** A non-zero
`skipped_records` (or the equivalent malformed-shape bucket) means the producer
and the aggregator disagree about the record shape. Fix that first: every metric
below it is computed over a subset nobody chose.

## 2. Identify the load-bearing patterns

Pick the **2–4** patterns that would change how the loop behaves. Ignore the
rest, however interesting.

**Single-digit counts are an interesting anecdote, not a pattern.** Say which
they are rather than quietly promoting them.

## 3. Propose specific edits

Name the artifact and the edit, not a vague direction.

- ❌ "Improve how the skill handles X."
- ✅ "In `<skill>/SKILL.md` step 4, add: `<the exact rule>` — 6 of 11 runs hit
  this (`metric_name: 6`)."

Cite the metric in parentheses on every proposal. A proposal with no metric
behind it is an opinion, and this skill exists precisely to replace those.

## 4. Output shape

Render a Markdown report with three sections, in this order:

1. **Window** — runs analyzed, date range.
2. **Patterns** — the 2–4 load-bearing patterns, one paragraph each, with the
   metric in parens.
3. **Proposed edits** — numbered list. Each entry: target file + section, the
   specific change, the metric that justifies it.

Keep the whole report under ~40 lines. Long retros don't get acted on.

## 5. Optional: invite the user to apply edits

**Check first whether the plugin is writable here** — the procedure is in
`${CLAUDE_PLUGIN_ROOT}/skills/codify-learnings/references/plugin-writability.md`.
Every target a retro proposes lives inside the plugin. When the plugin is
installed from a marketplace that tree is a read-only, version-keyed cache: an
edit either fails or lands somewhere the next update discards, **while reporting
as applied**. If it is read-only, do not offer to apply — present the findings and
route them to **`/cla:report-upstream`**, which files them against the canonical
source where they can change the loop for every repo.

End with: "Want me to apply any of these? Say `apply 1,3` or list the numbers."

Do NOT apply edits without explicit confirmation — retros are advisory.
`openspec/**`, `**/scripts/**/*.py`, and vendored frameworks stay excluded per
`codify-learnings`' own rules.

## Sources of truth

- **Output schema:** the calling skill's `aggregate.py` module docstring, for the
  exact field names it emits.
- **Log format:** `${CLAUDE_PLUGIN_ROOT}/lib/log_run.py`, for what gets written
  per run.
- **What to log:** the producing skill's own "log the run" step, for the record
  schema.

## When NOT to use a retro

- For a one-off question about a single run ("why did this one propose that?") —
  read that run's own record and transcript. Aggregating one run tells you less
  than reading it.
- Before roughly 5 runs accumulate — noise exceeds signal.
- To debug the aggregator or the writer itself — that is a code-reading task, not
  a metrics task.
