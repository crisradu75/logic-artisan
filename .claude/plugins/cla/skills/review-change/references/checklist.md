# review-change checklist (single source of truth)

This file and `dispatch.md` beside it hold the full review-change workflow; `dispatch.md` is Step 4 (the three agent prompts), read only for a large change. This file is loaded directly — both by the standalone `Skill(cla:review-change)` entry point (via the thin `SKILL.md` shell) AND by `/cla:spec-to-pr`'s Review phase (which reads this file directly and skips the skill-load round trip). Any change to review behavior MUST be made in these two files — dispatched-agent behavior in `dispatch.md` — not in either caller.

Review an OpenSpec change before implementation. Scales from in-context analysis for small changes to a 3-agent dispatch for larger ones. Prints a concise verdict.

**Repo context, the affected-file map, and the repo-specific domain checks live in the project overlay** — `cla.io/overlays/review-change.md` (this repo's overlay, named for the skill it serves, living in the repo rather than the plugin so a read-only plugin cache cannot strand it, and never synced by convention; a repo adopting `cla` swaps it for its own) — **and, for repo-wide shared facts (the workspace member list, the affected-file map, doc-sweep paths, the allocation-formula lockstep doc set), in `cla.io/project-facts.md`** (run `/cla:sync-context` to populate it; falls back to the overlay if absent). Read both alongside this workflow: they carry the monorepo architecture + one-directional data flow, the per-change-type affected-file map (Step 2), the domain-specific high-yield checks (0f–0i), and the allocation-math / i18n / mock-data checks (1–9). This file (`checklist.md`) is the portable review *workflow*; the overlay + `cla.io/project-facts.md` are this repo's *domain*.

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

**Read live specs overview-first.** For context on the existing specification, run `openspec list --specs`, then `openspec show <id> --type spec --json --no-scenarios` for an overview. Read in full, with scenarios, only the capabilities the change's delta touches. The MODIFIED retention comparison still reads the full live requirement.

**Identify the affected app/package(s)** from the proposal's Impact section, then the specific files within it, using the per-change-type **affected-file map in `cla.io/project-facts.md`** ("Affected-file map" — run `/cla:sync-context` to populate it; falls back to the project overlay `cla.io/overlays/review-change.md` ("Affected-file map") if absent) — it lists exactly which files to read for each change type this repo supports (see `cla.io/project-facts.md`'s "Workspace shape" for its app/package list). Confirm the named files exist at the claimed paths, and that the proposal's layer boundaries match the actual data-flow direction.

**Source files are authoritative; artifacts are claims.** Reading source freely is part of the review, not a side activity — the artifacts (proposal, design, tasks, spec deltas) describe a change's intent and assumptions, but the source code (`apps/*/src/**/*.ts(x)`, `packages/*/src/**/*.ts`, i18n JSON, CSS, root `CLAUDE.md`, the relevant `apps/*/CLAUDE.md`, smoke scripts) is ground truth. Every "X already works" / "function Y has signature Z" / "the data is keyed by W" claim in an artifact must be verified against the actual source before accepting it. This authorization applies BOTH to (a) the in-context analyst (Claude, small-change path), and to (b) the 3-agent dispatch (large-change path) — the agent prompts already include this license; the in-context path needs the same one.

**IMPORTANT: Maximize parallelism in pre-gathering.** Independent reads and greps MUST be batched into single messages with multiple tool calls. Do NOT read files one at a time when they have no dependencies on each other.

