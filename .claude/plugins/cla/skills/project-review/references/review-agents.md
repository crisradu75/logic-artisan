# Project Review — Agent Dispatch Prompts

Full per-agent prompt text for Step 2's five-agent dispatch. **Mandatory read** before constructing
any agent's prompt — `SKILL.md` keeps only the dispatch invariant (all five in parallel, the model
routing) inline; this file is the actual prompt content.

Each agent receives: (1) the Project Snapshot (Step 1, template in `references/aggregate-and-log.md`),
(2) the Mechanical Facts table (Step 0, `references/mechanical-checks.md`), (3) the relevant dimension
criteria from `references/review-criteria.md`, (4) the standard instructions below.

**Standard instructions for ALL agents:**

> **Grading:** Assign exactly one grade: **A**, **B**, **C**, or **D**. No plus/minus, no fractions. Use the grade definitions and calibration examples in the criteria as anchors.
>
> **Attribution:** This is a monorepo — every finding MUST name the app/package it applies to (e.g. one worked example per app/package this repo has), and its evidence MUST cite a specific path + line or grep result. A dimension whose quality differs sharply across components should say so in its summary rather than averaging it into one bland grade.
>
> **Finding caps:** At most **3 strengths** and **5 gaps**. Prioritize the most impactful.
>
> **Pre-verified facts:** The Mechanical Facts table already verified workspace build/lint/test and this repo's own cross-file invariants (shared-i18n parity + usage, any load-bearing key consistency, package boundaries). Do NOT re-check these — focus on qualitative judgment.
>
> **Context:** <inject: this repo's own one-paragraph product/component summary + its test-surface summary (unit suites, smoke/e2e scripts, any DB-isolation suite), from `references/project-context.md` ("Per-dimension agent-dispatch injection facts" — shared Context)>.
>
> **Output format:**
> ```
> Grade: {A/B/C/D}
> Summary: {one line}
>
> Strengths:
> - {component}: {finding with evidence}
>
> Gaps:
> - {component}: {finding} — {suggested improvement}
> ```

### Agent 1: Vision & Clarity

> **Review criteria:** {Dimension 1 from review-criteria.md}   **Snapshot:** {Step 1}   **Mechanical facts:** {Step 0}
>
> **Start by reading:** <inject: this repo's top-level docs to read for a vision/clarity pass, from `references/project-context.md` ("Per-dimension agent-dispatch injection facts" — Agent 1)>.
>
> Evaluate:
> 1. Can a new senior engineer understand the product AND the workspace shape in a few minutes from the top-level docs (what/who/why, and which component does what)?
> 2. Is each component's scope explicit? <inject: this repo's own per-component scope statement, from `references/project-context.md`>.
> 3. Does the repo's own guidance doc give an accurate, current picture of the workspace layout, its core data/control flow, and its conventions?
> 4. Are component / function / type / i18n-key / package names self-documenting?
> 5. Do the docs match the current code (formulas, dataset/domain-vocabulary counts, package paths)? Flag stale claims — e.g. any spec/doc still describing an earlier, since-restructured layout.
> 6. Could a new contributor extend the domain model (e.g. add a new entity/segment/category) or add a new product surface, using only the docs?

### Agent 2: Structure & Organization

> **Review criteria:** {Dimension 2 from review-criteria.md}   **Snapshot:** {Step 1}   **Mechanical facts:** {Step 0}
>
> **Start by reading:** <inject: this repo's workspace-config files to read for a structure pass (workspace manifest, root package manifest, lint config, each package's manifest), from `references/project-context.md` ("Per-dimension agent-dispatch injection facts" — Agent 2)>. Use Glob to survey each app's and package's source tree.
>
> Evaluate:
> 1. Workspace layout — is the apps/packages split clean and are workspace-internal deps sensible? Do the shared packages have coherent public surfaces (barrel exports)?
> 2. Package boundaries — the mechanical check already verified the workspace's own boundary invariants (which packages must stay platform-safe, which may depend on which). Beyond that pass/fail, is the *dependency direction* healthy (no accidental over-coupling, nothing that should be shared living inside one app)?
> 3. Per-app internal structure — <inject: this repo's own per-app source-tree bucketing convention, from `references/project-context.md`>.
> 4. File / symbol naming — consistent PascalCase components, camelCase functions, dotted i18n keys, kebab package names?
> 5. Component sizing — <inject: this repo's own largest/most-central components or screens worth checking for decomposition, from `references/project-context.md`>.
> 6. Gitignore hygiene — build output, `node_modules/`, `.env`, and any per-app local artifacts excluded?

### Agent 3: Requirements & Specifications

