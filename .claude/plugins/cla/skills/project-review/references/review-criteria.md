# Project Review Criteria

Evaluation rubric for a CTO-level review of this repo's workspace. Each dimension has review signals, grade definitions, and grep hints — this repo's own concrete component list, calibration examples, and grep recipes live in `references/project-context.md` ("Review criteria — repo specifics"); this file holds the portable rubric *shape*. Because this may be a monorepo, assess each component's coherence and the seams **between** them — and attribute every finding to the app/package it applies to.

---

## Dimension 1: Vision & Clarity

**Question:** Are the project's purpose, scope, and the workspace's shape immediately clear to a new senior engineer?

### Review signals
- **READMEs**: Does the root README explain what the product does, who it's for, and why — and make clear the repo's own workspace shape (single app vs monorepo, and what each component is)? Do any per-component READMEs explain their own subsystem?
- **Guidance-doc coherence**: Does the repo's own guidance doc (e.g. `CLAUDE.md`) give an accurate, current picture — the workspace layout, its core data/control flow, its conventions, and its own commands?
- **Naming**: Do component, function, type, i18n-key, and package names self-document?
- **Scope boundaries**: Is it clear what each component is and is NOT (production vs demo, additive vs core, etc.)?
- **Docs accuracy**: Do README/docs/specs match the current code (counts, formulas, domain-vocabulary sets, package paths)? Any stale numbers or references to a superseded layout?
- **Onboarding**: Could a new contributor extend the domain model or add a new surface, using only the docs + guidance doc?

See `references/project-context.md` for this repo's own concrete signal list.

### Grade definitions
- **A**: A new engineer grasps the product and the workspace shape in a few minutes. Docs lead with the value prop, core logic is explained and matches the code, scope per component is explicit, naming is self-documenting.
- **B**: Clear but requires reading multiple files. Minor stale numbers or one doc referencing a superseded structure.
- **C**: Requires significant exploration. Purpose implicit; docs materially diverge from code or from the workspace layout.
- **D**: Confusing or contradictory. README is a stub, or docs describe an architecture the code no longer has.

See `references/project-context.md` for this repo's own calibration examples per grade.

---

## Dimension 2: Structure & Organization

**Question:** Does the workspace layout follow clear conventions and scale well?

### Review signals
- **Workspace layout**: Is the apps/packages split (if any) clean, and are internal workspace deps sensible? Do shared packages have coherent public surfaces (barrel exports)?
- **Package boundaries**: The mechanical check already verified this repo's own boundary invariants. Beyond that pass/fail, is the dependency *direction* healthy — nothing over-coupled, nothing that should be shared trapped inside one app?
- **Per-app internal structure**: Is each app's own source tree cleanly bucketed by concern?
- **File naming**: Consistent conventions across components/functions/keys/package names?
- **Depth / sizing**: Are the largest/most-central components or screens reasonably scoped, or do they need decomposition?
- **Gitignore hygiene**: Build output, secrets, and local dev artifacts excluded?

See `references/project-context.md` for this repo's own concrete signal list, grep hints, and calibration examples.

### Grade definitions
- **A**: Clean apps/packages split, healthy dependency direction, shared packages have coherent barrels, per-app trees are logical, components reasonably scoped.
- **B**: Mostly clean with 1-2 minor issues.
- **C**: Boundaries blur (e.g. logic that should be shared inlined in a component, or something app-specific wrongly shared). Some dead files.
- **D**: No clear convention — layers and apps intermixed, or the workspace split is nominal only.

---

## Dimension 3: Requirements & Specifications

**Question:** Are requirements well-organized, traceable, and testable across every product/component this repo has?

### Review signals
- **Spec coverage**: Do the core capabilities of every product/component have specs? Gaps?
- **Spec quality**: MUST/SHOULD/MAY/SHALL with testable WHEN/THEN acceptance criteria?
- **Traceability**: Can you trace spec → implementation in the right package/app?
- **Spec currency**: Do specs match the current implementation (formulas, domain-vocabulary counts, workspace paths)? **Watch for staleness from any past restructure.**
- **Change pipeline**: Stale active changes? Is the archive clean?

See `references/project-context.md` for this repo's own concrete spec-sampling picks and grep hints.

### Grade definitions
- **A**: Good coverage across every product/component, testable criteria, specs match implementation, clean change pipeline.
- **B**: Reasonable coverage with minor gaps. Most specs current; some lack testable criteria, or one spec lags a past restructure.
- **C**: Significant gaps — several stale specs (e.g. still describing a superseded layout), or specs that don't match the code. Weak traceability.
- **D**: Specs absent or decorative (a real gap if the repo has a spec framework initialized, not "N/A").

