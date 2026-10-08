# review-change checklist (single source of truth)

This file and `dispatch.md` beside it hold the full review-change workflow; `dispatch.md` is Step 4 (the three agent prompts), read only for a large change. This file is loaded directly — both by the standalone `Skill(cla:review-change)` entry point (via the thin `SKILL.md` shell) AND by `/cla:spec-to-pr`'s Review phase (which reads this file directly and skips the skill-load round trip). Any change to review behavior MUST be made in these two files — dispatched-agent behavior in `dispatch.md` — not in either caller.

Review an OpenSpec change before implementation. Scales from in-context analysis for small changes to a 3-agent dispatch for larger ones. Prints a concise verdict.

**This repo's facts come from `cla.io/project-facts.md`** — the workspace member list, the per-change-type affected-file map (Step 2), doc-sweep paths and the cross-file lockstep doc sets (run `/cla:cla-setup` when it is missing or stale). **Its repo-specific review checks come from `cla.io/overlays/review-change.md` when that file is present** — the domain checks 0f–0i and 1–9, known real-data failure classes for 0j, past harness incidents. Without the overlay, the generic checks here are the whole review. This file (`checklist.md`) is the portable review *workflow*; those two files are this repo's *domain*.

**Input**: Optionally specify a change name (e.g., `/cla:review-change dashboard-add-daypart-filter`). If omitted, infer from context, auto-select if only one active change, or prompt.

## Step 1: Select the change

If a name is provided, use it. Otherwise:
- Infer from conversation context if the user mentioned a change
- Auto-select if only one active change exists
- If ambiguous, run `openspec list --json` and use **AskUserQuestion** to let the user select

Announce: "Reviewing change: **<name>**"

## Step 2: Read artifacts and pre-gather facts

Read the change directory at `openspec/changes/<name>/`:
- `.openspec.yaml`, `proposal.md`, `design.md` (when present), `tasks.md`, `specs/*/spec.md`

If `proposal.md` is missing, report incomplete and stop. design.md is optional: OpenSpec writes one only when a stock trigger applies. When it is absent, read it as "(absent)" everywhere below. A change with `skip_specs: true` in `.openspec.yaml` has no `specs/` directory, which is also not incomplete.

**Read live specs overview-first.** For context on the existing specification, run `openspec list --specs`, then `openspec show <id> --type spec --json --no-scenarios` for an overview. Read in full, with scenarios, only the capabilities the change's delta touches.

**Identify the affected app/package(s)** from the proposal's Impact section, then the specific files within it, using the per-change-type **affected-file map in `cla.io/project-facts.md`** ("Affected-file map") — it lists exactly which files to read for each change type this repo supports (see `cla.io/project-facts.md`'s "Workspace shape" for its app/package list). Confirm the named files exist at the claimed paths, and that the proposal's layer boundaries match the actual data-flow direction.

**Source files are authoritative; artifacts are claims.** Reading source freely is part of the review, not a side activity — the artifacts (proposal, design, tasks, spec deltas) describe a change's intent and assumptions, but the source code (`apps/*/src/**/*.ts(x)`, `packages/*/src/**/*.ts`, i18n JSON, CSS, root `CLAUDE.md`, the relevant `apps/*/CLAUDE.md`, smoke scripts) is ground truth. Every "X already works" / "function Y has signature Z" / "the data is keyed by W" claim in an artifact must be verified against the actual source before accepting it. This authorization applies BOTH to (a) the in-context analyst (Claude, small-change path), and to (b) the 3-agent dispatch (large-change path) — the agent prompts already include this license; the in-context path needs the same one.

**IMPORTANT: Maximize parallelism in pre-gathering.** Independent reads and greps MUST be batched into single messages with multiple tool calls. Do NOT read files one at a time when they have no dependencies on each other.

