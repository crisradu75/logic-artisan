## Why

The `cla` plugin ships from `.claude/plugins/cla/` as one `git-subdir` snapshot — the whole
directory, with no exclusion field — and 41% of that payload is validation machinery a consumer
cannot invoke. Before any of it can be moved out, three shipped procedures have to stop depending
on it: `lite-pr` and `revise.md` both mandate `python3 ${CLAUDE_PLUGIN_ROOT}/mutate.py`, and the two
conformance guards that genuinely run against a *consuming* repo's data are reachable only as pytest
modules inside a scope that is about to disappear.

This is change (a) of a **two**-change batch from
`cla.io/decisions/ship-only-consumer-usable-assets-2026-08-22.md` (deleted 2026-08-24; recover with
`git show eaa579b:<that path>`). The other is
`extract-dev-tree-from-plugin`, the single successor that carries everything the decision doc
sketched as changes (b) and (c): moving every dev-only asset out of the published plugin tree,
relocating the `release` skill to `<repo>/.claude/skills/release/`, adding a release-time
shipped-tree scan, and reconciling the docs.

This change is deliberately all in-place content edits and **no file moves**, so each rewrite lands
against a file that has not moved and the diff shows what changed rather than that it moved. Git
renders a rewritten-and-moved file as delete+add, which would make the highest-risk edits here the
least reviewable if bundled with the ~70 renames the successor performs.

## What Changes

- **Promote the two downstream-live conformance guards to skill scripts.** Each becomes a program
  with a `main()` and an exit code (0 clean, non-zero with the offending paths named), not a pytest
  module:
  - `conformance-checks/tests/test_project_facts_paths.py` →
    `skills/sync-context/scripts/check_fact_paths.py`
  - `conformance-checks/tests/test_no_project_tokens.py` →
    `skills/_shared/scripts/check_no_project_tokens.py`

  The split criterion is **whose data a guard reads**: these two read the consuming repo's
  (`cla.io/project-facts.md`, `cla.io/overlays/`, `cla.io/project-tokens.local.md`), and commit
  `a9ea9cf` records that they were deliberately engineered to run from an installed copy against a
  consuming repo — and, once fixed, "immediately found a stale path there that had been invisible".
  Their existing pytest tests **stay in `conformance-checks/tests/` for now** and are re-pointed at
  the new modules; `extract-dev-tree-from-plugin` relocates those tests. Each promoted script is a
  new script under root `CLAUDE.md`'s rule, so each ships with a mutant batch alongside its tests.

- **Downgrade the mutation gate to prose** in `skills/lite-pr/SKILL.md` step 2b and
  `skills/spec-to-pr/references/revise.md` step 2b. The gate stays required before the commit in
  step 3; only the `python3 ${CLAUDE_PLUGIN_ROOT}/mutate.py <batch.py>` invocation goes, replaced by
  "break what the fix touches and confirm a test fails". **Every other rule in those two blocks is
  preserved verbatim** — they carry named precedents (the default-path/overlay-path no-op; the two
  commits that recorded "three mutations checked, all caught" and each shipped a critical) that must
  survive.

- **Rename both `aggregate.py` modules** to distinct names, with their `test_aggregate.py`
  counterparts, and update every SKILL.md line, import, and hardcoded path list that names them.
  The rename is **not** fixing a collision that bites today — see design.md D0: the two test files
  already load their aggregator by explicit path under distinct module names, and `run_tests.py`
  runs every scope as its own subprocess, so the two are never in one process together. It is a
  **forward dependency on `extract-dev-tree-from-plugin`**, which consolidates all twelve scopes
  into one `plugin-tests/` scope; that successor's own design measures the duplicate test basenames
  across all 49 test files and finds exactly `conftest.py` and `test_aggregate.py`, with
  `test_aggregate.py` "renamed by change (a)". Without this rename, pytest collection in the
  consolidated scope breaks on the duplicate basename.

- **Fix the doc lines this change falsifies** — `skills/sync-context/SKILL.md:151` and
  `skills/_shared/references/skill-authoring.md:39` name the two promoted guards by their old
  `conformance-checks/tests/…` paths, and `CLAUDE.md:259`'s script table names
  `codify-retro`, `spec-to-pr-retro` `scripts/aggregate.py`. The broad layout reconciliation is
  deferred to `extract-dev-tree-from-plugin`.

Not breaking for consumers: no skill is removed, no invocation a consumer relies on disappears —
`mutate.py` itself still exists in the tree after this change (`extract-dev-tree-from-plugin`
moves it to `<repo>/plugin-tests/mutate.py`).

## Capabilities

### New Capabilities

None. Every behaviour this change alters is already covered by the `cla-plugin` spec.

### Modified Capabilities

