# Proposal

## Why

Issue #295 asks for a shipped version of interoga-ro's scenario-to-test guard. The plugin's rule says each
requirement a change adds or modifies is proven by a `requirement: <spec> / <heading>` test marker or a
`manual: <heading>: <reason>` tasks.md line, but only a reviewer reads it. A consuming repo has no test
gate over the plugin, so the check must be a script. Decisions 1 and 7 of
`cla.io/decisions/open-issues-2026-10-13.md` settle the shape: per-requirement markers by default,
per-scenario markers as an opt-in read from `cla.io/project-facts.md`.

## What Changes

- New stdlib-only script `.claude/plugins/cla/skills/_shared/scripts/check_spec_proof.py`. It reports and
  never edits. It fails on: a changed requirement (or scenario, in the opt-in) with neither marker nor
  `manual:` line, a marker or `manual:` line naming nothing, a heading repeated in one spec or delta, and
  a repo with no specs. "Changed" compares against the merge-base with the default branch; without it that
  rule is off and the output says so. It prints counts as information.
- It also accepts `manual: ...(prompt half)` together with a marker, and `waiting: <heading>: <reason>`
  lines (a requirement proven by a later change), counting both apart and failing a waiting line left in an
  archived change or beside an already-proven requirement.
- The opt-in is one line in `cla.io/project-facts.md`: `- Test proof granularity: requirement` or
  `- Test proof granularity: scenario`. Absent means `requirement`. A malformed or repeated line is an
  error, not a silent default. `/cla:cla-setup` asks for it and writes the line.
- `/cla:spec-to-pr` Implement's post-check runs the script and carries each problem to Handoff.
- This repo's `project-facts.md` states `requirement`. Its own marker consistency test stays as it is.

Not in scope: the spec format guard (sentence length, Purpose line) and shrink-only migration lists from
#319's second comment, which are separate checks.

## Capabilities

### New Capabilities

- `spec-proof`: what the shipped checker reports, and how a repo chooses the proof granularity.

### Modified Capabilities

None. `change-workflow` holds 8 requirements already; its "Each requirement names its proof" requirement
is unchanged.

## Impact

- New: the script, `plugin-tests/tests/skills/_shared/test_check_spec_proof.py`, a mutation batch in
  `plugin-tests/mutants/_shared/`.
- Edited: `cla-setup/SKILL.md`, `spec-to-pr/SKILL.md`, `DEVELOPER-GUIDE.md` §11,
  `cla.io/project-facts.md`.
- Minor version bump (a shipped script is added); no release is cut here.