Parallel batch 1 — Read all artifacts simultaneously:
- Read proposal.md, design.md (if present), tasks.md, and all specs/*.md in ONE message

Parallel batch 2 — After reading artifacts, run ALL verification checks simultaneously. Most verification checks (0a–0l and 1–9 below) require reading source — do so freely; don't gate on the artifacts alone. <!-- enumerates-checks -->

### High-yield checks (always do — these catch the vast majority of real issues)

0a. **Symbol reality check** — For every task or design.md passage that names a TypeScript function, type, interface, class, exported constant, or React component (e.g., "call `computeTotal` in `Checkout.ts`", "add a field to `LineItem`", "add a prop to `OrderSummary`"), grep the affected app/package's `src/` to confirm the symbol exists at the claimed path with the claimed signature. Wrong symbol names are the #1 task-authoring error.

0b. **Reference / config-file reality check** — For every task/design.md that names a config or data file (an i18n JSON, a dataset JSON) or asserts its contents (a translation key path like `dashboard.example.label`, a record name, a category key), read the file and confirm. Past failure mode: a task references a `t('some.key')` that doesn't exist in the JSON, or an enum key that the engine's `order` array doesn't include.

0c. **Component / provider wiring check** — For a change that wires a UI component to shared state: for every task that says "wire component X to state Y" or "pass Z down from the app root", read the affected app's root/composition component (the affected-file map names it) and confirm the prop/handler is actually threaded, and that a new control re-running a computation calls back through the update handler rather than mutating local state.

0d. **Idempotency / already-done check** — For every "create `<path>`" or "add X to Y" task, check whether `<path>` already exists or `X` is already in `Y`. If already present, the task should be rewritten as "verify" rather than "add". (E.g. proposing to "add" a data entry that is already present in this repo's committed dataset roster.)

0e. **Line-number drift check** — For every task citing "line N" in a target file, read lines around that number and confirm the referenced construct is actually there. If drifted, the report quotes the current line number.

0f–0i. **Repo-specific high-yield checks** — reserved for the domain checks `cla.io/overlays/review-change.md` lists when the repo has one (for example i18n key parity, a styling convention, a dataset's shape, seed-data coverage). Where it lists them they are as high-yield as 0a–0e; where it does not, there is nothing to run.

0j. **Real-data/scale grounding check** — For any change that parses/decodes/bulk-loads an external data file (a dump, an export, a public dataset) or bulk-writes to a datastore: does the design's evidence of correctness rest only on small synthetic fixtures, or has an actual sample of the real artifact been inspected (even a truncated head, or a repo-local sample-inspector script if one exists) for its real delimiter/encoding/field names/quoting convention? Two things a fixture cannot tell you, so check both against the real artifact and the target runtime's documented limits: **shape** (does the fixture's schema match the real file's, or was it authored from the same assumption the design is making?) and **scale** (does any single-pass "load it all at once" step stay inside the runtime's/datastore's hard limits — string or buffer size caps, transaction/lock ceilings, memory — at the real artifact's size, not the fixture's?). A scale limit that accumulates ACROSS statements rather than per-statement is the classic trap: shrinking the batch size does not fix it, so verify which kind you're up against rather than assuming batching is sufficient. **A design whose only evidence is "the fixture test passes" has validated neither.** Where `cla.io/overlays/review-change.md` records failure classes that have already bitten this stack (the concrete limits, values and workarounds), apply them here.

0k. **Deferred-guess-with-artifact-already-available check** — When a design/spec/doc marks a fact (a column name, a delimiter, an encoding, a rate/threshold) as a documented-but-unverified guess with a stated intent to "confirm once the real X is obtained" as a non-blocking follow-up: check whether the real X (the actual file, the actual API response, the actual production dataset) is already obtainable or already on disk right now. If so, flag it as a blocking task to resolve before merge, not an open follow-up — "we'll confirm later" against an artifact that's already available is a self-inflicted, entirely avoidable defer.

0l. **Hidden claims** — A sentence whose truth depends on the code, real data, a cited existing implementation, or the deployment is a claim even when it reads as an explanation, a comparison or a trade-off. Verify it like any other claim. Do this yourself rather than delegating it: it needs judgement, not a lookup.

### Weight and proof checks (always do, on both size-gate paths)

These are unlettered on purpose: they read the artifacts, not the code. Each one that fires is an **Important** finding, except the dropped-scenario case under Spec validity and the marker case under Requirement proof. The orchestrator runs them, and Agents 2 and 3 carry them.

- **Spec validity.** Run `openspec validate <change> --strict`. Any error is a finding, and so is an `Archive would refuse this delta` line, which exits 0. A MODIFIED block that drops a scenario the live requirement still has is **Critical**: archive would delete it.
- **Size.** A proposal over one page; a design.md over one page; any artifact that restates the proposal or the specs instead of pointing to them. The remedy is the cut.
- **Spec level.** Apply `openspec/config.yaml` `rules.specs` to every requirement the change adds or modifies, MODIFIED ones included. A code name, file path or skill-internal rule in a spec is a finding unless it is the interface, and so is anything else those rules exclude. The remedy moves the detail to design.md, tasks or code, or cuts it.
- **Invented requirement.** A requirement that describes no observable behaviour change, such as a refactor, tooling or docs change written as a SHALL. Remedy: drop it and set `skip_specs: true` in `.openspec.yaml`.
- **Requirement proof.** Each requirement the change adds or modifies needs a tasks.md test task that names it, or a tasks.md line `manual: <heading>: <reason>`. A requirement with neither is the finding. Scenarios are examples and need no test of their own. A test task that does not name the `requirement: <spec> / <heading>` comment its test will carry is a **Suggestion**, not a blocker.

### Repo-specific domain checks (1–9), when the overlay lists them

A repo with a core calculation engine, a mock dataset or translated text may list numbered checks 1–9 for them in `cla.io/overlays/review-change.md` — verify-"no-changes-needed" claims, numeric claims, cross-artifact consistency, **allocation-math integrity** (the load-bearing engine formulas), i18n literal discipline, fixed-ordering discipline, build/typecheck impact, testing reality. Apply them for any change touching those areas.

All checks above (generic 0a–0e and 0j–0l here, plus the overlay's 0f–0i and 1–9 when it has them) are run by the orchestrator (you), not by agents. Record results in the **context brief** below. <!-- enumerates-checks -->

**Empirical-verification fidelity (when a finding claims RUNTIME or datastore semantics).** Most checks above are static (grep a symbol, read a file). Some findings instead assert *behavior* — "this write can violate a uniqueness constraint depending on row order," "this async path races that one," "this call returns an empty result rather than an error." When you resolve such a finding by *running something* (a scratch query, a throwaway test), the harness MUST structurally mirror the real object: the SAME field/column names, the SAME constraint shape, and — critically — the same *cardinality* on whatever the constraint keys off. The classic self-deception is a stand-in that is accidentally already unique (a primary key, a surrogate id) standing in for a genuinely non-unique grouping value, so the very collision the finding predicts becomes unreachable in the harness and the check "passes" without ever testing anything. **A "verified" claim built on a structurally-wrong harness is worse than an unverified one — it carries false confidence into the next decision.** **When a runtime/datastore-semantics Critical is hard to verify faithfully in a scratch harness, the safest resolution is often to defer adjudication to the change's own implementation test — which is structurally faithful by construction — rather than to a hand-built scratch check.** Any past incident of this shape in THIS repo belongs in its `cla.io/lessons-learned/`; grep it before relying on a scratch harness here.

**Cost offload for large changes (default — thin-orchestrator discipline).** On a **large** change (per the Step-3 size gate — pre-compute `a`/`b`/`c`/`e` before this step to know, including the complexity-concentration override), the *mechanical* portion of checks 0a–0h (grep a symbol, read a reference/config file, confirm a file/line claim) **defaults to** a dispatch to the read-only `fact-gatherer` agent (haiku) rather than being run inline: hand it the list of artifact claims — **minus any claim that needs a command run** (`fact-gatherer` has no `Bash`, so a row resting on a query, a build, or a test result comes back `unresolved` and looks like a finding; verify those yourself) — and it returns the context-brief rows as a **structured pass/fail table** (each row resolving to verbatim evidence or an explicit NOT-FOUND, per the grounding contract), so the raw greps/reads stay out of the orchestrator's context. **You still adjudicate every ✗ row yourself** — the agent gathers facts, it does not decide whether a failed claim matters. Judgment may keep the mechanical checks inline for a borderline-small change (a dispatch costs more than the checks save on a truly small change), and small changes stay fully inline. This is the thin-orchestrator discipline of `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/runtime-rules.md`; it is defined here because the checklist is the shared source of truth, so the default **applies to BOTH** the `/cla:spec-to-pr` Review phase AND the standalone `/cla:review-change` path — an intended, shared behavior, not a spec-to-pr-private optimization. Routing rationale: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`.

**Dispatched Review agents return structured output (thin-orchestrator discipline).** The Step-4 review agents, the `fact-gatherer` sweep above, and the `doc-sweeper` sweep (spec-to-pr Review) all return terse, structured output the orchestrator can merge without re-parsing prose — the Step-4 agents' `- [Critical/Important/Suggestion] <issue>` line format IS that schema (severity label + one-line description, one per line), alongside the `- [Open] …` kind for a row that carries no severity, `fact-gatherer` returns the pass/fail table, and `doc-sweeper` returns the `path:line — symbol` hit list. Do NOT accept a prose-essay return in place of the structured shape; it defeats the context economy the dispatch exists for.

### Grounding contract — every claim resolves to evidence or NOT-FOUND

Every row in the context brief below (and every finding derived from one) MUST resolve to one of exactly two things: **the verbatim evidence** (the actual grep hit, the real symbol signature, the exact key string, the quoted source line — trimmed, ≤200 chars) OR an explicit **NOT-FOUND** (`not found: <what you searched, where>`). A ✓/✗ with no resolving quote and no NOT-FOUND does not count as verified — it is an unchecked claim wearing a checkmark, and it is exactly how a phantom finding survives into Revise. "Looks right" / "should exist" / "the design says so" are not evidence; the source is. This binds BOTH the in-context analyst (small-change path) and the dispatched agents (large-change path) — the agent prompts already demand a Result column, but the *resolving quote or NOT-FOUND* is what makes that column falsifiable. When a claim genuinely cannot be resolved either way in the budget available, say so (`unresolved: <why>`) rather than guessing a ✓ or ✗ — an honest gap is adjudicable; a fabricated verdict is not.

### Context brief — standard format

Build a table like this as the verification step produces results. It is the substrate for each agent prompt (if agents are dispatched), and its **✓ rows** become the `### Verified claims` section of the final report.

**Only ✓ rows.** That section is the positive-verification list and renders `- ✓ …` entries. Every other row reaches the report by its own route:

- a ✗ row, by the promotion rule below;
- a row that is neither a pass nor a finding, through `### Open questions` — a ✗ that is just to-be-created by this change, or an `unresolved:`.

Stated here rather than left to the template's shape. A reader taking "becomes the section" literally renders a failed check as a verified one.

```
| Claim in artifact                                | Source location    | Verification                        | Result                                  |
|--------------------------------------------------|--------------------|-------------------------------------|-----------------------------------------|
| "call `someFunction` in `<Module>`"              | tasks.md 4.1       | grep `someFunction` in the affected package's src/ | ✓ present, matching signature |
| "`<some.i18n.key>` exists"                        | tasks.md 3.1       | read the repo's i18n JSON files     | ✗ not yet created (task 3.1 adds it) |
| "gateway exposes `getThings()`"                  | design.md §2       | grep in the affected data-layer module | ✓ present, returns Promise<Thing[]> |
| "value is derived, not stored"                   | design.md §3       | read the deriving module            | ✓ derived at read time, not persisted   |
| "both language files updated"                     | tasks.md 6.3       | read tasks.md                       | ✓ present                               |
```

If a row ends with ✗ and isn't just "to-be-created by this change," it is a candidate finding for the report.

### Step 2b: Inherited obligations — a required output field whenever the caller supplies any

**Input.** A caller may hand this review a set of obligations the change INHERITS from a change that shipped ahead of it — a stored field, column, response key, or required behaviour an earlier change added *for this one to consume*. `/cla:spec-to-pr` passes them from its `<inherits>` argument, one entry per `;`, each `<token> — <the failure if it is dropped>`. No entries → skip this section entirely and the report omits it. This is the ONE input a change's own artifacts can never supply: the obligation's justification lives in the change that created it, so every check scoped to this change is blind to it by construction.

**Settle each entry HERE, in Step 2b, on BOTH size-gate paths.** Do it before Step 3 decides small vs large, because the answer must not depend on which path ran — the large path's findings come from three dispatched agents, and an obligation nobody passed them would simply go unanswered. One command per entry, not a reading:

```
grep -rl "<token>" openspec/changes/<name>/
```

- **No match anywhere in the change directory → `NOT ADDRESSED`, always.** A change cannot have honoured a field none of its four documents names, and this is the case that recurs.
- **A match → read it and choose.** `HONOURED` when the artifacts consume the field the way the obligation requires; `VIOLATED` when they name it and get it wrong or contradict it — an `## Impact` still saying "Migration: none", a Non-Goals section still calling the producing module read-only.

Add one row per entry to the context brief, tagged `INHERITED OBLIGATION`, so the large path's agents receive them with everything else they are given.

**A pasted token is not a discharge.** The fix for a `VIOLATED` or `NOT ADDRESSED` obligation makes the consumption *implementable*: a `tasks.md` subtask naming the field and what reads it. Prose in `proposal.md` alone satisfies the grep and changes nothing an implementer does — re-flag an obligation whose only fix was prose, exactly as the subtle-implementation-risk rule below re-flags an artifact fix with no proving-test task.

**Effect on the verdict — this is what makes the field load-bearing rather than decorative.** Every non-`HONOURED` entry is a **Critical** finding, and a report carrying one can never be `READY`; see the verdict rubric's carve-out in Step 5. Without that wiring a report could state `<token>: NOT ADDRESSED` beside `Verdict: READY` and no fix round would ever run.

**Countability.** One verdict line per supplied entry, no exceptions. Fewer lines than entries means the round did not complete — a missing line is a failed round, not a pass.

## Step 3: Size gate — decide review mode

Count four things from the artifacts. Design decisions are deliberately not one of them: counting them let more decision headings buy the 3-agent review.
- **a** = files listed in the proposal Impact section (Modified + New)
- **b** = subtasks in tasks.md (count `- [ ]` lines)
- **c** = capabilities touched (delta spec directories under `specs/`)
- **e** = verifiable CLAIMS the artifacts make about existing code — every "X already works", "no
  changes needed to Y", "Z has signature W", every named symbol/file/line. Count them from the
  context brief you just built; each row is one claim.

**Rule:**
- **Small change** — `a ≤ 5` AND `b ≤ 20` AND `c = 1` AND `e < 25` **AND NOT the complexity-concentration override below**:
  - Skip the 3-agent dispatch. The orchestrator IS the reviewer — verification checks in Step 2 already produced the findings. Go straight to Step 5.
  - Announce: "Small change (a=.., b=.., c=.., e=..) — analyzing directly without agent dispatch."
- **Large change** — any of the `a`/`b`/`c`/`e` thresholds exceeded, OR the complexity-concentration override fires:
  - Proceed to Step 4 to dispatch the 3 agents in parallel.

**Claim-density override (a change can be small in code and large in assertions).** File count
and subtask count both under-weight a docs- or design-heavy change whose risk lives in what it
CLAIMS rather than what it touches: 3 files and 40 claims about existing behaviour grades "small"
and skips the dispatch, yet every one of those claims is a place the artifact can be wrong about
the codebase. Treat as **Large** when `e >= 25`, regardless of `a`/`b`/`c`. Announce it the same
way: "Large change (a=.., b=.., c=.., e=..) — claim-density override — dispatching 3 agents."

**Complexity-concentration override (a change can be conceptually large while geographically narrow).** File count under-weights a change whose whole weight lands in one already-large file — `a` reads "small" while the change is anything but. Treat as **Large** (dispatch the 3 agents) even when `a ≤ 5`, when the change is concentrated in one or two files AND carries `b ≥ 15` subtasks. Evidence this is real, not hypothetical: a `seed.ts`-concentrated change gated Small on `a=4`, got the in-context review, and its post-implementation Revise round then surfaced **more** real Important findings (8, zero phantoms) than either genuinely-Large change in the same chain (4 each) — the in-context pass under-covered exactly because the file-count gate said "small." When the override fires, announce it: "Large change (a=.., b=.., c=.., e=..) — complexity-concentration override: b≥15 subtasks in {N} file(s) — dispatching 3 agents."

Modal case in this repo: small. Don't over-engineer a review.

## Step 4: Launch three review agents in parallel (large changes only)

**Large change only: read `${CLAUDE_PLUGIN_ROOT}/skills/review-change/references/dispatch.md` now and follow it** — model routing, the placeholder check, injection, and the three agent prompts. A small change never reaches this step.

## Step 5: Aggregate and report

**An `[Open]` line from any agent goes to `### Open questions`, never into a findings section.** Deduplicate open lines the same way as findings — two agents raising the same unsettled question is one row. Deduplicate findings. When multiple findings trace to one root cause, group them: "Root cause: X — fixing this resolves N of M findings."

**Same finding at two severities:** keep the higher.

Print a **compact** report:

```
## Review: <name>

**Mode:** direct analysis (small change, a=.., b=.., c=.., e=..)   OR
**Mode:** 3-agent dispatch (a=.., b=.., c=.., e=.., [complexity-concentration override] if it fired) | Design: N or (absent) | Tasks: N | Specs: N

### Inherited obligations
- <token>: HONOURED | VIOLATED | NOT ADDRESSED — <evidence>

### Verified claims
- ✓ <thing checked>: <result>
- ✓ <thing checked>: <result>
- ✓ <thing checked>: <result>

### Open questions
- <what could not be settled>: <what it would take to settle it>

### Fix before implementing
- [source] [Critical/Important/Suggestion] Issue description

### Fix during implementation
- [source] [Critical/Important/Suggestion] Issue description

### Suggestions
- [source] [Critical/Important/Suggestion] Issue description

**Verdict: READY / FIX FIRST / RETHINK**
```

**Verdict rubric:**
- **READY** — 0 Critical, 0 Important, **and every Step 2b inherited obligation `HONOURED`.** A non-`HONOURED` entry is a Critical, so it is already excluded by the count — this clause is stated anyway because the verdict is what selects the caller's fix round, and an obligation answered in the report but not reflected in the verdict changes nothing. A report may never pair `NOT ADDRESSED` with `READY`.
- **FIX FIRST** — ≥1 Critical and/or Important finding, AS LONG AS every one of them (regardless of severity label) can be resolved by editing the artifact text (cutting a restated or redundant section, splitting a task, adding a missing subtask, fixing a count, adding a missing i18n key, threading a prop, correcting a wrong SQL clause, pinning an under-specified value, etc.) without revisiting the design's premise. When a finding can be fixed either by adding text or by cutting it, recommend the cut. Point each fix at design.md, tasks.md or code, and at spec text only when the finding is about an outcome or interface. The number of edits doesn't matter; their *kind* does — and severity label doesn't gate this either: a Critical finding with a concrete, contained, single-edit fix (e.g. "this migration uses the wrong `ON DELETE` clause syntax," "this task bundles two unrelated concerns") is FIX FIRST, not an automatic RETHINK.
- **RETHINK** — at least one Critical or Important finding whose fix requires re-opening the design conversation (an unstated assumption about how the allocation math works, a data-flow inversion, a goal/non-goal that needs renegotiation, a genuinely missing architectural decision like "how is this value even obtained"). RETHINK is about *the kind of work needed to resolve the finding*, not about the count OR the severity label. A change with 8 Important (or even 2 Critical) findings that are all "edit this paragraph," "fix this clause," or "add this task" is FIX FIRST; a change with 1 Important finding that says "the whole approach assumes the engine returns X but it returns Y" is RETHINK. **Do not shortcut this to "any Critical → RETHINK"** — that literal reading contradicted this same rubric's own principle in an earlier version and corrupted the `verdict` field's meaning in `/cla:spec-to-pr-retro`'s telemetry (multiple real runs had Criticals that were single-edit fixes, correctly resolved in one Review round, yet got mislabeled RETHINK). Judge by the fix's nature, always.

### Fixing a "subtle-implementation-risk" finding — the artifact fix MUST add a proving test

Some FIX-FIRST findings aren't "the plan is wrong" but "the plan is right yet an implementer could satisfy its *letter* while missing its *point*." Signatures: a finding whose fix is "reuse an existing helper/formula instead of writing a new one" (an implementer can call the right function but pass it the wrong value source), "gate this control consistently with its true sibling, not a visually-adjacent one" (an implementer can pick the wrong conditional), "these two values must reconcile to the same total" (an implementer can round each independently). For **this class**, editing the design/tasks prose to prescribe the correct shape is necessary but **not sufficient** — a literal-but-incomplete implementation has reintroduced the exact defect one layer down, caught only by a *separate* post-implementation review pass. So when you apply the artifact fix for a subtle-implementation-risk finding, the fix MUST also add (or extend) a `tasks.md` subtask that mandates a **dedicated regression test proving the fix holds** — a test that would fail if the implementer followed the letter but not the spirit. Treat "add the proving test" as part of discharging the finding, not an optional extra: a subtle-implementation-risk finding whose artifact fix adds prose but no proving-test task is only *half* resolved, and should be re-flagged if the tasks.md still lacks it. (The corresponding post-implementation obligation lives in `/cla:spec-to-pr`'s Revise triage — but catching it here, at the tasks level, is cheaper than catching it as a Revise finding after Implement already shipped the incomplete version.)

### Verdict integrity — no capitulation, no sycophancy

The verdict is the review's whole output; the two ways it silently degrades are both *pressure* failures, not analysis failures. In an autonomous `/cla:spec-to-pr` run the pressure isn't a human in the room — it's the orchestrator that dispatched this review wanting to proceed, and (in the re-review after fixes) the standing assumption that the fix worked. Hold the line against both, as named, checkable rules:

- **INT-CAP (no capitulation).** A Critical or Important finding is discharged only by *evidence that the underlying issue is gone* — a resolving quote from the now-corrected artifact/source (per the grounding contract above), not by the fact that an edit was attempted, that the round budget is running out, or that the change "needs to ship." "We already fixed that," "the delegate reported done," and "there's no budget for another round" are **not** resolutions. A finding that cannot be shown resolved stays open (→ FIX FIRST / warn), it does not quietly become READY.
- **INT-SYC (no sycophancy).** Do not adopt a premise just because the artifact, the proposal author, or the orchestrator asserts it — "this already works," "no changes needed to Y," "this is obviously correct" are hypotheses to verify against source (checks 1 and 0a–0l exist precisely for this), never facts to accept. A READY verdict must rest on your own grounded verifications, not on the change's self-description. <!-- enumerates-checks -->
- **Re-verification is not rubber-stamping.** When a fix has been applied and you re-check it (the `/cla:spec-to-pr` Revise "did the edits land?" step, or a second review round), verify the *defect is actually gone*, not merely that *an edit exists where the finding pointed*. An edit that touches the right line but doesn't remove the problem is an unresolved finding, not a closed one.

These are the review analogue of the phantom-finding verification discipline (`/cla:spec-to-pr` Revise): the cost of holding a verdict open one more round is small; the cost of a capitulated READY is a real defect shipped with a green light on it.

### Why `### Verified claims` is printed

Silent "✓" work is invisible to the user — they can't tell whether the reviewer checked 10 things and they all passed, or skipped the check. List the load-bearing verifications the review actually made. There is no quota: a padded list is noise.

### Report constraints

- One line per finding.
- **A `[Critical]` or `[Important]` never prints under `### Suggestions`.** Severity is stated twice, by the section and by the label. On a disagreement the finding moves and the label stands; never edit the label down to match the section. The two Fix sections are timing-based, so the move goes to whichever of them the fix's timing warrants. Only the move out of `### Suggestions` is forced. **The cost, stated because this reads as cosmetic:** `spec-to-pr`'s Review loop applies each Critical and Important finding and does nothing with Suggestions. A Critical filed under that heading is **dropped**, not deferred. This is not Step 5's tie-break, which settles two dispatched reports grading one finding differently — that one settles two reviewers, this one settles a single finding's two statements of itself.
- Omit any section with zero findings (don't print empty headers) — **except `### Inherited obligations` (omitted only when the caller supplied no entries) and `### Open questions` (print "(none)" when empty).** Both are required output fields, not findings lists. For `### Inherited obligations`, `HONOURED` lines are the answer, not an empty section.
- Total report should fit on one screen (~40 lines max).
- If `Verified claims` would be longer than 6 lines, keep the 6 most load-bearing (the ones directly tied to the artifacts' top claims). **`### Open questions` is not trimmed, and is kept short by grouping rather than by cutting.** Trimming it would delete precisely the rows nobody has resolved, which is the opposite of what a budget should drop first.
- **`### Open questions` is where a row goes that is neither a pass nor a finding.** Two kinds land here: a check the reviewer could not run and why, and a claim whose answer depends on code this change has not written yet, which is normal before implementation. Each names what would settle it. **An open question is not a finding and carries no severity** — it does not block a READY verdict on its own; it tells the reader what was not established, which is a different thing from telling them what is wrong.
