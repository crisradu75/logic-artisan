# Mechanical Checks

Deterministic checks the orchestrator runs **before** launching review agents. They produce a **Mechanical Facts** table every agent receives as pre-verified input — agents should NOT re-check these; they focus on qualitative judgment instead.

This repo's monorepo shape and the exact commands/checks below are repo-specific — see `cla.io/project-facts.md` ("Dev / build / test commands") for the concrete build/lint/test invocations and any repo-specific exclusion (e.g. a suite needing live local infra), run `/cla:sync-context` to populate it, falling back to `references/project-context.md` ("Mechanical checks — repo specifics") if absent; that same overlay also carries the static-analysis script's exact check list (skill-specific, not moved). This file holds the portable *shape*: what the workspace tooling already verifies (run directly) and what a small script verifies (the fast static analysis the model would otherwise hand-grep inconsistently).

---

## Part A — delegated to workspace tooling

These are already deterministic exit-code checks. **Run them directly; do not re-implement them.** Running the workspace test suite is what makes per-package/per-app invariants pre-verified, so the review needn't hand-check them.

### 1. Build health
Run this repo's own build command (per `cla.io/project-facts.md`, falling back to `references/project-context.md`).
- **PASS:** exits 0. **FAIL:** capture the first errors (file:line + message) and which project.

### 2. Lint
Run this repo's own lint command (per `cla.io/project-facts.md`, falling back to `references/project-context.md`).
- **PASS:** no errors. **FAIL:** count + first offenders + which project.

### 3. Unit tests
Run this repo's own test command (per `cla.io/project-facts.md`, falling back to `references/project-context.md`).
- **PASS:** all pass. **FAIL:** failing test name(s) + assertion + which project.
- **Any suite this repo deliberately excludes from the aggregate** (typically one needing live local infra, e.g. a database stack) is recorded as **SKIP** unless that infra is already up and you deliberately run it — see `cla.io/project-facts.md` (falling back to `references/project-context.md`) for whether this repo has one and what it is. If you do run it, a FAIL here is high-severity per that same reference.

## Part B — the static-analysis script

```bash
node .claude/plugins/cla/skills/project-review/scripts/mechanical-checks.mjs        # human table
node .claude/plugins/cla/skills/project-review/scripts/mechanical-checks.mjs --json  # machine-readable
```

Fast (<1s), exit code always 0 (findings are data, not a gate). It performs the deterministic cross-file checks **not** covered by build/lint/test — this repo's exact check list (what each one verifies and its PASS/FAIL wording) lives in `references/project-context.md` ("Mechanical checks — repo specifics").

### Not checked here — smoke-test string drift
Whether an edit-time hook already guards smoke/e2e-script string drift (and what it does vs. doesn't cover) is repo-specific — see `references/project-context.md`. Whether the whole smoke/e2e flow is still *current end-to-end* stays a qualitative call for the Validation dimension regardless.

---

## Output Format: Mechanical Facts Table

Merge Part A + Part B into one table:

```
### Mechanical Facts (pre-verified)

| Check | Status | Details |
|-------|--------|---------|
| Workspace build | PASS/FAIL | {"exits 0" or first errors + project} |
| Workspace lint | PASS/FAIL | {"clean" or count + first offenders} |
| Workspace tests | PASS/FAIL | {"all pass" or failing tests + project} |
| {this repo's excluded live-infra suite, if any} | PASS/FAIL/SKIP | {"not run (no local stack)" or result} |
| {one row per this repo's own static-analysis checks} | PASS/FAIL | {result, or the diff/mismatch} |
```

Print any FAIL to the user immediately:
```
[Project Review] ⚠ {check}: {details}
```

Then include the full table in every agent prompt.
