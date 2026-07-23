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

Fast (<1s), exit code 0 for a normal run (`FAIL`/`ERROR` rows are data, not a gate; only a malformed config block exits non-zero). The script itself is a **generic, repo-agnostic engine** — it hardcodes no paths, packages, or app names. It performs the deterministic cross-file checks **not** covered by build/lint/test, driven entirely by this repo's own check list, which lives in `references/project-context.md` ("Mechanical checks — repo specifics") as a fenced ```json``` block (an untagged ``` fence also works, but a ```json-tagged one is preferred when more than one fence sits under the heading):

```json
{
  "checks": [
    { "type": "json-key-parity", "name": "...", "files": ["path/a.json", "path/b.json"] },
    { "type": "json-key-usage", "name": "...", "localeFiles": ["path/en.json", "path/ro.json"],
      "sourceDirs": ["path/to/src"], "keyPattern": "\\bt\\(\\s*['\"]([^'\"]+)['\"]", "extensions": [".ts", ".tsx"] },
    { "type": "derived-key-consistency", "name": "...",
      "sources": [
        { "kind": "regex-array", "file": "path/domain.ts", "pattern": "KEYS\\s*=\\s*\\[([^\\]]+)\\]", "flags": "s", "label": "domain.ts" },
        { "kind": "json-array-field", "file": "path/data.json", "field": "key", "label": "data.json" }
      ],
      "deriveLocale": { "template": "dashboard.foo.{key}", "localeFiles": ["path/en.json", "path/ro.json"] } },
    { "type": "import-boundary", "name": "...", "sourceDir": "path/to/src", "forbidden": ["react", "react-dom"],
      "extensions": [".ts", ".tsx"], "reason": "must stay Node-safe", "passMessage": "..." },
    { "type": "cross-import-ban", "name": "...", "pairs": [
      { "sourceDir": "apps/a/src", "forbidden": ["apps/b", "b-app-name"], "extensions": [".ts", ".tsx"] },
      { "sourceDir": "apps/b/src", "forbidden": ["apps/a", "a-app-name"] }
    ], "passMessage": "..." }
  ]
}
```

All paths in the config are repo-relative (resolved from the repo root, not this file). `forbidden`/`pairs` entries match by exact string or substring, so pin as loosely or tightly as needed — e.g. `"react"` also matches `"react-dom"` and `"preact"`, so tighten to a more specific token if that's not intended. `import-boundary`/`cross-import-ban` scan `.ts`/`.tsx` by default (override per check, or per pair, via `extensions`) and detect a forbidden specifier via a static `from '...'`, `require('...')`, `import('...')`, or bare `import '...'`. No block, an empty `checks` array, or a missing overlay all mean "no checks configured" — a trivial PASS, not a crash on paths from wherever this script was first written. Run `/cla:sync-context` to populate this section for a fresh repo (or author it by hand). (For test authoring: `MECHANICAL_CHECKS_ROOT` and `MECHANICAL_CHECKS_OVERLAY` env vars override, respectively, the resolved repo root and the overlay file `loadConfig()` reads — see the sibling `mechanical-checks.test.mjs`.)

A `regex-array` source's optional `flags` (e.g. `"s"` to let `.` match newlines) may be any regex flags except `g`, which is always stripped — the pattern is expected to have exactly one capture group and match once (`text.match(re)`), a shape `g` breaks (it returns whole-match strings with no capture groups instead).

Each check's result is `PASS`, `FAIL` (the check ran and found a real problem — e.g. a key mismatch or a forbidden import), or `ERROR` (the check itself couldn't run meaningfully — an unrecognized `type`, or a thrown exception from a bad path/malformed source file/misconfigured field). Treat `ERROR` as "fix the check's config," not as a review finding about the repo.

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
| {one row per this repo's own static-analysis checks} | PASS/FAIL/ERROR | {result, or the diff/mismatch; ERROR means the check's own config is broken, not a repo finding} |
```

Print any FAIL to the user immediately:
```
[Project Review] ⚠ {check}: {details}
```

Then include the full table in every agent prompt.
