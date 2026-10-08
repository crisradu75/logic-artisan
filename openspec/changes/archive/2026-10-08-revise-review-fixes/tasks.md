## 1. Revise

- [x] 1.1 `revise.md` exit gate: a last round that committed fixes ends `ok` with a Handoff line; `warn` only for Critical/Important left open at the cap. `SKILL.md` stub and cap-exhaustion line in step.
- [x] 1.2 `revise.md` agent table: `comment-analyzer` restored to the pre-change bar; never when no comment, docstring or `.md` hunk changed. `multi-pr` `discover-and-gate.md` caps step matches.
- [x] 1.3 Round ≥ 2 on a resume derives the pre-fix SHA from the previous fix commit's parent; the sibling question is skipped on the empty-diff fallback (`revise.md`, `SKILL.md`).

manual: A change becomes an opened pull request: Revise is executed by the model from `revise.md` and `SKILL.md`; checked by reading both after the edit.

## 2. Nudge

- [x] 2.1 `spec_to_pr_aggregate.py` nudge text, the retro `SKILL.md` and `handoff.md` name `fail` with `warn`; tests under `requirement: run-ledgers / Handoff suggests a retro on repeated trouble`, one new for a Revise that failed at its cap; one mutant for the text.
