# review-change dispatch — Step 4 of `checklist.md` (large changes only)

Read only when `checklist.md`'s Step 3 size gate grades the change **Large**. Step
and section names below (Step 2, Step 2b, Step 5, §"Grounding contract") are
`checklist.md`'s, which the orchestrator has already read.

## Launch three review agents in parallel

Use the **Agent tool** to launch all three concurrently in a SINGLE message. Include the context brief and the full text of the artifacts (read them yourself and paste content into the prompt — don't make agents re-read files).

**Model routing:** `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md` is the shared routing source for *all* review-agent dispatch in this repo (spec-to-pr Review, this dispatch, and project-review) — not a spec-to-pr-private table. Pass an explicit `model:` per its "Review-agent dispatch" rows — **Agent 1 (Design Reviewer) → `opus`** (it catches the "the whole premise is wrong" class, worth the top tier); **Agents 2 & 3 (Task, Spec & Codebase) → `sonnet`** (structured rubric application). When invoked from `/cla:spec-to-pr` this is mandatory. The standalone `/cla:review-change` path SHOULD apply the same routing (it's the same judgment work regardless of entry point); the only reason to fall back to the session model for all three is a session already at Opus, where routing Agent 1 to opus is a no-op and routing 2 & 3 down to sonnet is the one real economy — apply it when the session is above Sonnet.

**Important instruction for all agents:** You have been given the COMPLETE text of all change artifacts. Do NOT re-read these files — use only the content provided. You MAY read source files (across whichever app/package Step 2 identified) to verify claims, but never re-read the change artifacts themselves.

**Inherited-obligation rows in the context brief.** Step 2b tags any obligation this change inherits from an earlier change as an `INHERITED OBLIGATION` row in the context brief every agent below receives. A row reading `VIOLATED` or `NOT ADDRESSED` is a **Critical** finding: report it, and say what the artifacts must state instead — a `tasks.md` subtask naming the field and what reads it, not a mention pasted into prose. These rows are the one input that cannot be derived from the artifacts in front of you; their justification lives in a different change.

**Before dispatching, check that every placeholder is filled:** write each composed prompt to a scratch file and run `grep -c 'inject:' <file>`; it must print 0. Run it yourself: the agent cannot check its own prompt.

**Injection is mandatory, not optional (Decision C).** Every `<inject: ...>` placeholder below MUST be replaced with actual content before the prompt is dispatched — for most placeholders that is repo-fact content from `cla.io/overlays/review-change.md`. Each placeholder names its own source; read it — the orchestrator reads the overlay (already done in Step 2) and pastes the relevant facts directly into the prompt text at dispatch time. A dispatched agent never loads the skill or resolves `cla.io/overlays/review-change.md` itself, so a placeholder left un-filled, or replaced with a bare "see cla.io/overlays/review-change.md" pointer, leaves that agent reviewing blind — strictly worse than embedding the facts. The check *structure* below (what to verify, in what order) is the portable part; the injected content is what makes each check concrete for this repo.

### Agent 1: Design Reviewer  (`model: opus`)

> You are a senior engineer reviewing an OpenSpec change for this repo. **Affected area:** <the app/package(s) Step 2 identified>. <inject: this repo's architecture + one-directional data-flow summary for the affected area, from `cla.io/overlays/review-change.md` ("Repo context") — for the plain workspace member list/roles, pull from `cla.io/project-facts.md`'s "Workspace shape" instead>. Be terse — one line per finding, no preamble.
>
> You have been given the COMPLETE text of all change artifacts. Do NOT re-read these files — use only the content provided. You MAY read source files to verify claims.
>
> **Read only — never write to the working tree.** Do NOT edit, revert, or restore any file, and do NOT run `git checkout`, `checkout -- <path>`, `restore`, `reset`, `stash`, `switch`, or `branch`. The tree may hold uncommitted work in the exact files you are reviewing and you cannot tell, so a "temporary" revert destroys it silently and your report still reads as success. Read a committed state with `git show <ref>:<path>` or `git diff <base>...<branch>`. If a finding genuinely needs code mutated to verify it, copy the file to the session scratchpad, mutate the copy there, and say in your report that you did NOT verify against the live tree.
>
> **Change:** <name>
> **Affected area:** <the specific paths from Step 2>
> **Context brief:** <pre-gathered facts table>
> **Proposal content:** <full text>
> **Design content:** <full text, or "(no design.md)">
> **Relevant repo-convention doc content:** <inject: the repo's own architecture/convention doc(s) for the affected area, per `cla.io/overlays/review-change.md`>
>
> Check:
> 1. **Verify claims (MOST IMPORTANT):** For every claim that says "X already works", "no changes needed to Y", or "Z outputs W" — verify against the actual code.
> 2. Feasibility, completeness (missing edge cases — <inject: this repo's own domain-specific edge-case examples per affected area, from `cla.io/overlays/review-change.md`>), unstated risks, scope, architecture fit (<inject: this repo's own architecture-boundary rules per affected area, from `cla.io/overlays/review-change.md`>).
> 3. **Allocation-math integrity** (only if the change touches this repo's core calculation engine) — does it preserve the documented formulas? <inject: the exact formulas this repo's engine must preserve, from `cla.io/overlays/review-change.md`>. Any silent formula change without an explicit behavior-change goal is Critical — and must update the load-bearing spec/doc files this repo names for that formula together (per `cla.io/project-facts.md`'s "Allocation-formula lockstep doc set", falling back to `cla.io/overlays/review-change.md` if absent).
> 4. **i18n discipline** — Is all new user-facing text routed through this repo's translation-key mechanism, with the key added to every language file of the correct i18n layer? <inject: this repo's i18n-layer names + any load-bearing key convention (e.g. keys-not-display-strings), from `cla.io/overlays/review-change.md`>.
> 5. **Convention fit** — <inject: this repo's styling-token, fixed-ordering, simulated-latency, and test-coverage conventions per affected area, from `cla.io/overlays/review-change.md`>.
> 6. **Hidden claims** — A sentence whose truth depends on the code, real data, a cited existing implementation or the deployment is a claim even when it reads as an explanation, a comparison or a trade-off. Verify it.
>
> Output format — one line per issue:
> - [Critical/Important/Suggestion] Issue description
>
> One more line kind, for something you could not settle:
> - [Open] <what could not be settled>: <what it would take to settle it>
>
> An `[Open]` line is NOT a finding and carries no severity. Never relabel one
> as Critical/Important/Suggestion to make it fit — that manufactures a problem
> out of a question, which is the failure this line kind exists to prevent.

### Agent 2: Task Reviewer  (`model: sonnet`)

> You are reviewing tasks for an OpenSpec change in this repo (see the affected area below for which app/package). Your PRIMARY focus is catching tasks that are too complex — tasks where an LLM implementer would hang or produce poor results due to scope overload. Be terse.
>
> You have been given the COMPLETE text of all change artifacts. Do NOT re-read these files — use only the content provided. You MAY read source files to verify task feasibility.
>
> **Read only — never write to the working tree.** Do NOT edit, revert, or restore any file, and do NOT run `git checkout`, `checkout -- <path>`, `restore`, `reset`, `stash`, `switch`, or `branch`. The tree may hold uncommitted work in the exact files you are reviewing and you cannot tell, so a "temporary" revert destroys it silently and your report still reads as success. Read a committed state with `git show <ref>:<path>` or `git diff <base>...<branch>`. If a finding genuinely needs code mutated to verify it, copy the file to the session scratchpad, mutate the copy there, and say in your report that you did NOT verify against the live tree.
>
> **Change:** <name>
> **Affected area:** <the specific app/package + paths from Step 2>
> **Context brief:** <pre-gathered facts table>
> **Tasks content:** <full text>
> **Design content:** <full text, or "(no design.md)">
> **Delta specs content:** <full text of each spec>
>
> Check:
> 1. **Task complexity (MOST IMPORTANT)** — Flag any task that:
>    - Has more than 5 subtasks
>    - Touches more than 3 files across different concerns (e.g. a data-layer change + a UI component + an i18n update all in one task, or a schema migration + an authorization policy + a UI form all in one task)
>    - Mixes creation, deletion, and modification of different components
>    - Requires generating large amounts of content in one task (e.g. populating a large dataset/seed from scratch)
>    - Combines mechanical work with creative/judgment work
>    For each flagged task, suggest a concrete split.
> 2. **Implementability scope (MOST IMPORTANT)** — Classify each task as LLM-work or human-work. LLM-work = things an implementer agent can do with Read/Edit/Write/Bash in one session: writing/editing source files, editing config/data files, writing migrations, running the repo's own build/lint commands, running a scripted smoke test. Human-work = things requiring judgment the agent cannot substitute for: sourcing real figures from an external data provider, visually approving a chart's look, deciding a business weight/parameter, provisioning a real external cloud resource. Flag any task that is silently human-work as **Important** with a concrete recommendation. <inject: this repo's own mock-data-is-fine-but-say-so convention, if any, from `cla.io/overlays/review-change.md`>.
> 3. **Task-design alignment** — Design elements with no task? Tasks with no design basis?
> 4. **Missing tasks** — <inject: this repo's own list of commonly-forgotten companion tasks per affected area (dataset/array updates, prop threading, regenerated types, policy tests, doc updates), from `cla.io/overlays/review-change.md`>.
> 5. **Dependencies & ordering** — Is the ordering logical? (data-layer/migration before the code that reads it; data layer before the component that renders its output; i18n keys before/with the component that calls the translation function; a user-facing string change before any smoke-test update that asserts on it)
> 6. **File annotations** — Does each task list affected files with paths specific enough to grep (full paths, not a bare `src/`)?
> 7. **Idempotency** — Flag tasks that "create" a file/constant already present or "add" an entity already listed — rewrite as "verify".
> 8. **i18n parity** — Any task that adds a translation key but updates only one language file (of the correct i18n layer) is incomplete; all must change.
> 9. **Requirement proof** — Each requirement the delta specs add or modify needs a test task that names it or a tasks.md line `manual: <heading>: <reason>`; scenarios are examples and need no test of their own. A requirement with neither is **Important**. A test task that names no `requirement: <spec> / <heading>` marker is a **Suggestion**.
>
> Output format — one line per issue:
> - [Critical/Important/Suggestion] Issue description

### Agent 3: Spec & Codebase Reviewer  (`model: sonnet`)

> You are checking delta specs and codebase consistency for an OpenSpec change in this repo. Be terse.
>
> You have been given the COMPLETE text of all change artifacts. Do NOT re-read these files — use only the content provided. You MAY read source files to verify spec requirements against actual code.
>
> **Read only — never write to the working tree.** Do NOT edit, revert, or restore any file, and do NOT run `git checkout`, `checkout -- <path>`, `restore`, `reset`, `stash`, `switch`, or `branch`. The tree may hold uncommitted work in the exact files you are reviewing and you cannot tell, so a "temporary" revert destroys it silently and your report still reads as success. Read a committed state with `git show <ref>:<path>` or `git diff <base>...<branch>`. If a finding genuinely needs code mutated to verify it, copy the file to the session scratchpad, mutate the copy there, and say in your report that you did NOT verify against the live tree.
>
> **Change:** <name>
> **Affected area:** <the specific app/package + paths from Step 2>
> **Context brief:** <pre-gathered facts table>
> **Delta specs content:** <full text of each spec>
> **Main specs directory:** openspec/specs/ — list it with `openspec list --specs` and read an overview with `openspec show <id> --type spec --json --no-scenarios`; read in full only the capabilities the delta touches
> **Source root:** <the affected app's/package's own `src/` per Step 2 — NOT a repo-root `src/`, which may not exist>
>
> Check:
> 1. **Spec requirements vs current code behavior (MOST IMPORTANT):** For each requirement, compare the outcome it states with what the code does now. Flag where the spec assumes behavior that doesn't exist yet (expected for ADDED Requirements) vs contradicts existing behavior (this is a bug). Compare outcomes, not names.
> 2. Spec testability (every SHALL has at least one WHEN/THEN scenario), conflicts with main specs, codebase pattern adherence (<inject: this repo's own architectural/authorization/i18n/styling/typechecking conventions, from `cla.io/overlays/review-change.md`>).
>    **Spec level and invented requirements**, each **Important**: a requirement, ADDED or MODIFIED, that breaks these rules: <inject: the `rules.specs` items from `openspec/config.yaml`, verbatim, or "(none)" when the repo has no such block>; a code name, file path or skill-internal rule in a spec, unless it is the interface; a delta that restates the proposal; a requirement that describes no observable behaviour change (remedy: drop it and set `skip_specs: true`).
> 3. **Delta section correctness** — Are spec changes labeled `## ADDED Requirements` / `## MODIFIED Requirements` / `## REMOVED Requirements` correctly? An entirely new capability should be `## ADDED`; modifying an existing requirement should be `## MODIFIED` with both the new text and scenarios.
> 4. **MODIFIED requirements are complete** — Each `## MODIFIED Requirements` entry carries the full final requirement text and all its scenarios, not a diff. Run `openspec validate <change> --strict`: a block that drops a scenario the live requirement still has is **Critical**, because archive would delete it.
> 5. **Hidden claims** — A sentence whose truth depends on the code, real data, a cited existing implementation or the deployment is a claim even when it reads as an explanation, a comparison or a trade-off. Verify it.
>
> Output format — one line per issue:
> - [Critical/Important/Suggestion] Issue description
>
> One more line kind, for something you could not settle:
> - [Open] <what could not be settled>: <what it would take to settle it>
>
> An `[Open]` line is NOT a finding and carries no severity. Never relabel one
> as Critical/Important/Suggestion to make it fit — that manufactures a problem
> out of a question, which is the failure this line kind exists to prevent.
