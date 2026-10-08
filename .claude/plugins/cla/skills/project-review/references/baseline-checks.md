# Baseline Checks

Deterministic checks the orchestrator runs **before** launching review agents. They produce a **Baseline Facts** table every agent receives as pre-verified input — agents should NOT re-check these; they focus on qualitative judgment instead.

This repo's exact commands come from `cla.io/project-facts.md` ("Dev / build / test commands"; run `/cla:cla-setup` when it is missing or stale), including any suite excluded from the aggregate (e.g. one needing live local infra).

These are already deterministic exit-code checks. **Run them directly; do not re-implement them.** Running the workspace test suite is what makes per-package/per-app invariants pre-verified, so the review needn't hand-check them. Cross-file checks a repo wants enforced — key-set parity between locale files, import boundaries — belong in that repo's own test suite, where this step picks them up.

## 1. Build health
Run this repo's own build command (from `cla.io/project-facts.md`).
- **PASS:** exits 0. **FAIL:** capture the first errors (file:line + message) and which project.

## 2. Lint
Run this repo's own lint command (from `cla.io/project-facts.md`).
- **PASS:** no errors. **FAIL:** count + first offenders + which project.

## 3. Unit tests
Run this repo's own test command (from `cla.io/project-facts.md`).
- **PASS:** all pass. **FAIL:** failing test name(s) + assertion + which project.
- **Any suite this repo deliberately excludes from the aggregate** (typically one needing live local infra, e.g. a database stack) is recorded as **SKIP** unless that infra is already up and you deliberately run it — see `cla.io/project-facts.md` for whether this repo has one and what it is. If you do run it, a FAIL here is high-severity per that same reference.

## Not checked here — smoke-test string drift
Whether an edit-time hook already guards smoke/e2e-script string drift (and what it does vs. doesn't cover) is repo-specific — `cla.io/overlays/project-review.md` says so if this repo has one. Whether the whole smoke/e2e flow is still *current end-to-end* stays a qualitative call for the Validation dimension regardless.

---

## Output Format: Baseline Facts Table

```
### Baseline Facts (pre-verified)

| Check | Status | Details |
|-------|--------|---------|
| Workspace build | PASS/FAIL | {"exits 0" or first errors + project} |
| Workspace lint | PASS/FAIL | {"clean" or count + first offenders} |
| Workspace tests | PASS/FAIL | {"all pass" or failing tests + project} |
| {this repo's excluded live-infra suite, if any} | PASS/FAIL/SKIP | {"not run (no local stack)" or result} |
```

Print any FAIL to the user immediately:
```
[Project Review] ⚠ {check}: {details}
```

Then include the full table in every agent prompt.
