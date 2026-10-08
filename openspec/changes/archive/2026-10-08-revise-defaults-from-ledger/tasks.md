## 1. Revise

- [x] 1.1 `revise.md`: the cap line, the deferral paragraph and reversal condition replaced by the decision and its evidence in one line; the exit gate runs a round over any fix commit while the cap allows; `PREV_FIX_SHA` captured just before the fix commit.
- [x] 1.2 `revise.md` agent table: `comment-analyzer` on substantial comment, docstring or prose changes only; the docs-only and ambiguous rows defer to it.
- [x] 1.3 `SKILL.md` Revise stub, exit gate and caps table; `workflow-diagram.md`; `design-tradeoffs.md`.

manual: A change becomes an opened pull request: Revise is executed by the model from `revise.md` and `SKILL.md`; checked by reading both after the edit, as the archived `live-specs-at-outcome-level` change did.

## 2. Retro

- [x] 2.1 `spec_to_pr_aggregate.py`: `round_2_yield` over the window replaces `findings_by_round_reversal`; `_cap_hit` uses `>=` and, on Revise, needs a `warn` or `fail` status; the nudge names that.
- [x] 2.2 Tests under `requirement: run-ledgers / Summarising recent spec-to-pr runs` and `requirement: run-ledgers / Handoff suggests a retro on recurring trouble`; `handoff.md` step 5, `run-log-schema.md` and the retro `SKILL.md` describe the new cap rule. measured: the nudge fires on 0 of interoga-ro's 62 ledger prefixes, against 31 before.

## 3. Spec and gate

- [x] 3.1 `change-workflow` / A change becomes an opened pull request modified; `run-ledgers` / The spec-to-pr retro summary and / Handoff suggests a retro removed and restated.
- [x] 3.2 Mutation batches over every touched batch, all killed; the full suite parallel and serial with matching counts.
