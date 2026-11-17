# Step 3: tuning the authoring brief (2026-11-17)

Three rounds. Each round: one Opus agent authored both changes from the brief on a scratch copy of
mnemo at 898ee67, with the benchmark decisions, a Stakes section (protected area: the owner's
notes; `Change budget: protected`) and a config seeded by `seed_openspec_rules.py`. The author
could not read the rubric, judge prompt or baseline. A fresh Opus judge then scored three blinded
versions with `judge-prompt.md`; round 3's judge applied the owner's rule that "kept the decision
and raised the conflict as an open question with a proposed fix" passes an outcome that conflicts
with a decision.

| | Brief | Words | Requirements | Invented (rough) | Outcomes passed | Judge rank |
|---|---|---|---|---|---|---|
| Round 1 | v1 | 6,618 | 38 | ~16 | 5 of 8 (e partial; g, h missing) | 1st of r1 / A / real |
| Round 2 | v2 | 8,140 | 42 | ~24 (r2 judge), ~20 (r3 judge) | 7 of 8 (g missing) | 1st of r2 / A / r1 |
| Round 3 | v3 | 8,860 | 45 | ~24 | 7 of 8 (g missing) | 1st of r3 / A / r2 |
| No guidance (A) | none | 12,235 | 59 | ~29 / ~38 / ~45 by judge | 3–4 of 8 | 2nd–3rd |

Brief changes:
- v1: principle 4, "think broadly, write narrowly": protected-area risks become requirements, the
  rest one line under "Risks noted"; open questions only for real gaps.
- v2: keep every decision as decided and raise a concern instead of changing it (round 1 reversed
  the decided save order); three failure types added to the risk list: what the next run does with
  what an earlier run left behind, fallbacks that some failures must never take, comparisons
  against the wrong baseline.
- v3: for each protected-area risk, check whether a decision rules out the fix and raise the
  conflict; every check or score says what passes, or asks; design.md follows the specs; tests run
  on copies, never on protected data (round 2 had a task pushing to a real notes remote).

Round 3 versus round 2 (round 3 judge): faithfulness 5/5 vs 3/4; no task touches real data (round
2: a task pushes to a real remote); every invented answer flagged.

Known gap: outcome g (a new test question scored against a base without its fix) was missed by all
six versions written. Covering it conflicts with the decision "a [meta] PR is never batched with
content changes"; no version raised that conflict. The owner chose to ship v3 with g recorded as
a known gap, to revisit when the [meta] rule is settled in mnemo. Further rounds aimed at g were
declined as fitting the brief to one test case.

Round 3's own weakness (for review, not the brief): its `save` design uses
`pull --rebase --autostash`, which leaves conflict markers when the stash fails to re-apply.

Caveat: the invented-item counts vary by judge (variant A was counted ~29, ~38 and ~45 by three
judges); the outcome tables are the solid measure.
