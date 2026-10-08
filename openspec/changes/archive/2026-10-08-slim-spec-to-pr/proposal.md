## Why

`/cla:spec-to-pr` put about 31k words in front of the model on a typical run. Its `SKILL.md` restated
each phase reference it then told the model to read, rationale and incident history sat beside the
rules in every file, and the `Measured-by:` rule was written out three times. This is P1 of the
2026-10-08 plugin-surface simplification.

## What Changes

- `SKILL.md` keeps mode detection, the placeholders, the hoisted rules and a flags table. Each phase
  stub says which reference to read first and keeps only the rules that gate correctness and the
  text the tests pin.
- `revise.md`, `ship.md`, `handoff.md`, `review-sweeps.md`, `precheck.md` and `run-log-schema.md`
  keep their rules and move their rationale to `design-tradeoffs.md`, which is read only when
  revising the skill. `Measured-by:` is stated once, in `ship.md` §2b.
- `archive-preflight.md` merges into `archive.md`.
- Stale pointers fixed: "Autonomy modes", the overlay's "Incident / offense history" heading, removed
  section names cited from other skills, hardcoded `npm run` commands, and the diagram's
  `--interactive` row.

No rule's behaviour changes, so there is no spec delta (`skip_specs`).

**Rules dropped (CLAUDE.md check 2).** Prose, not rules: rationale, history and duplicate copies of a
reference's own rules. Each "why" moved to `design-tradeoffs.md`. Fully deleted:
- the `run-log-schema.md` sample refusal line; `log_run.py` prints it;
- the nudge thresholds in `handoff.md`; the `run-ledgers` spec states them;
- two mutation-gate anecdotes; DEVELOPER-GUIDE §12 holds them;
- `commit.py` history and the "no repo-root `src/`" monorepo note.

Copies, not rules: the SKILL.md copies of the test-notes external-API note and the caps table (now
the flags table).
