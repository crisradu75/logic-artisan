## Why

An OpenSpec `## MODIFIED Requirements` block **replaces** the requirement it names rather than
patching it, so a scenario that exists on the live requirement and is absent from the delta is
deleted from `openspec/specs/` at sync/archive time. `openspec` ≥1.11.0 refuses such an apply, so
the loss is now caught — but at apply time, by a tool this plugin does not own, in a version a
consuming repo may not be running. A repo consuming this plugin shipped exactly that once, dropping
three live scenarios from one block, caught by hand.

The decision this change implements (`cla.io/decisions/open-issues-2026-08-24.md`, item **D2**,
GitHub issue #97) opens with a genuine fork: #97's own proposed fix is a refusal inside
`openspec archive`/`sync`, which is `openspec` tooling this plugin does not own, and the stated
alternative is to report it upstream and add nothing here. **This proposal settles that fork as
"there is an in-scope half, and it is smaller than #97 implies."** The plugin already tells its
skills to hold this rule at four sites, and defines the comparison at none of them:

| site | what it says today | what is missing |
|---|---|---|
| `multi-pr/references/discover-and-gate.md:62–70` | every in-scope change carrying a MODIFIED block earns a re-base check — "diff its delta against the live spec **as of that moment**" | the word *diff*, and nothing else. No rename handling, no report shape, no adjudication rule, no severity |
| `review-change/references/checklist.md:223` (dispatch item 5) | "Any `## MODIFIED Requirements` entry must include the full final requirement text plus its scenarios, not just the diff" | a delta holding 3 of 5 live scenarios satisfies this sentence *as read*. The omission is invisible without opening the live spec, and nothing instructs the reviewer to |
| `multi-spec/references/authoring-brief.md:30` | the author-side rule — read the active spec, copy every scenario | the author-side rule only; a rule stated to the writer is not a check |
| `spec-to-pr/references/archive-preflight.md:65–79` — check (c) | already loops over **every** delta MODIFIED heading and greps the active spec | it compares the **heading**, then stops. Scenario retention is one grep further into a loop that already exists |

So the surviving gap is not "nothing covers this". It is that the obligation is stated four times
and the procedure zero times — and the two design notes #97 paid for (resolve `## RENAMED
Requirements` first; report ADDED counts alongside missing ones) are exactly what an undefined
"diff" gets wrong. A comparison run without them produced a **100% false-positive rate** on its only
real corpus: 2 flags across 2 changes, both benign renames.

## What Changes

- **Add one shared reference** — `skills/_shared/references/modified-block-retention.md` — defining
  the retention comparison end to end: resolve `## RENAMED Requirements` before anything else,
  enumerate the live requirement's scenarios and the delta block's, and report **both** directions
  in one line (`live N → delta M (+K added, -J missing)`).
- **Bind it at the site that already has a trigger and no procedure** — `multi-pr`'s Phase 1
  re-base check stops saying "diff" and names the procedure.
- **Add the trigger where none exists** — a single-change run (`/cla:spec-to-pr` on its own,
  `/cla:lite-pr`, a hand-authored change) never passes through `multi-pr` Phase 1 and so is checked
  nowhere today. Three placements: `review-change`'s spec-reviewer dispatch (item 5 becomes
  falsifiable — compare against the live spec, do not read the delta alone), `review-change` Step 5
  for the small path, which skips that dispatch and is the modal case here, and
  `archive-preflight.md` check (c) as the last backstop before materialization, folded into the
  MODIFIED-heading loop already there.
- **Make the adjudication rule explicit and the refusal impossible.** The comparison flags and a
  human or reviewing agent decides. Resolving RENAMED removes *requirement*-level false positives;
  it does **not** remove a scenario renamed in place, which was 1 of the 2 measured flags and has no
  mechanical tell. A guard that refused on a hit would refuse on a legitimate rename.
