# Baseline score

Three versions of the same two changes (`add-check-scripts`, `add-mnemo-improve`), judged blind on
2026-11-17 with `judge-prompt.md`. In the blind copies X was variant A (no guidance), Y was the
real CLA output (`changes/` in this folder, made by `/cla:multi-spec` from mnemo commit 89c3be5)
and Z was variant B (lean principles brief). Decisions used: the three files in `../inputs/`.

## Packaging items left out

Decisions Q11-Q14 in `plugin-architecture` (project-level copy, `mnemo-plugin/` as a plain folder,
`VERSION` file and `v<semver>` tags, no plugin or marketplace packaging) postdate the real run. The
judge marked real down for them.

**Method.** No new judge was run. The judge's report was read and every packaging-dependent finding
was dropped. The seven critical outcomes (a-g) do not depend on packaging, so their scores need no
change. The judge's 1-5 scores for faithfulness and invention are single numbers, with no per-item
breakdown, so they cannot be recomputed without a new judge. They are therefore not given here.
The judge's working notes are only dumps of the real files and hold no per-item scores either.

**Items dropped (all from the judge's report; file:line are in the real output):**

- keeps `plugins/mnemo/` instead of `mnemo-plugin/` (check-scripts proposal:18)
- rewrites `marketplace.json` into a tag pointer (check-scripts design D11:175), also called harmful invention
- uses `mnemo--v` tags instead of `v<semver>` plus a `VERSION` file
- device tests for questions the decisions already dropped (improve tasks 1.1, 1.4; check-scripts tasks)
- files issues to `repository` in `plugin.json` on "mnemo-plugin" (improve upstream-issues:10, design:126, tasks 1.5), where the decisions use the stamp file
- the "Decision rows (verbatim)" quotes with the "replaced by" text cut out (design:206, 212), a consequence of writing against the pre-Q11 text

Not dropped, because they are not packaging: Y's `deletions` redefinition (note-checks:41), its
edits to the recall, review and setup specs, the stop on a missing `hubs/`, name-pattern tokens
with exit 2.

**What this leaves.** Word and requirement counts, and the critical outcomes, are as measured. The
rough invented-item counts (about 30 and 40 for real) include the dropped items; at least the
tag pointer is one of them, but how many in all was not counted, so the real count below is an
upper bound.

## Measured sizes

Measured with `wc -w` over every file of both changes, and `grep -r '### Requirement:'`.

| | words | requirements | capabilities | invented items (judge's rough count, both changes) |
|---|---|---|---|---|
| A (no guidance) | 12,243 | 59 | 10 | about 35 (15 + 20) |
| B (lean brief) | 3,734 | 22 | 5 | about 5 |
| real (today's CLA) | 20,510 | 96 | 19 | about 70 (30 + 40), upper bound |

## Critical outcomes covered (a-g), packaging-independent

| | A | B | real |
|---|---|---|---|
| a. unpushed commit not silently lost | covered | covered | covered |
| b. conflict keeps uncommitted and stashed work | covered | covered | covered |
| c. hung save is time-bounded | missing | missing | covered |
| d. failed check commits nothing | covered | covered | covered |
| e. secret hit blocks, no inbox fallback | covered | covered | covered |
| f. scoring leaves the query log alone | implicit only | missing | covered |
| g. test question not scored against a base without its fix | missing | missing | covered |
| **covered of 7** | 4 (f only implicit) | 4 | 7 |

Outcome a is "covered" in all three in the sense that each reports "committed, not pushed" (exit
3). All three miss the retry of that commit on a clean tree: the candidate outcome h in `rubric.md`,
not scored.

## Pass rule

The rule in `README.md`: (a) all 7 outcomes covered, (b) smaller than A in words and requirements,
(c) fewer invented items than A.

| | (a) all 7 covered | (b) smaller than A | (c) fewer invented than A | passes |
|---|---|---|---|---|
| A | no (3 missing or implicit) | n/a, it is the reference | n/a | no |
| B | no (c, f, g missing) | yes (3,734 < 12,243 words; 22 < 59) | yes (about 5 < about 35) | no |
| real | yes | no (20,510 > 12,243 words; 96 > 59) | no (about 70 > about 35) | no |

Nothing passes today. Today's CLA fails on size and invention, as expected. The lean brief fails on
rigor, which is the gap the next change has to close: keep a-g and stay under A's size.

## For reference: the judge's own scores (with packaging)

Not packaging-adjusted. C = `add-check-scripts`, I = `add-mnemo-improve`. A = X, real = Y, B = Z.
Ranking: A, then B, then real.

| | A C | A I | real C | real I | B C | B I |
|---|---|---|---|---|---|---|
| Faithfulness | 4 | 5 | 2 | 2 | 3 | 4 |
| Invention (5 = little and harmless) | 4 | 3 | 2 | 1 | 5 | 5 |
| Gap handling | 4 | 4 | 3 | 3 | 3 | 3 |
| Reviewability | 3 | 3 | 1 | 1 | 5 | 5 |
| Implementability | 5 | 4 | 3 | 3 | 2 | 2 |

The faithfulness rows for real are the ones the packaging items depress; the reviewability rows
follow from size and do not change.
