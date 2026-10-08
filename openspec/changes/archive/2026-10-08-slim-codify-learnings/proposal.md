## Why

`codify-learnings` works where it is small — at most three fixes, each tied to a quoted session
failure, tools before docs, plugin-writability routing — and the rest costs about 9,500 words of
plugin prose per run plus a full read of the lessons log. Its gate never refused (236 of 236
applied across five repos), its effectiveness tally is self-graded and logged on 8 of 60 runs, 39%
of what it applied was memory outside git, and `codify-retro` cannot join re-offenses across runs
because 88 of them carry 78 distinct slugs (`cla.io/decisions/retro-and-learning-loop-simplification-2026-10-08.md`,
D1, D4, D5, D6).

## What Changes

- **Delete `codify-retro`** (skill, aggregator, tests, mutants) and every reference to it.
- **`codify-learnings`** becomes five steps in about 1,000 words: list the session's failures; check
  each against existing rules, a hit being a re-offense keyed by the failing artifact's path or hook
  name and escalated one rung; propose at most three fixes; one prompt (`y` / `n` / indices); log
  a short entry and one ledger line. Memory holds personal working preferences only; repo lessons
  go to `CLAUDE.md` or `cla.io/overlays/`.
- **One reference**, `references/routing.md`: the four-rung ladder, which home a lesson takes, the
  writability check, and 15 failure prompts (from 51).
- **The codify record** becomes `{ts, applied: [{target, rung}], re_offenses: [{artifact, escalated_to}]}`
  in `lib/log_run.py` (design.md).
- `run-ledgers`: the retro-report requirement names only the spec-to-pr retro.

**Dropped, and why it is safe** (check 2): the effectiveness tally, Step 3.5 self-check,
size-maintenance thresholds and log-only report sections (D4); the no-default gate rules and the
step-through mode (D4 sets the prompt; indices still pick); the full-log read (grep instead); the
scope note; the four prefer-fixes trigger examples (the rule stays); the
`${CLAUDE_PLUGIN_ROOT}` resolver (the one reference has no placeholder); the enforcement-tier
names (block-or-warn stays; the names live in `past-offenses.md`). The 51 failure-mode bullets
become 15 prompts: six retired as graduated to a hook or a skill (compound `cd`, OpenSpec
completeness, spec heading drift, PR mergeability, same-capability changes, parallel-session
staging), six retired as narrow, 39 merged. Memory
candidates now count against the cap of three. This repo's overlay loses the four sections the
skill no longer reads.

## Impact

- `run-ledgers`: one requirement removed, one added (the spec-to-pr half, restated).
- Consumers: old codify records stay as history; the writer refuses the old shape from now on.