Parallel batch 1 — Read all artifacts simultaneously:
- Read proposal.md, design.md (if present), tasks.md, and all specs/*.md in ONE message

Parallel batch 2 — After reading artifacts, run ALL verification checks simultaneously. Most verification checks (0a–0l and 1–9 below) require reading source — do so freely; don't gate on the artifacts alone. <!-- enumerates-checks -->

### High-yield checks (always do — these catch the vast majority of real issues)

0a. **Symbol reality check** — For every task or spec that names a TypeScript function, type, interface, class, exported constant, or React component (e.g., "call `computeTotal` in `Checkout.ts`", "add a field to `LineItem`", "add a prop to `OrderSummary`"), grep the affected app/package's `src/` to confirm the symbol exists at the claimed path with the claimed signature. Wrong symbol names are the #1 task-authoring error.

0b. **Reference / config-file reality check** — For every task/spec that names a config or data file (an i18n JSON, a dataset JSON) or asserts its contents (a translation key path like `dashboard.example.label`, a record name, a category key), read the file and confirm. Past failure mode: a task references a `t('some.key')` that doesn't exist in the JSON, or an enum key that the engine's `order` array doesn't include.

0c. **Component / provider wiring check** — For a change that wires a UI component to shared state: for every task that says "wire component X to state Y" or "pass Z down from the app root", read the affected app's root/composition component (see the overlay's affected-file map and this repo's prop/handler names) and confirm the prop/handler is actually threaded, and that a new control re-running a computation calls back through the update handler rather than mutating local state.

0d. **Idempotency / already-done check** — For every "create `<path>`" or "add X to Y" task, check whether `<path>` already exists or `X` is already in `Y`. If already present, the task should be rewritten as "verify" rather than "add". (E.g. proposing to "add" a data entry that is already present in this repo's committed dataset roster — see the overlay for this repo's concrete example.)

0e. **Line-number drift check** — For every task citing "line N" in a target file, read lines around that number and confirm the referenced construct is actually there. If drifted, the report quotes the current line number.

0f–0i. **Domain-specific high-yield checks** — i18n key-parity + load-bearing daypart keys (0f), CSS-variable/styling convention (0g), mock-dataset shape/keying feasibility (0h), and operator seed-data/sample-file coverage (0i). These are repo-specific and as high-yield as 0a–0e for this repo — run them from the project overlay `cla.io/overlays/review-change.md` ("Domain-specific high-yield checks").

0j. **Real-data/scale grounding check** — For any change that parses/decodes/bulk-loads an external data file (a dump, an export, a public dataset) or bulk-writes to a datastore: does the design's evidence of correctness rest only on small synthetic fixtures, or has an actual sample of the real artifact been inspected (even a truncated head, or a repo-local sample-inspector script if one exists) for its real delimiter/encoding/field names/quoting convention? Two things a fixture cannot tell you, so check both against the real artifact and the target runtime's documented limits: **shape** (does the fixture's schema match the real file's, or was it authored from the same assumption the design is making?) and **scale** (does any single-pass "load it all at once" step stay inside the runtime's/datastore's hard limits — string or buffer size caps, transaction/lock ceilings, memory — at the real artifact's size, not the fixture's?). A scale limit that accumulates ACROSS statements rather than per-statement is the classic trap: shrinking the batch size does not fix it, so verify which kind you're up against rather than assuming batching is sufficient. **A design whose only evidence is "the fixture test passes" has validated neither.** Repo-specific known failure classes (the concrete limits, values, and workarounds that have actually bitten this stack) belong in the project overlay `cla.io/overlays/review-change.md` ("Real-data/scale failure classes") — read them and apply them here.

0k. **Deferred-guess-with-artifact-already-available check** — When a design/spec/doc marks a fact (a column name, a delimiter, an encoding, a rate/threshold) as a documented-but-unverified guess with a stated intent to "confirm once the real X is obtained" as a non-blocking follow-up: check whether the real X (the actual file, the actual API response, the actual production dataset) is already obtainable or already on disk right now. If so, flag it as a blocking task to resolve before merge, not an open follow-up — "we'll confirm later" against an artifact that's already available is a self-inflicted, entirely avoidable defer.

0l. **Claim-shape sweep** — Walk the artifacts for the claim shapes named in §"Grounding contract" ("Claim shapes — four sentences that are claims and do not look like claims") and resolve each per that contract. Unlike `0a–0h`, this is not delegable to `fact-gatherer`: each shape returns a judgement — a comparison of two mechanisms, a classification, an assessment of one test's strength against another's — rather than a pass/fail row. **It reports even when clean, in `### Open questions`.** One line on every review that ran it — naming a shape that triggered and how it resolved, or stating that no sentence triggered any shape. Without it, a review where the sweep found nothing prints identically to one where nobody swept. It goes in `### Open questions` rather than `### Verified claims` for two reasons: that section is trimmed to six lines and a nothing-found note is the first thing a trim discards, and it is counted by a downstream alarm watching whether reviews are still producing verifications — a mandatory row would inflate that count and stop the alarm firing.

### Weight and proof checks (always do, on both size-gate paths)

These four are unlettered on purpose: they read the artifacts, not the code. Each one that fires is an **Important** finding, except the marker case named under Scenario proof. The orchestrator runs them, and Agents 2 and 3 carry them.

- **Size.** A proposal over one page; an ADDED requirement over 500 characters or stating more than one behaviour; any artifact that restates the proposal or the specs instead of pointing to them. A MODIFIED requirement is exempt from the length check, because OpenSpec forbids trimming it outside a change made to split it. The remedy is the cut.
- **Invented requirement.** A requirement that describes no observable behaviour change, such as a refactor, tooling or docs change written as a SHALL. Remedy: drop it and set `skip_specs: true` in `.openspec.yaml`.
- **Scenario proof.** Each scenario the change adds, or whose text it changes, needs a tasks.md test task that names it, or a tasks.md line `manual: <heading>: <reason>`. A scenario with neither is the finding. A pure heading rename and a scenario carried forward unchanged in a MODIFIED block are exempt. A test task that does not name the `scenario: <spec> / <heading>` comment its test will carry is a **Suggestion**, not a blocker.
- **Repeated scenario heading.** A scenario heading the change adds that already names another scenario in the same spec, live or in the delta. `<spec> / <heading>` must name one scenario. Remedy: rename the new heading.

### Applies when the change touches allocation math, mock data, or i18n

These repo-specific checks — verify-"no-changes-needed" claims, file/symbol presence, numeric claims, cross-artifact consistency, **allocation-math integrity** (the load-bearing engine formulas), i18n literal discipline, fixed-ordering discipline, build/typecheck impact, and testing reality — live in the project overlay `cla.io/overlays/review-change.md` ("Applies when the change touches allocation math…"). Apply them for any change touching the engine, the mock dataset, or i18n. (A repo adopting `cla` replaces that overlay with its own domain checks.)

All checks above (generic 0a–0e and 0j–0l here, plus the overlay's 0f–0i and 1–9) are run by the orchestrator (you), not by agents. Record results in the **context brief** below. <!-- enumerates-checks -->

**`0l` is the one exception, and it is deliberate: the orchestrator runs it AND the Step-4 agents carry it.** The other checks resolve a claim to a fact, which one party can do once. `0l` is a *recognition* sweep — it asks whether a sentence is a claim at all — and the party that already decided a sentence was not a claim is the party least able to notice. Two independent passes is the point, not redundancy. Three consequences to hold. The orchestrator's sweep is the **comprehensive** one, because it alone holds every artifact — Agent 1 receives the proposal and design, Agent 3 the delta specs, and `tasks.md` goes only to Agent 2, which carries no shape check; so a shape triggered by a sentence in `tasks.md` is caught by the orchestrator or not at all, and the agents' passes are a second look at what each of them holds rather than full coverage. A shape row the orchestrator resolved does not excuse the agents from their own sweep, and **where the orchestrator's shape finding and an agent's disagree, the Step 5 tie-break applies as written — keep the higher severity.** That rule is worded for two dispatched reports; read the orchestrator's own sweep as a third report for this purpose.

**Empirical-verification fidelity (when a finding claims RUNTIME or datastore semantics).** Most checks above are static (grep a symbol, read a file). Some findings instead assert *behavior* — "this write can violate a uniqueness constraint depending on row order," "this async path races that one," "this call returns an empty result rather than an error." When you resolve such a finding by *running something* (a scratch query, a throwaway test), the harness MUST structurally mirror the real object: the SAME field/column names, the SAME constraint shape, and — critically — the same *cardinality* on whatever the constraint keys off. The classic self-deception is a stand-in that is accidentally already unique (a primary key, a surrogate id) standing in for a genuinely non-unique grouping value, so the very collision the finding predicts becomes unreachable in the harness and the check "passes" without ever testing anything. **A "verified" claim built on a structurally-wrong harness is worse than an unverified one — it carries false confidence into the next decision.** **When a runtime/datastore-semantics Critical is hard to verify faithfully in a scratch harness, the safest resolution is often to defer adjudication to the change's own implementation test — which is structurally faithful by construction — rather than to a hand-built scratch check.** Any past incident of this shape in THIS repo (with the concrete constraint, the wrong stand-in, and what it let through) belongs in the project overlay `cla.io/overlays/review-change.md` ("Incident history") — read it before relying on a scratch harness here.

**Cost offload for large changes (default — thin-orchestrator discipline).** On a **large** change (per the Step-3 size gate — pre-compute `a`/`b`/`c`/`e` before this step to know, including the complexity-concentration override), the *mechanical* portion of checks 0a–0h (grep a symbol, read a reference/config file, confirm a file/line claim) **defaults to** a dispatch to the read-only `fact-gatherer` agent (haiku) rather than being run inline: hand it the list of artifact claims — **minus any claim that needs a command run** (`fact-gatherer` has no `Bash`, so a row resting on a query, a build, or a test result comes back `unresolved` and looks like a finding; verify those yourself) — and it returns the context-brief rows as a **structured pass/fail table** (each row resolving to verbatim evidence or an explicit NOT-FOUND, per the grounding contract), so the raw greps/reads stay out of the orchestrator's context. **You still adjudicate every ✗ row yourself** — the agent gathers facts, it does not decide whether a failed claim matters. Judgment may keep the mechanical checks inline for a borderline-small change (a dispatch costs more than the checks save on a truly small change), and small changes stay fully inline. This is the plugin's thin-orchestrator discipline (`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/runtime-rules.md`); it is defined here because the checklist is the shared source of truth, so the default **applies to BOTH** the `/cla:spec-to-pr` Review phase AND the standalone `/cla:review-change` path — an intended, shared behavior, not a spec-to-pr-private optimization. Routing rationale: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`. `0l`'s claim-shape sweep sits outside this delegable set — each shape returns a judgement, not a pass/fail row a haiku dispatch could produce.

**Dispatched Review agents return structured output (thin-orchestrator discipline).** The Step-4 review agents, the `fact-gatherer` sweep above, and the `doc-sweeper` sweep (spec-to-pr Review) all return terse, structured output the orchestrator can merge without re-parsing prose — the Step-4 agents' `- [Critical/Important/Suggestion] <issue>` line format IS that schema (severity label + one-line description, one per line), alongside the `- [Open] …` kind for a row that carries no severity, `fact-gatherer` returns the pass/fail table, and `doc-sweeper` returns the `path:line — symbol` hit list. Do NOT accept a prose-essay return in place of the structured shape; it defeats the context economy the dispatch exists for.

### Grounding contract — every claim resolves to evidence or NOT-FOUND

Every row in the context brief below (and every finding derived from one) MUST resolve to one of exactly two things: **the verbatim evidence** (the actual grep hit, the real symbol signature, the exact key string, the quoted source line — trimmed, ≤200 chars) OR an explicit **NOT-FOUND** (`not found: <what you searched, where>`). A ✓/✗ with no resolving quote and no NOT-FOUND does not count as verified — it is an unchecked claim wearing a checkmark, and it is exactly how a phantom finding survives into Revise. "Looks right" / "should exist" / "the design says so" are not evidence; the source is. This binds BOTH the in-context analyst (small-change path) and the dispatched agents (large-change path) — the agent prompts already demand a Result column, but the *resolving quote or NOT-FOUND* is what makes that column falsifiable. When a claim genuinely cannot be resolved either way in the budget available, say so (`unresolved: <why>`) rather than guessing a ✓ or ✗ — an honest gap is adjudicable; a fabricated verdict is not.

#### Claim shapes — four sentences that are claims and do not look like claims

These are recognition failures, not procedure failures — in each reported instance the reviewer held the grounding rule and the license to read source, and did not engage either, because the sentence presented as an explanation, a comparison, an output specification, or a trade.

**Shape 1 — Producible state.** *Trigger:* an artifact specifies a fixed set of example/demo/fixture/sample states a surface must show. *Resolution, per state:* (a) name the production function or query that would produce it, and read it; (b) resolve the predicate that gates the state against the **real data the system will run on**, not the fixture's — the count or the condition; (c) record ONE of exactly four, and each names what you did:
`producible: <path:line of the producing path> + <the figure the predicate resolves to>`;
`NOT PRODUCIBLE: <the line that forbids it>` **or** `NOT PRODUCIBLE: not found: <what you searched, where>` — the second form is the normal one, because an absent producing path is an absence, not a prohibition, and there is no forbidding line to quote;
`unresolved: <what you would have had to search, and why you did not>`;
`open: <why the answer does not exist yet>` — for a state whose producing path this change itself adds, per the carve-out below.
*Failure mode:* **having searched and found nothing is `NOT PRODUCIBLE`, and it carries the floor. `unresolved` is only for a search you did not run, and it must name the search you skipped** — "unresolved: budget" is not a resolution, it is a blank. A reviewer who cannot name the search has not identified the claim, which is the recognition failure this whole subsection exists to catch. *Severity floor:* a state recorded `NOT PRODUCIBLE` and written as a requirement is **Critical** — a requirement the product cannot satisfy does not fail loudly, it gets satisfied dishonestly, and the available resolution under implementation pressure is always to invent the data. *Carve-out, and it is the common case:* a state whose producing path **this change itself adds** is recorded `open: producing path is added by this change, not yet written` and goes to `### Open questions` — it is not `NOT PRODUCIBLE` — this review runs pre-implementation, so read the change's own delta for the producing path before concluding it is absent, exactly as the context brief already exempts a row that is "just to-be-created by this change". Without this the shape manufactures a Critical on every change that adds a surface and its query together.

**Shape 2 — Precedent strictness.** *Trigger:* an artifact names an existing shipped implementation as the precedent it mirrors, follows, or is modelled on. *Resolution:* (a) read the named precedent's actual mechanism at its path; (b) for each provision the new requirement imposes, record whether the precedent **satisfies** it, **does not satisfy** it, or **does not have** it — the last meaning the precedent has no counterpart to the provision at all, rather than a weaker one; (c) for each provision the precedent **does not satisfy OR does not have**, state what the extra strictness buys and who pays for it. Both buckets resolve here: an earlier draft fired step (c) only on "does not satisfy", so a provision the precedent simply lacks — the strictest case, and the one most likely to be an unexamined addition — escaped the resolution and the severity floor entirely. *Failure mode:* a provision stricter than its own cited precedent whose benefit cannot be stated. *Severity floor:* **Important**, rising to **Critical** when the provision blocks implementation. This is why no other check finds this: every other check asks whether the artifact is strong *enough*; this one asks whether it is stronger than it needs to be, and that direction has no other reader.

**Shape 3 — Guarantee class.** *Trigger:* an artifact says a mechanism prevents, controls, serialises, or makes impossible a hazard. *Resolution:* (a) classify the guarantee as a **CODE property** (a constraint, a lock, a registration, a type, a test that goes red) or a **DEPLOYMENT property** (true only because of how many processes, instances, workers, or regions run today); (b) for CODE, quote the enforcing line; (c) for DEPLOYMENT, require the artifact to say so **and** to name the trigger condition that changes it — the scaling change, the config flip, the phase that lifts the limit. *Failure mode:* leaving it unclassified, because the two read identically in prose and the gap only becomes visible once the deployment fact changes, at which point the hazard returns with no code change and nothing red. *Severity floor:* a deployment property with no named trigger is **Important**; a deployment property **described as** a code property is **Critical**, because that is a false statement about what the code enforces.

**Shape 4 — Compensating coverage and exclusion reach.** Two halves, one shape, because the issue reports them as one event.
- *Trigger (a):* a change gives up automated coverage in exchange for a named alternative. *Resolution:* read the named replacement and confirm what kind of assertion it **actually runs** — grep the replacement file for the mechanism the claim names — then state the replacement's strength relative to what was given up. *Failure mode:* accepting the description. The given-up half is visible in the diff; the replacement is a promise, so the promise is the half to verify.
- *Trigger (b):* an exclusion entry is added to any keyed allowlist or denylist — a route, a page, a denylist. *Resolution:* enumerate the components or modules reachable **only** through the excluded surface, and for each, name where it is otherwise covered or state that it is not. *Failure mode:* the entry names a page file, so the exclusion reads as excluding a route while in practice it excludes every component that route uniquely renders. *Severity floor:* **Important** where a component reachable only through the excluded surface has no named alternative coverage, rising to **Critical** where the exclusion silently drops a surface the change elsewhere claims is covered. This half carries its own floor: an earlier draft gave a floor only to trigger (a), leaving the exclusion-reach half — the half whose whole point is that its true scope is wider than it reads — with nothing to grade a finding at.
- *Severity floor:* **Important** for an unverified compensating claim; **Critical** when the replacement is measurably weaker than what it replaced.

**The common signature, so a fifth shape is recognisable.** A sentence is a claim under this contract when its truth depends on something outside the artifact — the code, the corpus, a shipped precedent, the deployment, a test file — **even when its grammar is not assertive**. The four grammars that hide one: an explanation ("because", "prevents", "is the control"), a comparison to something shipped ("mirrors", "same as", "following"), a specification of output shape ("the page shows"), and a trade ("replaced by", "compensated by", "covered instead by"). A sentence matching that signature is in scope whether or not it appears in the list.

### Context brief — standard format

Build a table like this as the verification step produces results. It is the substrate for each agent prompt (if agents are dispatched), and its **✓ rows** become the `### Verified claims` section of the final report.

**Only ✓ rows.** That section is the positive-verification list and renders `- ✓ …` entries. Every other row reaches the report by its own route:

- a ✗ row, by the promotion rule below;
- a `0l` shape row, by its severity floor;
- a row that is neither a pass nor a finding, through `### Open questions` — a ✗ that is just to-be-created by this change, an `unresolved:`, an `open:`.

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

**A `0l` shape row promotes on its own verdict, not on a ✗.** Its Result column reads `producible: …`, `NOT PRODUCIBLE: …`, `unresolved: …` or `open: …`, none of which is a ✗, so the rule above never fires for the one check whose results are not tick-or-cross. Read it this way instead: **a shape row is a candidate finding at that shape's severity floor whenever its resolution produced the thing that shape's floor grades** — not only when the reviewer notices a failure mode. Per shape, matching each floor's own wording rather than a paraphrase of it:

  - **Shape 1** — a state recorded `NOT PRODUCIBLE` **and written as a requirement** (Critical). A state shown as illustration rather than required is not a finding, and neither is an `open:` or `unresolved:` row.
  - **Shape 2** — a provision the cited precedent does not satisfy or does not have **and whose benefit cannot be stated** (Important), rising to **Critical** when the provision blocks implementation. A provision the precedent lacks whose benefit the artifact does state is compliant, not a finding.
  - **Shape 3** — a deployment property **with no named trigger** (Important), or one **described as a code property** (Critical). A deployment property correctly classified and given its trigger is compliant.
  - **Shape 4** — a compensating claim whose replacement was not read (Important), rising to **Critical** where the replacement is measurably weaker than what it replaced; an excluded surface with a component that has no named alternative coverage (Important), rising to **Critical** where the exclusion drops a surface the change elsewhere claims is covered.

  Two earlier drafts got this wrong in opposite directions, which is why each entry above carries its floor's qualifier verbatim: keying promotion on the reviewer noticing a failure mode left three of four floors unreachable, and paraphrasing the floors without their qualifiers graded compliant work as a finding. An earlier wording keyed promotion on the failure mode alone, which describes the *reviewer's* omission rather than the artifact's defect — so a guarantee correctly classified as a deployment property with no trigger hit no failure mode, carried no ✗, and reached no finding, leaving its floor unreachable. An `unresolved` row is not a finding — it goes to `### Open questions`, naming what would settle it. It carries no severity and does not block a READY verdict on its own.

### Step 2b: Inherited obligations — a required output field whenever the caller supplies any

**Input.** A caller may hand this review a set of obligations the change INHERITS from a change that shipped ahead of it — a stored field, column, response key, or required behaviour an earlier change added *for this one to consume*. `/cla:spec-to-pr` passes them from its `<inherits>` argument, one entry per `;`, each `<token> — <the failure if it is dropped>`. No entries → skip this section entirely and the report omits it. This is the ONE input a change's own artifacts can never supply: the obligation's justification lives in the change that created it, so every check scoped to this change is blind to it by construction.

**Settle each entry HERE, in Step 2b, on BOTH size-gate paths.** Do it before Step 3 decides small vs large, because the answer must not depend on which path ran — the large path's findings come from three dispatched agents, and an obligation nobody passed them would simply go unanswered. One command per entry, not a reading:

```
grep -rl "<token>" openspec/changes/<name>/
```

- **No match anywhere in the change directory → `NOT ADDRESSED`, always.** A change cannot have honoured a field none of its four documents names, and this is the case that recurs.
- **A match → read it and choose.** `HONOURED` when the artifacts consume the field the way the obligation requires; `VIOLATED` when they name it and get it wrong or contradict it — an `## Impact` still saying "Migration: none", a Non-Goals section still calling the producing module read-only.

Add one row per entry to the context brief, tagged `INHERITED OBLIGATION`, so the large path's agents receive them with everything else they are given.

**A pasted token is not a discharge.** The fix for a `VIOLATED` or `NOT ADDRESSED` obligation makes the consumption *implementable*: a `tasks.md` subtask naming the field and what reads it, plus the delta spec when the obligation is a required field or behaviour. Prose in `proposal.md` alone satisfies the grep and changes nothing an implementer does — re-flag an obligation whose only fix was prose, exactly as the subtle-implementation-risk rule below re-flags an artifact fix with no proving-test task.

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
  - **If the change carries a `## MODIFIED Requirements` block, run the retention comparison yourself before you do** — `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/modified-block-retention.md`. On the large path it is check 5 of Agent 3's prompt in `dispatch.md`, and a small change never reaches Step 4; since small is the modal case here, a binding that lives only in the dispatch reaches the minority of reviews. One live-spec read per modified requirement, and it reports on a clean one too.
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

**Severity tie-break, when two dispatched reports carry the same finding at different severities.** Keep the **higher severity**, full stop. Where a report actually carried implementation-level evidence for its severity (a source line, a schema, a migration, a query result) and the other rested on the spec delta or artifact text alone, note which — but **only when the reports give you that**, and never as a reason to lower a severity.

**The note is conditional because the input often cannot supply it.** A Step-4 agent's return format is one line per issue — `- [Critical/Important/Suggestion] <issue>`, or `- [Open] …` for a row with no severity — and nothing in it carries an evidence class. An earlier draft made recording it mandatory, which leaves an orchestrator holding two severity labels and no evidence in either report with two exits, both bad: omit the required annotation, or invent the classification — the fabrication the Grounding contract exists to prevent. So: keep the higher severity always, and add the evidence note only where the reports made it visible.

This does **not** demote, for three independently sufficient reasons: (a) `spec-to-pr`'s Revise applies **SEV-MAX** to the identical situation (`spec-to-pr/SKILL.md`) — "the same finding rated differently by two agents is triaged at the HIGHER severity, always," called the aggregation analogue of the never-demote-a-real-finding principle — so demoting here would put two opposite merge rules in one pipeline with nothing explaining the difference; (b) READY requires 0 Critical and 0 Important, so demoting one Important to Suggestion clears the verdict gate with the finding unresolved, which INT-CAP (below) forbids by name; (c) `review-change` runs pre-implementation, where artifact-text evidence is the *correct* evidence class for its core output, so ranking source-line evidence above it would demote exactly what this review exists to produce.

The tie-break is recorded on the finding it resolves and adds no report line of its own — §"Report constraints" below still budgets one line per finding and about one screen total.

Its evidence: one overlapping finding out of 18, from one change in one chain in one consuming repo. The observed instance was a two-reviewer split under a different workflow, not this checklist's three-agent dispatch, so this rule is being generalised across a dispatch shape it was not observed in. Low overlap is the split working as designed, so expect this rule to fire rarely.

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
- swept for claim shapes: <the shape that triggered and how it resolved, or "no sentence triggered any shape">

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
- **FIX FIRST** — ≥1 Critical and/or Important finding, AS LONG AS every one of them (regardless of severity label) can be resolved by editing the artifact text (cutting a restated or redundant section, pinning a wording detail, splitting a task, adding a missing subtask, fixing a count, adding a missing i18n key, threading a prop, correcting a wrong SQL clause, pinning an under-specified value, etc.) without revisiting the design's premise. When a finding can be fixed either by adding text or by cutting it, recommend the cut. The number of edits doesn't matter; their *kind* does — and severity label doesn't gate this either: a Critical finding with a concrete, contained, single-edit fix (e.g. "this migration uses the wrong `ON DELETE` clause syntax," "this task bundles two unrelated concerns") is FIX FIRST, not an automatic RETHINK.
- **RETHINK** — at least one Critical or Important finding whose fix requires re-opening the design conversation (an unstated assumption about how the allocation math works, a data-flow inversion, a goal/non-goal that needs renegotiation, a genuinely missing architectural decision like "how is this value even obtained"). RETHINK is about *the kind of work needed to resolve the finding*, not about the count OR the severity label. A change with 8 Important (or even 2 Critical) findings that are all "edit this paragraph," "fix this clause," or "add this task" is FIX FIRST; a change with 1 Important finding that says "the whole approach assumes the engine returns X but it returns Y" is RETHINK. **Do not shortcut this to "any Critical → RETHINK"** — that literal reading contradicted this same rubric's own principle in an earlier version and corrupted the `verdict` field's meaning in `/cla:spec-to-pr-retro`'s telemetry (multiple real runs had Criticals that were single-edit fixes, correctly resolved in one Review round, yet got mislabeled RETHINK). Judge by the fix's nature, always.

### Fixing a "subtle-implementation-risk" finding — the artifact fix MUST add a proving test

Some FIX-FIRST findings aren't "the plan is wrong" but "the plan is right yet an implementer could satisfy its *letter* while missing its *point*." Signatures: a finding whose fix is "reuse an existing helper/formula instead of writing a new one" (an implementer can call the right function but pass it the wrong value source), "gate this control consistently with its true sibling, not a visually-adjacent one" (an implementer can pick the wrong conditional), "these two values must reconcile to the same total" (an implementer can round each independently). For **this class**, editing the design/tasks prose to prescribe the correct shape is necessary but **not sufficient** — see `cla.io/overlays/review-change.md` ("Incident history") for two real cases in this repo where a literal-but-incomplete implementation reintroduced the exact defect one layer down, caught only by a *separate* post-implementation review pass. So when you apply the artifact fix for a subtle-implementation-risk finding, the fix MUST also add (or extend) a `tasks.md` subtask that mandates a **dedicated regression test proving the fix holds** — a test that would fail if the implementer followed the letter but not the spirit. Treat "add the proving test" as part of discharging the finding, not an optional extra: a subtle-implementation-risk finding whose artifact fix adds prose but no proving-test task is only *half* resolved, and should be re-flagged if the tasks.md still lacks it. (The corresponding post-implementation obligation lives in `/cla:spec-to-pr`'s Revise triage — but catching it here, at the tasks level, is cheaper than catching it as a Revise finding after Implement already shipped the incomplete version.)

### Verdict integrity — no capitulation, no sycophancy

The verdict is the review's whole output; the two ways it silently degrades are both *pressure* failures, not analysis failures. In an autonomous `/cla:spec-to-pr` run the pressure isn't a human in the room — it's the orchestrator that dispatched this review wanting to proceed, and (in the re-review after fixes) the standing assumption that the fix worked. Hold the line against both, as named, checkable rules:

- **INT-CAP (no capitulation).** A Critical or Important finding is discharged only by *evidence that the underlying issue is gone* — a resolving quote from the now-corrected artifact/source (per the grounding contract above), not by the fact that an edit was attempted, that the round budget is running out, or that the change "needs to ship." "We already fixed that," "the delegate reported done," and "there's no budget for another round" are **not** resolutions. A finding that cannot be shown resolved stays open (→ FIX FIRST / warn), it does not quietly become READY.
- **INT-SYC (no sycophancy).** Do not adopt a premise just because the artifact, the proposal author, or the orchestrator asserts it — "this already works," "no changes needed to Y," "this is obviously correct" are hypotheses to verify against source (checks 1 and 0a–0l exist precisely for this), never facts to accept. A READY verdict must rest on your own grounded verifications, not on the change's self-description. <!-- enumerates-checks -->
- **Re-verification is not rubber-stamping.** When a fix has been applied and you re-check it (the `/cla:spec-to-pr` Revise "did the edits land?" step, or a second review round), verify the *defect is actually gone*, not merely that *an edit exists where the finding pointed*. An edit that touches the right line but doesn't remove the problem is an unresolved finding, not a closed one.

These are the review analogue of the phantom-finding verification discipline (`/cla:spec-to-pr` Revise): the cost of holding a verdict open one more round is small; the cost of a capitulated READY is a real defect shipped with a green light on it.

### Why `### Verified claims` is printed

Silent "✓" work is invisible to the user — they can't tell whether the reviewer checked 10 things and they all passed, or skipped the check. List the load-bearing verifications the review actually made. There is no quota: a padded list is noise, and the `### Open questions` sweep row is what shows the review ran.

### Report constraints

- One line per finding.
- **A `[Critical]` or `[Important]` never prints under `### Suggestions`.** Severity is stated twice, by the section and by the label. On a disagreement the finding moves and the label stands; never edit the label down to match the section. The two Fix sections are timing-based, so the move goes to whichever of them the fix's timing warrants. Only the move out of `### Suggestions` is forced. **The cost, stated because this reads as cosmetic:** `spec-to-pr`'s Review loop applies each Critical and Important finding and does nothing with Suggestions. A Critical filed under that heading is **dropped**, not deferred. This is not Step 5's tie-break, which settles two dispatched reports grading one finding differently — that one settles two reviewers, this one settles a single finding's two statements of itself.
- Omit any section with zero findings (don't print empty headers) — **except `### Inherited obligations` (omitted only when the caller supplied no entries) and `### Open questions` (never omitted — and note it can never legitimately read "(none)": the claim-shape sweep runs on every review and always emits its one row, so an empty section means the sweep was skipped, not that nothing was found).** Both are required output fields rather than findings lists. For `### Inherited obligations`, `HONOURED` lines are the answer, not an empty section; for `### Open questions`, the sweep row is — an empty one is evidence the sweep did not run. Dropping either because "there is nothing to fix" removes the evidence that anyone looked.
- Total report should fit on one screen (~40 lines max).
- If `Verified claims` would be longer than 6 lines, keep the 6 most load-bearing (the ones directly tied to the artifacts' top claims). **`### Open questions` is not trimmed, and is kept short by grouping rather than by cutting.** Trimming it would delete precisely the rows nobody has resolved, which is the opposite of what a budget should drop first. But one shape resolves *per state*, so a change specifying many demo states can emit many near-identical rows: group those into one row naming the count and the shared reason (`4 demo states: producing paths are added by this change, not yet written`) rather than listing each. Group, never drop.
- **`### Open questions` is where a row goes that is neither a pass nor a finding.** Three kinds land here: a check the reviewer could not run and why; a claim whose answer depends on code this change has not written yet, which is normal before implementation and is not a defect; and a one-line note that a sweep ran and found nothing, so a review that did the work does not print identically to one that skipped it. The first two kinds name what would settle them — for the second, that is the change's own implementation. The **third**, the sweep row, names no outstanding question: it exists so a review that ran the sweep does not print identically to one that skipped it. **An open question is not a finding and carries no severity** — it does not block a READY verdict on its own; it tells the reader what was not established, which is a different thing from telling them what is wrong.
