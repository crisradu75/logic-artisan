# candidate-extraction — Phase 1's extract / sequence / confirm mechanics (full mechanics)

The Phase 1 step-by-step procedure. `SKILL.md`'s Phase 1 stub carries the load-bearing invariant (the one confirmation gate, stated in the hoisted rules); this file carries the extraction filter, the sequencing rule, and the exact confirmation-gate question shape.

## 1a. Extract the lite-pr candidates

Read the doc and pull out every discrete, **lite-pr-sized** change it describes. Each candidate is:

- a short kebab-case `id`,
- a **one-line description** concrete enough to pass straight to `/cla:lite-pr` (the actual change to make — not a paraphrase of the whole decision; name the files/behavior where the doc names them),
- `depends_on` — other candidate ids in this batch it must run after (read the doc's own dependency/"depends on"/"after"/"builds on" prose, not just an explicit list).

**Extraction filter — only lite-sized candidates.** Honor the doc's own "next step" cues. An item whose stated next step is `/cla:lite-pr` (or that's plainly a small, self-contained change) is a candidate. An item routed to `/cla:spec-to-pr` or `/cla:multi-spec` — or that the doc itself flags as needing OpenSpec artifacts / a formula change — is **not** a lite-pr candidate. Neither is an item that moves **shared environment state**: a migration applied to a shared database, seeded fixture data, or a provisioning step. That kind of item creates a merge-before-next edge whatever depends on its code, and `merge-dependencies-only` keys on `depends_on`, so routing it out here is what keeps that policy correct. For both kinds, list the item under an explicit "Out of scope for multi-lite (route to spec-to-pr/multi-spec)" note rather than forcing it through `lite-pr`. This mirrors the `lite-pr` vs `spec-to-pr` judgment call, applied per candidate.

## 1b. Sequence them

One `/cla:lite-pr` per candidate. Order by explicit dependency cues first (a candidate runs after everything in its `depends_on`); where the doc states no dependency between two candidates, fall back to **document order** (deterministic, predictable). Do **not** try to *group* multiple candidates into one PR the way `/cla:multi-spec` groups decisions into one change — lite candidates are individually small and independent by nature; if the user wants two fused, they say so at the confirmation step.

## 1c. Confirm the plan (the only stop before the chain runs)

Print the derived plan and confirm it once via `AskUserQuestion` before any `/cla:lite-pr` runs:

- the ordered candidate list (id + one-line description),
- for each, its `depends_on`,
- the "out of scope" items being skipped and why — including, for each item routed out as moving shared environment state, which named part of the doc says so,
- **the merge policy question**, in the same `AskUserQuestion` call:
  - **`merge-each-clean` (Recommended)** — every candidate that passes the clean check in `candidate-loop.md` step 8 merges as soon as it passes. Each later candidate branches off a base that already holds the earlier merges, so its tests run on the combined tree. Expect open PRs at the end only for candidates that could not merge, each with its reason.
  - **`merge-dependencies-only`** — only a candidate a later candidate `depends_on` merges; every other PR is left open for the user to review and merge. Choose this when the user wants to read each PR before it lands.

State in the question that both policies run the same pre-merge checks and never merge a candidate with an unresolved Critical/Important finding.

This is the user's chance to reorder, drop, fuse, or re-scope a candidate before anything ships. Do not proceed past this gate until both the plan and the policy are confirmed. Record the confirmed policy in the run-notes ledger header (`references/bootstrap-and-tracking.md`) as soon as it is created.

**Explicit-autonomy override.** If the user's invocation already states an autonomy directive ("operate autonomously", "don't ask, just run", "I'm leaving — take it to done"), treat 1c as pre-confirmed: apply the derived plan as-is, state it transparently as the first output so the user can still override by replying, and proceed. (Same override contract as `/cla:multi-pr`.) **The policy is the one exception to applying the recommendation.** Use `merge-each-clean` only if the invocation names it ("merge as you go", "merge everything clean"). Otherwise use `merge-dependencies-only`, and say which policy was applied and why in that first output. A pre-confirmed plan is not an authorization to merge more than the invocation asked for.