- **Explicit non-goals, recorded so a later reader does not re-litigate them.** No script. No
  enforcing gate inside `openspec archive`/`sync` — that half stays upstream, and this change
  carries the task of filing it there.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `cla-plugin`: adds three requirements — the retention comparison and where it runs, the
  rename-resolution ordering with its adjudication rule, and the two-directional report shape. All
  three are `## ADDED Requirements`; no existing requirement's text changes.

## Impact

**Files this change edits** (all portable synced core; one new file, five one-paragraph edits across
four existing files). **Locate every site by content, not by the line numbers below** — they were
re-measured 2026-08-29 and had already drifted once from the 2026-08-25 figures this section
originally carried:

- `.claude/plugins/cla/skills/_shared/references/modified-block-retention.md` — **new**
- `.claude/plugins/cla/skills/review-change/references/checklist.md` — **two** regions: dispatch item
  5 (line 304 of 424, headed "MODIFIED requirements are complete") and Step 5 (the small path, which
  skips the dispatch entirely). One region only would leave the modal case uncovered
- `.claude/plugins/cla/skills/spec-to-pr/references/archive-preflight.md` (check (c), line 67 of 96)
- `.claude/plugins/cla/skills/multi-pr/references/discover-and-gate.md` (re-base check, line 65 of 197)
- `.claude/plugins/cla/skills/multi-spec/references/authoring-brief.md` (line 30 of 69 — pointer only;
  **inside a fenced prompt template**, which design D8 records as unresolved)

**Two sites paste, three point (design D8).** The `checklist.md` item-5 and `authoring-brief.md`
edits are both inside dispatched-agent prompts, where this plugin's own rule says a bare pointer
does not resolve. So the reference is written in two halves — a `## Procedure` section of 25 lines
or fewer, and the rationale — and those two sites paste the Procedure verbatim while the other three
point at the file. One statement of the steps still exists; a paste quotes it rather than authoring
a second version.

**A sixth site, found by review and edited:**

- `.claude/plugins/cla/skills/multi-pr/SKILL.md` (line 64 — the hoisted re-base rule). It states the
  same obligation in the same undefined words; leaving it alone would have had the hoisted rule and
  the reference it points at describe the check differently.

**Two files outside the plugin tree also change, both required by tasks rather than incidental:**

- `cla.io/lessons-learned/lessons-learned.md` — task 6.3 records D2's reversal condition where a
  future run will meet it, plus what this change's own dry-run disproved. A decisions doc is
  superseded and deleted; this condition has to outlive one.
- `openspec/changes/modified-block-diff-scope/{proposal,design,tasks}.md` — this change's own
  artifacts.

**Still not affected.** No script, no hook, no test, no dev-tree file, nothing under `plugin-tests/`.

**Not affected.** No script, no hook, no test, no dev-tree file, no `openspec/specs/` tooling.
`plugin-tests/` gains nothing; the change is prose in synced core, policed by the existing
conformance guards.

**Sequencing — one shared file with ONE sibling.** `grounding-contract-claim-shapes` edits
`review-change/references/checklist.md`, in §"Grounding contract", `0k`/`0l`, the cost-offload
paragraph and Step 6. **`fix-brief-binding-defect` does not touch that file at all** — it edits
`spec-to-pr/references/subagent-brief.md`, and its own proposal says so in as many words ("This
change makes no `checklist.md` edit at all"). An earlier draft of this paragraph named both, and the
task list then greped for a sibling edit that was never made — the shape this whole change exists to
catch, in its own artifacts. Both siblings are now archived, so the ordering question is settled
either way.

This change edits the **spec-reviewer dispatch prompt's item 5** inside Step 4 and **Step 5**,
neither of which `grounding-contract-claim-shapes` names, and adds **no numbered check** — so it
does not compete for `0l`. Disjoint by region, shared by file: this change edits last, and its task
list verifies the one real sibling's edits survived.

**Relationship to what already shipped.** PR #150's live-set validation covers *parse integrity
after any edit*; its own requirement text says so and explicitly disclaims this concern
(`openspec/specs/cla-plugin/spec.md:531`). PR #149's re-base check supplies the chain-path trigger
this change supplies the procedure for. Neither is duplicated here.
