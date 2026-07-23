# candidate-extraction — Phase 1's extract / sequence / confirm mechanics (full mechanics)

The Phase 1 step-by-step procedure. `SKILL.md`'s Phase 1 stub carries the load-bearing invariant (the one confirmation gate, stated in the hoisted rules); this file carries the extraction filter, the sequencing rule, and the exact confirmation-gate question shape.

## 1a. Extract the lite-pr candidates

Read the doc and pull out every discrete, **lite-pr-sized** change it describes. Each candidate is:

- a short kebab-case `id`,
- a **one-line description** concrete enough to pass straight to `/cla:lite-pr` (the actual change to make — not a paraphrase of the whole decision; name the files/behavior where the doc names them),
- `depends_on` — other candidate ids in this batch it must run after (read the doc's own dependency/"depends on"/"after"/"builds on" prose, not just an explicit list).

**Extraction filter — only lite-sized candidates.** Honor the doc's own "next step" cues. An item whose stated next step is `/cla:lite-pr` (or that's plainly a small, self-contained change) is a candidate. An item routed to `/cla:spec-to-pr` or `/cla:multi-spec` — or that the doc itself flags as needing OpenSpec artifacts / a migration / a formula change — is **not** a lite-pr candidate: list it under an explicit "Out of scope for multi-lite (route to spec-to-pr/multi-spec)" note rather than forcing it through `lite-pr`. This mirrors the `lite-pr` vs `spec-to-pr` judgment call, applied per candidate.

## 1b. Sequence them

One `/cla:lite-pr` per candidate. Order by explicit dependency cues first (a candidate runs after everything in its `depends_on`); where the doc states no dependency between two candidates, fall back to **document order** (deterministic, predictable). Do **not** try to *group* multiple candidates into one PR the way `/cla:multi-spec` groups decisions into one change — lite candidates are individually small and independent by nature; if the user wants two fused, they say so at the confirmation step.

## 1c. Confirm the plan (the only stop before the chain runs)

Print the derived plan and confirm it once via `AskUserQuestion` before any `/cla:lite-pr` runs:

- the ordered candidate list (id + one-line description),
- for each, its `depends_on` and therefore whether its PR will be **merged before dependents** (only candidates that something else depends on) or **left open** (independents),
- the "out of scope" items being skipped and why.

This is the user's chance to reorder, drop, fuse, or re-scope a candidate before anything ships. Do not proceed past this gate until it's confirmed.

**Explicit-autonomy override.** If the user's invocation already states an autonomy directive ("operate autonomously", "don't ask, just run", "I'm leaving — take it to done"), treat 1c as pre-confirmed: apply the derived plan as-is, state it transparently as the first output so the user can still override by replying, and proceed. (Same override contract as `/cla:multi-pr`.)