- `cla-plugin`: three requirements change.
  - **Conformance guard for the overlay separation** — the token guard stops being "a pytest test"
    living in `conformance-checks/` and becomes a skill script invoked as a program with an exit
    code. Its scan scope, exclusions, token-list-as-overlay contract, failure output, and
    absent-vs-empty semantics are all unchanged.
  - **Project-facts staleness guard** — same shape: it stops being "a pytest test alongside the
    conformance guard under `.claude/plugins/cla/conformance-checks/tests/`" and becomes
    `sync-context/scripts/check_fact_paths.py`, a program with an exit code. Its extraction rules,
    stack-agnosticism, repo-derived prefixes, and stated coverage limits are unchanged.
  - **Repo-state resolution seam** — names "each retro loop's `aggregate.py`", which the rename
    falsifies. The seam's actual rule (resolve `CLAUDE_RETRO_DIR`, else
    `<git rev-parse --show-toplevel>/cla.io/retro`) is unchanged; only the module names it cites
    move, and the distinct-name rule is restated on its real (forward-dependency) grounds.
  - Plus one **new requirement** added to the same spec, **Review-fix evidence gate**, pinning the
    prose form of the mutation gate so the rule survives `mutate.py` leaving the plugin tree in
    `extract-dev-tree-from-plugin`.

## Impact

**Files rewritten (highest risk):**
- `.claude/plugins/cla/conformance-checks/tests/test_project_facts_paths.py` (897 lines) → new
  module at `skills/sync-context/scripts/check_fact_paths.py`
- `.claude/plugins/cla/conformance-checks/tests/test_no_project_tokens.py` (899 lines) → new module
  at `skills/_shared/scripts/check_no_project_tokens.py`

Both are the "rewrote a file rather than edited it" shape root `CLAUDE.md` warns about. Note in
particular that `test_no_project_tokens.py` carries **four** repo-level assertions
(`test_no_project_tokens_in_synced_core`, `test_no_project_tokens_in_synced_source`,
`test_no_absolute_developer_paths_in_synced_source`, `test_every_scanned_file_is_actually_readable`)
— all four must reach `main()`, and dropping one is invisible.

**Files edited in place:**
- `skills/lite-pr/SKILL.md` (step 2b, line 132)
- `skills/spec-to-pr/references/revise.md` (step 2b, line 97)
- `skills/sync-context/SKILL.md` (line 151)
- `skills/_shared/references/skill-authoring.md` (line 39)
- `skills/codify-retro/SKILL.md` (line 29), `skills/spec-to-pr-retro/SKILL.md` (line 27)
- `CLAUDE.md` (line 259 only — the script-table row this change falsifies)

**Files renamed (module renames, not tree moves):**
- `skills/codify-retro/scripts/aggregate.py`, `skills/spec-to-pr-retro/scripts/aggregate.py`
- `skills/codify-retro/tests/test_aggregate.py`, `skills/spec-to-pr-retro/tests/test_aggregate.py`

**Consumers of the renamed modules that hardcode the old paths** (not named in the decision doc;
found by grep, and each will break silently if missed):
- `consistency-checks/scripts/check_script_drift.py` — two path lists plus a check name
- `consistency-checks/tests/test_ledger_names_agree.py` — two `_PLUGIN_ROOT / … / "aggregate.py"`
  constructions
- `consistency-checks/tests/test_check_script_drift.py` — an expected-paths fixture
- `run_tests.py` module docstring, which justifies the multi-scope split by naming the collision

**Consumer of the *promoted* guard module** (a second, distinct enumeration — this one breaks on the
promotion, not on the rename):
- `consistency-checks/tests/test_token_list_is_curated_here.py` does
  `sys.path.insert(0, str(_GUARD.parent))` then `import test_no_project_tokens as guard`, where
  `_GUARD` is hardcoded as `_PLUGIN_ROOT / "conformance-checks" / "tests" /
  "test_no_project_tokens.py"` (lines 24–25, 38–42). It then reads three symbols off that module:
  `guard._repo_root()`, `guard.TOKEN_LIST_RELPATH`, and `guard.load_tokens`. All three must survive
  the promotion as **module-level names on the promoted script**, not be folded into `main()`.
  Its own `_load_guard` docstring says why it asks the guard rather than recomputing: *"a version of
  this check that computed its own repo root passed happily while the guard's anchor was off by one
  level and the guard skipped."* Leaving it importing a module whose implementation has moved would
  break the guard that guards the token list — the precise failure it exists to catch.

**New mutant batches:** each promoted script is a new script, so root `CLAUDE.md`'s rule 4 applies.
Batches land under `conformance-checks/mutants/` with the same basename as the guard test they
cover — the pairing `consistency-checks/tests/test_guards_have_mutant_batches.py` already enforces.

**New directory:** `skills/sync-context/scripts/` does not exist yet (the skill is `SKILL.md` only).

**Test scopes touched:** `conformance-checks/`, `consistency-checks/`, `codify-retro/`,
`spec-to-pr-retro/`. `run_tests.py` remains the gate for this change
(`extract-dev-tree-from-plugin` deletes it).

**Automatic coverage after this change:** both promoted checkers become manually-invoked skill
helpers with **no automatic trigger** in this repo. That is not a temporary state pending the
successor — see design.md's Risks section and Open Questions.

**Out of scope**, and owned by `extract-dev-tree-from-plugin`: moving anything to
`<repo>/plugin-tests/`; deleting `run_tests.py` or moving `mutate.py`; moving the `release` skill to
`<repo>/.claude/skills/release/`; the release-time shipped-tree scan; and the layout/scope-count
reconciliation across `CLAUDE.md`, `DEVELOPER-GUIDE.md`, the plugin `README.md`, root
`.gitattributes`, and `TODO.md`.
