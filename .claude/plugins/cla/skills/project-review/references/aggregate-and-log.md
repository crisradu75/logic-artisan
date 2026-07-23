# Project Review — Snapshot, Aggregation, Report Template, and Retro Log

**Mandatory read** for Step 1 (before building the Project Snapshot) and Step 3 (before printing the
report or appending the retro-log line). `SKILL.md` keeps only the verdict rubric inline; this file is
the full recipe for everything else in those two steps.

## Step 1 — Project Snapshot template

The shape below is a generic template — fill the `Apps`/`Packages`/`Backend` lines from
`cla.io/project-facts.md`'s "Workspace shape" (run `/cla:sync-context` to populate it; falls back to
`references/project-context.md`'s "What the repo is" / "Per-dimension agent-dispatch injection facts" —
Project Snapshot, if absent); `Dataset` stays dynamic (counts read live from the dataset itself):

```
Project: <this repo's name> (<its workspace/monorepo shape>)
Apps:     <one clause per app: name (one-line role)>
Packages: <one clause per shared package: name (one-line role)>
Backend:  <this repo's own backend project, if any>
Dataset:  <this repo's own domain-vocabulary/dataset counts and where they live, if applicable>
Active OpenSpec changes: {count from ls openspec/changes/ excluding archive/}   Archived: {count from openspec/changes/archive/}
Build: {PASS/FAIL}   Lint: {PASS/FAIL}   Tests: {PASS/FAIL}   Static checks: {n PASS / m FAIL from the script}
```

This snapshot + the Mechanical Facts table (`references/mechanical-checks.md`) = the complete brief
every agent receives. Do NOT read full file contents to paste into agent prompts — agents read
specific files themselves.

## Step 3 — Aggregate, report, and log (full recipe)

Wait for all five agents. Then:

1. **Deduplicate:** If two agents found the same gap, keep the more specific version.
2. **Merge mechanical + qualitative:** Combine FAIL items from Step 0 with agent findings. Mechanical FAILs count as gaps in the relevant dimension (build/lint/test → Validation or Architecture; i18n/daypart → Architecture/Vision; boundary → Structure/Architecture).
3. **Compute verdict:** per the rubric table in `SKILL.md` Step 3 (kept inline there — the correctness-gating thresholds).
4. **Extract top recommendations:** the 3-5 highest-impact gaps, prioritized by: core-flow impact (the product's primary user path), real breakage risk (broken build, corrupted core calculations, missing translations, tenant-isolation holes) over aesthetics, and actionability.

Print the full report:

```
## Project Review: {repo}
**Date:** {today}  |  **Reviewer:** Claude (CTO-level review)

### Mechanical Checks
{n} PASS, {m} FAIL
{list any FAILs with one-line details}

### Dimension Grades

| Dimension | Grade | One-line summary |
|-----------|-------|-----------------|
| Vision & Clarity | {A-D} | {summary} |
| Structure & Organization | {A-D} | {summary} |
| Requirements & Specs | {A-D} | {summary} |
| Architecture & Design | {A-D} | {summary} |
| Validation & Quality | {A-D} | {summary} |

### Verdict: {verdict}

{1-2 sentence overall assessment}

### Top Recommendations (priority order)
1. **{recommendation}** — {why it matters, what to do}
2. ...

### Detailed Findings
#### {dimension} — Grade: {grade}
**Strengths:** … **Gaps:** …
(repeat for all five dimensions)
```

Keep each finding to 1-2 lines. Aim for ~60-80 lines total — comprehensive but scannable.

5. **Append the run to the retro log** (matches the repo's other `*-runs.jsonl` retro-log pattern, so grades are trend-able across runs). Append exactly one JSON line to `cla.io/retro/project-review-runs.jsonl` (create the file if absent):

```bash
printf '%s\n' '{"ts":"{ISO-8601 UTC}","mechanical":{"pass":N,"fail":M},"grades":{"vision":"A","structure":"B","requirements":"B","architecture":"A","validation":"C"},"verdict":"STRONG","topRecs":3,"outputChars":N}' >> cla.io/retro/project-review-runs.jsonl
```

Fill in the real values. `outputChars` is the printed report's own character count (optional — a
verbosity proxy, not a full token-spend measure) — it directly checks the report against this
skill's own "~60-80 lines total" target above; a future `/cla:project-review-retro` could trend it
to flag the report template creeping past its budget. This is the only state the skill persists; a
future `/cla:project-review` can diff against the previous line to see whether any dimension
regressed.
