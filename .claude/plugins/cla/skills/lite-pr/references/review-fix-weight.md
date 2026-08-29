# Why the Review phase reports the fix commit's weight

Supporting note for `SKILL.md`'s Review step 5. The instruction there is one
sentence; this is the run behind it.

## The run

Source repo, PR #186. A guard hook gained a new detection rule.

| commit | what it was | insertions |
|---|---|---|
| `0d409fa` | the feature, reviewed by three agents | 474 |
| `e57902d` | the fixes for what they found | 590 |

Three agents reviewed `0d409fa` and returned five criticals between them. Those
were fixed in `e57902d`, the mutation gate was run over the fixes, both suites
were green, and the run reported that review was complete and fixes applied.

All of that was true and none of it was the thing that mattered: **the fix
commit was larger than the commit that had been reviewed, and nobody had read
it.** The report did not say so, and the user had to ask whether the fixes had
been reviewed to find out.

They had not. Reviewing `e57902d` found five more criticals — including one that
predated the PR and silently disarmed two unrelated guards.

## What this does and does not change

It does **not** add a review round. `lite-pr` reviews once on purpose: the full
triage → fix → re-review loop is `/cla:spec-to-pr`'s Revise phase, and rebuilding
it here would reintroduce exactly the cost this skill exists to avoid. That
trade is still the right one for the changes `lite-pr` targets.

What it changes is what the user is told. A cost decision and a soundness claim
are different things, and a report that ends "review complete, fixes applied"
collapses them — it reads as though the whole diff was reviewed when the reviewed
artifact is one commit and the fixes came after it. One line naming the two
numbers hands over the fact needed to decide whether to look, and costs nothing
when the answer is no.

## When the comparison is undefined

Steps 1–3 do not always produce a fix commit. Review may find nothing, or
everything it found may be deferred with a rationale. Then there is no fix commit
to weigh, and the step is one line saying so. Do not synthesise a number, and do
not quietly skip the line — "review found nothing to fix" is itself the fact the
user wants.

Note also that the reviewed side of the comparison assumes `commit-push-pr` wrote
a single commit. Where it wrote more, compare against the range rather than
against one sha, and say which range.

## The signal worth watching

A fix commit comparable in size to the change it fixes is the case to flag hardest.
It usually means the review found something structural rather than local, and a
structural fix is a new change wearing a fix's label — carrying the risk of one,
and none of the review.