> **Review criteria:** {Dimension 3 from review-criteria.md}   **Snapshot:** {Step 1}   **Mechanical facts:** {Step 0}
>
> **Start by reading:** sample 3 specs under `openspec/specs/` spanning products — <inject: this repo's own recommended sample-spec picks (one per major product/component, plus the architecture-level spec), from `references/project-context.md` ("Per-dimension agent-dispatch injection facts" — Agent 3)>. List `openspec/changes/`.
>
> Evaluate:
> 1. Spec quality — MUST/SHOULD/MAY/SHALL with testable WHEN/THEN criteria?
> 2. Coverage — do the core capabilities of every product/component have specs? Gaps?
> 3. Traceability — pick 2 specs (spanning different products/components) and verify the implementation exists in the right package/app.
> 4. Spec currency — do sampled specs match current code (formulas, dataset/domain-vocabulary counts, workspace paths)? **Specifically check whether the architecture spec or older specs still describe an earlier, since-restructured layout** — a real staleness risk after any repo restructure.
> 5. Change pipeline — stale active changes under `openspec/changes/`? Is `changes/archive/` clean?

### Agent 4: Architecture & Design

> **Review criteria:** {Dimension 4 from review-criteria.md}   **Snapshot:** {Step 1}   **Mechanical facts:** {Step 0}
>
> **Start by reading:** <inject: this repo's own core-engine, data-gateway, app-entrypoint, backend-route/adapter, and RLS/data-client files to read for an architecture pass, from `references/project-context.md` ("Per-dimension agent-dispatch injection facts" — Agent 4)>.
>
> Evaluate:
> 1. Data-flow discipline (core product) — is the gateway → projection → engine → component chain strictly one-directional? Is the app's root component the single source of truth for its draft/result state, re-running the engine on any live edit?
> 2. Engine purity — is the core generate/compute function pure (no UI-framework imports, no side effects)? <inject: the grep recipe that should return empty confirming engine purity, from `references/project-context.md`>.
> 3. Allocation-math integrity — do the formulas match this repo's own allocation-engine spec? <inject: the exact formula set + invariants this repo's engine must preserve, from `references/project-context.md`>. Excluded units zeroed? Fixed roster ordering preserved?
> 4. i18n architecture — is all user-facing text routed through the translation-key mechanism (every i18n layer)? Are any load-bearing enum-like values (e.g. a status or category enum) carried as keys end-to-end?
> 5. Data seam — is the gateway a clean seam a real upstream data feed could replace? Is any simulated latency intentional/localized? Is the shared data-schema package genuinely reusable by a backend (platform-safe)?
> 6. Backend design — is any LLM/external-API adapter interface vendor-neutral (no vendor SDK type leaking into routes/contract)? Is the wire contract duplicated-in-sync between server and frontend as documented?
> 7. Multi-tenant design (if applicable) — is tenant isolation enforced where it matters (DB-level row-security policies), not just in the UI? Is the DB client seam clean?
> 8. Styling consistency, extensibility (adding a new domain entity/category), and type safety across the boundary types.

### Agent 5: Validation & Quality Assurance

> **Review criteria:** {Dimension 5 from review-criteria.md}   **Snapshot:** {Step 1}   **Mechanical facts:** {Step 0}
>
> **Start by reading:** <inject: this repo's own core-engine test file, smoke/e2e script paths, RLS/DB test directory, and the testing-strategy spec, from `references/project-context.md` ("Per-dimension agent-dispatch injection facts" — Agent 5)>, then the core engine source and the primary intake-form component for edge-case/validation logic.
>
> Evaluate (grade against the repo's actual reality — its own suites + smoke/e2e scripts + any DB-isolation suite):
> 1. Unit-suite coverage — does the core engine's test suite cover its core invariants (budget integrity, identity/consistency checks, calibration, any minimum-floor logic) and edge cases? Do the other packages/apps have meaningful suites?
> 2. Multi-tenant safety net (if applicable) — does the DB-level isolation test suite actually assert cross-tenant isolation (tenant A cannot read tenant B's rows)? Where present, this is the highest-stakes correctness property in the repo.
> 3. Smoke/e2e currency — do the repo's own smoke/e2e scripts still match the current UI (selectors, strings, flow)? Would they pass today? (Note: edit-time drift may already be guarded by a hook — check for one — but currency of the *whole flow* is still a judgment call.)
> 4. Build + lint + test as the safety net — clean (from Mechanical Facts)? Is the type surface strong enough to catch domain misuse across package boundaries?
> 5. Engine edge cases — empty/degenerate input, all-excluded selection, zero/negative budget, a zero-denominator division guard: handled, or `NaN`/crash? <inject: the grep recipe for this repo's own division-guard pattern, from `references/project-context.md`>.
> 6. Input validation — does the primary intake form guard its required inputs before proceeding? Do other create/edit forms validate?
> 7. Honesty of the demo (if the product is a demo/prototype) — is it clear which data is mock, and are any intentional simulated-latency delays documented as fake work? Is any gap between a testing-strategy spec and reality acknowledged?
