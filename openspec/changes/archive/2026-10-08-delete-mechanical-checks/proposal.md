## Why

`project-review` shipped the plugin's one Node script, `mechanical-checks.mjs`, a cross-file
key-parity engine driven by a JSON block in the repo's overlay. No repo on the marketplace plugin
configures it; the one that does (agentic-air) runs its own vendored copy, which keeps working. The
script also kept a second test command (`node --test`) in every pre-PR and release gate. This is
P4a of the 2026-10-08 plugin-surface simplification.

## What Changes

- Delete `project-review/scripts/mechanical-checks.mjs` and its `node --test` suite.
- `project-review` keeps its five review dimensions. Step 0 runs only the repo's own build, lint and
  test commands; its reference is renamed `baseline-checks.md` and says that cross-file checks a repo
  wants belong in that repo's own tests. The skill drops its placeholder resolver paragraph, since
  no reference carries a placeholder command any more.
- The shipping gate is two commands, pytest and `openspec validate --specs --strict`: CLAUDE.md,
  DEVELOPER-GUIDE, both READMEs, `cla.io/project-facts.md` and `/release`'s Step 1 and Step 3.
- `check_shipped_tree.py` allows only `.py` under `skills/*/scripts/`; `norecursedirs` drops `node`;
  the scanners stop listing `.mjs`, with their floors and recorded counts re-measured.

No live spec promises the checks, so there is no spec delta (`skip_specs`).

**Rules dropped (CLAUDE.md check 2).** The overlay's "Mechanical checks — repo specifics" JSON
schema and its PASS/FAIL/ERROR semantics, which existed only for the script. Part A (build, lint,
test) and the Mechanical Facts table are kept as written.