---

## Dimension 4: Architecture & Design

**Question:** Are the architectural patterns sound across the product(s) and any backend(s)?

### Review signals
- **Data-flow discipline**: Is the core data/control flow strictly one-directional (or otherwise architecturally sound per the repo's own stated design)? Is the app's root component the single source of truth for its draft/result state?
- **Core-logic purity**: Is the core calculation/business logic pure — no UI-framework imports, no side effects?
- **Domain-formula integrity**: Do the formulas match the repo's own specs, including any budget/normalization/floor invariants, roster ordering, and cross-segment blending?
- **i18n architecture**: Is ALL user-facing text routed through the translation-key mechanism (every i18n layer this repo has)? Are any load-bearing enum-like values carried as keys end-to-end?
- **Data seam**: Is any external-data gateway a clean seam a real upstream feed could replace? Is any simulated latency intentional/localized? Is a shared data-schema package genuinely reusable by a backend?
- **Backend design**: Is any LLM/external-API adapter interface vendor-neutral (no vendor SDK type leaking into routes/contract)? Is any wire contract kept in sync between server and frontend as documented? Are rate-limit/input-length/output-cap middlewares sound?
- **Multi-tenant/authorization design** (if applicable): Is isolation enforced at the data layer (e.g. DB row-security policies), not merely in the UI? Is the DB client seam clean, with any privileged-key usage kept server-only?
- **Styling consistency, extensibility, and type safety** across the boundary types.

See `references/project-context.md` for this repo's own concrete signal list, grep hints, and calibration examples.

### Grade definitions
- **A**: Strict architectural discipline with a pure core whose formulas match spec; clean external-data seam; vendor-neutral backend adapter (if any); tenant isolation enforced at the data layer (if applicable); consistent i18n + styling; easy to extend.
- **B**: Good patterns with minor bleed. *E.g. one bare string literal in a component, a hardcoded weight in two places, or a slightly leaky adapter boundary.*
- **C**: Patterns exist but inconsistently applied. *E.g. some core logic leaked into a UI component, mixed styling, or tenant checks that lean on the UI more than the data layer.*
- **D**: No clear pattern — logic/data/rendering entangled, formulas diverge from spec, or tenant isolation is UI-only.

---

## Dimension 5: Validation & Quality Assurance

**Question:** Is the validation strategy honest and adequate across the workspace?

### Review signals
- **Testing reality**: grade against whether the repo's own suites actually cover each component's core invariants and edge cases.
- **Multi-tenant safety net** (if applicable): does the isolation test suite actually assert cross-tenant isolation (tenant A cannot read/write tenant B's rows)? This is typically the highest-stakes correctness property in a multi-tenant repo — a hole here is a data-leak, not a cosmetic bug.
- **Smoke/e2e currency**: do the repo's own smoke/e2e scripts still match the current UI (selectors, strings, flow)? Would they pass today?
- **Build/lint/test as the safety net**: clean (from Mechanical Facts)? Is the type surface strong enough to catch domain misuse across package boundaries?
- **Core-logic edge cases**: empty/degenerate input, all-excluded selection, zero/negative input, a zero-denominator division guard — handled, or a crash?
- **Input validation**: do intake forms guard required inputs before proceeding?
- **Honesty of any demo/prototype component**: is it clear which data is mock, and are any intentional simulated-latency delays documented as fake work? Is any gap between an intended-testing spec and reality acknowledged?

See `references/project-context.md` for this repo's own concrete signal list, grep hints, and calibration examples.

### Grade definitions
- **A**: Suites cover each component's core invariants; the isolation suite (if any) proves cross-tenant isolation; smoke/e2e are current; build+lint+test clean; core logic guards its edge cases (no crash on degenerate input); any mock/intended-testing gap is documented.
- **B**: Good coverage and a green build/lint/test, but 1-2 edge cases unguarded, isolation coverage thin, or a documented gap only lightly covered.
- **C**: A smoke/e2e script is stale (wouldn't pass), OR several edge cases crash, OR isolation is under-tested, OR lint/build warnings left unaddressed.
- **D**: No working validation of a whole product — a suite/smoke script broken or absent and build or lint failing, with no acknowledgment; or tenant isolation entirely untested.

---

## Overall Verdict

Derived from dimension grades:

| Verdict | Criteria |
|---------|----------|
| **EXEMPLARY** | All dimensions A or B, no dimension below B |
| **STRONG** | Majority A/B, at most one C, no D |
| **SOLID** | Majority B/C, no more than one D |
| **NEEDS WORK** | Two or more D grades, or majority C/D |
