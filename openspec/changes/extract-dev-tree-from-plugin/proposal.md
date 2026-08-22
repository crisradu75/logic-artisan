## Why

The `cla` plugin ships from `.claude/plugins/cla/` as one `git-subdir` snapshot — the whole
directory, with no exclusion field — and 71 of its 171 tracked files (41.5%) are validation machinery
a consumer cannot invoke: every `tests/` tree, every `mutants/` corpus, 12 `pyproject.toml`,
`run_tests.py`, `mutate.py`, the three `SOURCE-REPO-ONLY.md` markers, and the Node test. One shipped
skill, `release`, is likewise unrunnable downstream: it edits the repo-root marketplace catalog a
consumer does not own and cuts `cla--v<version>` tags for this plugin.

Change (a), `decouple-skills-from-dev-assets`, has already cut every dependency a shipped procedure
had on that machinery. Nothing now reads it from a skill, so it can move.

**This change is the whole remainder of the program.** It was drafted as two — (b) a pure relocation
and (c) a guard-plus-documentation pass — and the split does not survive contact with
`consistency-checks/tests/test_doc_facts.py`. That file is a drift guard over this repo's own
documentation: it asserts that every stated pytest-scope count, every stated skills-shipping-tests
count, the root `README.md`'s workflow-skill count, and every concrete `.claude/plugins/cla/...`
path named in four documents is true of the tree. Relocation makes all four false at once. A change
that moves the tree and defers the documentation therefore leaves its **own** gate — bare `pytest`
— red by construction, and a change that cannot go green cannot be reviewed, merged, or reverted
independently. Measured: 16 concrete plugin paths are named across the four guarded documents and
**10 of those mentions stop resolving** the moment the move lands
(`scratchpad/docpaths.py`, the enumeration in this change's own scratch file, run against
`test_doc_facts.py::test_no_doc_names_a_plugin_path_that_no_longer_exists`'s own regex and `_DOCS`
map). Relocation and doc reconciliation are one change because the repo's own guard says so.

**The name undersells it, deliberately kept anyway.** `extract-dev-tree-from-plugin` names the
largest mechanical part. This change also (i) adds the **release-time shipped-tree scan** that keeps
the plugin lean afterwards, and (ii) **reconciles every document, overlay, and guard** that
describes the old layout. Renaming the change would cost a third directory and a fresh set of
cross-references for no gain; the scope is stated here instead. Read this proposal, not the
directory name, for what the change covers.

This is the second and final change from
`cla.io/decisions/ship-only-consumer-usable-assets-2026-08-22.md`, superseding the decision doc's
(b)/(c) split. It must land strictly after (a).

## What Changes

### Part 1 — the relocation

- **Every dev-only asset moves out of the plugin into `<repo>/plugin-tests/`.** Each `tests/`
  directory under `.claude/plugins/cla/`, each `mutants/` directory, each `pyproject.toml`, and
  `skills/project-review/scripts/mechanical-checks.test.mjs` relocate there, **collapsing the 12
  isolated pytest scopes into one** with a single `pyproject.toml`. The collapse is possible because
  change (a) renamed the colliding `aggregate.py` / `test_aggregate.py` module pairs — and because
  the second collision the runner claims does not exist (see design.md D1).

- **`conformance-checks/` disappears from the plugin.** Change (a) promoted its two
  downstream-live guards to skill scripts; the three that read the *plugin's own* data —
  `test_no_hardcoded_plugin_paths.py`, `test_skill_lint.py`, `test_guards_are_not_vacuous.py` —
  move to the dev tree with everything else.

- **`consistency-checks/` and `launcher-checks/` move in full**, including
  `consistency-checks/scripts/check_script_drift.py` (a script, not a test — it moves because its
  whole subject is this repo's own source).

- **`mutate.py` MOVES to the dev tree. `run_tests.py` is DELETED.** These are different
  dispositions, not one. Q2 sends both runners out of the plugin; Q4 supersedes it for
  `run_tests.py` specifically, because a single pytest scope needs no aggregating runner. **The
  shipping gate becomes bare `pytest` from the repo root.**

- **The `release` skill moves to `<repo>/.claude/skills/release/`** and becomes a repo-local skill
  invoked as `/release` rather than `/cla:release`. Its `${CLAUDE_PLUGIN_ROOT}/…` references become
  plain repo-relative paths, and its `run_tests.py` precondition — dangling the moment this change
  deletes that file — is re-pointed at the bare-`pytest` gate.

- **The three `SOURCE-REPO-ONLY.md` markers and `consistency-checks/tests/test_source_only_markers.py`
  are deleted.** Once the dev tree never ships, every asset in it is source-repo-only by
  construction: the marker mechanism, its guard, and `run_tests.py`'s skip logic all lose their
  subject at once.

- **`lib/log_run.py` STAYS in the plugin.** It is shipped code — every retro-logging skill invokes
  it as a program. Only `lib/tests/` moves.

### Part 2 — the guards the move breaks, repaired rather than relaxed

Six guards resolve their subject by a hardcoded scope-directory literal or a numeric floor over a
set the move empties. Each one **fails loudly**, which is why they are in scope rather than
deferred, and each is re-pointed with its floor **re-derived by running it** — never lowered to go
green. Enumerated with measurements in design.md D9; the load-bearing cases are
`test_guards_have_mutant_batches.py`, `test_guards_are_not_vacuous.py`,
`test_subprocess_encoding.py`, `test_doc_facts.py`, `check_script_drift.py`, and
`skills/release/tests/test_release_preconditions.py`.

### Part 3 — the release-time scan

- **A shipped-tree scan becomes a `release` precondition**, as
  `<repo>/.claude/skills/release/scripts/check_shipped_tree.py`, alongside the four preconditions
  already there. It refuses the release rather than warning, and it lives outside the plugin with
  the repo-local skill it serves.

- **The scan is a structural allowlist**, pinned at **14 patterns** plus one leaf-name exclusion.
  The earlier 11-pattern draft was measured against planted files and **admitted four dev-asset
  shapes** a denylist catches; patterns 7 and 11 are tightened accordingly and the "strict superset
  of the denylist" claim is withdrawn and replaced with a measurement (design.md D1a).

### Part 4 — the documentation reconciliation

- **Two false claims about what reaches a consuming repo are deleted, not reworded**: the root
  `.gitattributes` bullet claiming a `hooks/tests/` test "ships with the plugin, so it also fires in
  a consuming repo", and `CLAUDE.md`'s "`conformance-checks` is portable core that reaches consuming
  repos".

- **Every layout document is reconciled**: `CLAUDE.md`, the plugin `README.md`, the root
  `README.md`, `DEVELOPER-GUIDE.md`, `TODO.md`, and the live `cla.io/overlays/codify-learnings.md`.
  Every count written into prose is the recorded output of a command run in the same commit.

- **Two shipped files that mandate the deleted runner are fixed**:
  `.claude/plugins/cla/skills/_shared/README.md` (the near-miss rule) and
  `.claude/plugins/cla/skills/_shared/references/skill-authoring.md` (`"`run_tests.py` exits 0 with
  no near-miss warning"` as the model of a checkable done-condition). Both are in the published
  tree, so both would otherwise ship a command that no longer exists to every consuming repo.

Not breaking for consumers of any skill except `release`: no shipped skill loses a capability, and
nothing a consumer invokes today disappears. `/cla:release` does disappear — **BREAKING** for any
consumer who invoked it, though invoking it downstream never did anything useful (it edits a catalog
and tags a plugin that a consumer does not own).

## Capabilities

### New Capabilities

None — no new spec file. Both rules belong to the existing `cla-plugin` spec, which already owns the
core/state boundary and the activation model.

### Modified Capabilities

- `cla-plugin`: **two requirements added, three modified.**
  - **ADDED — Shipped-asset boundary** (7 scenarios). The substantive rule: `.claude/plugins/cla/`
    SHALL contain only assets a consuming repo can use, because `git-subdir` has no exclusion field
    and everything under `path` ships; the plugin's own validation machinery lives at
    `<repo>/plugin-tests/` as a single pytest scope; the verification gate is bare `pytest`; a
    workflow that operates on the plugin's own *distribution* is repo-local, not shipped; the
    boundary is enforced at the publication gate rather than in the suite, with the week-one drift
    window stated as an accepted cost; and a documentation claim about what reaches a consumer is
    inside the boundary, deleted rather than softened once false.
  - **ADDED — Release-time shipped-asset scan** (8 scenarios). The publication workflow SHALL verify
    the boundary mechanically before cutting a tag: a structural allowlist over the repository's
    *tracked* files, every offending file named in one run, refusal rather than warning, a distinct
    "could not run" status when the enumeration is empty, a recorded reason per allowlist entry
    under a capped count, **a declared shape narrow enough to reject a dev asset placed inside an
    otherwise-shipped directory**, and the scan itself living outside the published tree.
  - **MODIFIED — Core/state boundary** (1 → 2 scenarios). The plugin directory currently has exactly
    two declared companions (`cla.io/`, `.claude/`). The dev tree is a third kind of asset, so
    without this edit the two requirements contradict. It gains `<repo>/plugin-tests/` as the third
    home and a pointer to the added requirement.
  - **MODIFIED — In-place activation and namespacing** (3 → 4 scenarios). Currently reads "Each
    workflow SHALL be a skill … and SHALL be invoked under the plugin namespace as `/cla:<skill>`."
    After this change `release` is repo-local at `<repo>/.claude/skills/release/` invoked as
    `/release`, so the requirement needs the carve-out.
  - **MODIFIED — Conformance guard for the overlay separation** (8 in the main spec → 10 after (a) →
    11 here). Change (a)'s final text states a known coverage gap: "files outside the checker's scan
    roots — `lib/`, the `*-checks/` scopes, `run_tests.py`, `mutate.py` — ship to consumers
    unscanned". This change makes that false by removing all but `lib/` from the shipped tree. The
    paragraph is rewritten rather than deleted: `lib/` still ships and is still outside the scan
    roots, so a real gap survives, just a much smaller one. The eleventh scenario requires every
    scan root to name a directory that still ships.

**Deliberately NOT modified:** *Project-facts staleness guard*. Change (a) already re-homed it to
`skills/sync-context/scripts/check_fact_paths.py` as a program needing no pytest; nothing in that
requirement's post-(a) text names `conformance-checks/`, the dev tree, or a runner, so this change
falsifies none of it. *Repo-state resolution seam* is likewise untouched — the two aggregators it
names stay in the plugin, and only their tests move.

## Impact

**Scale:** roughly 71 files move, plus a documentation reconciliation across six files. The failure
mode is a silently dropped test, so this change carries a before/after collected-test count as a
hard gate rather than a green suite as evidence.

**Moved into `<repo>/plugin-tests/`** (one pytest scope, one `pyproject.toml`):
- every `tests/` directory under `.claude/plugins/cla/` — the 6 test-bearing skills, plus
  `skills/_shared/`, `lib/`, `hooks/`, `conformance-checks/`, `consistency-checks/`,
  `launcher-checks/`
- every `mutants/` directory, `mutate.py`
- `consistency-checks/scripts/check_script_drift.py` — **the only `scripts/` directory in the three
  `*-checks/` scopes.** `launcher-checks/` has **no** `scripts/` directory (`git ls-files
  .claude/plugins/cla/launcher-checks` → 4 files: `SOURCE-REPO-ONLY.md`, `pyproject.toml`,
  `tests/conftest.py`, `tests/test_cla_launcher.py`), which is why its dead
  `pythonpath = ["scripts"]` entry is dropped rather than carried.
- `skills/project-review/scripts/mechanical-checks.test.mjs`

**Moved to `<repo>/.claude/skills/release/`:** the whole `skills/release/` tree (`SKILL.md`), which
then gains `scripts/check_shipped_tree.py` — **2 files**, not 1.

**Added:** `<repo>/.claude/skills/release/scripts/check_shipped_tree.py`,
`plugin-tests/tests/skills/release/test_check_shipped_tree.py`,
`plugin-tests/mutants/release/test_check_shipped_tree.py`.

**Deleted:** `.claude/plugins/cla/run_tests.py`; the three `SOURCE-REPO-ONLY.md`
(`consistency-checks/`, `launcher-checks/`, `skills/release/`);
`consistency-checks/tests/test_source_only_markers.py` and its mutant batch;
`consistency-checks/tests/test_runner_stream_encoding.py` and its `_EXEMPT` entry;
`test_doc_facts.py::test_the_scope_discovery_rule_here_matches_what_run_tests_finds`.

**Stays in the plugin:** `lib/log_run.py`, every skill except `release`, `agents/`, `hooks/*.py` and
`hooks/hooks.json`, `output-styles/`, `.claude-plugin/plugin.json`, the plugin `README.md`, and the
two guards change (a) promoted (`skills/sync-context/scripts/check_fact_paths.py`,
`skills/_shared/scripts/check_no_project_tokens.py`).

**Edited (documentation and live overlays):** `CLAUDE.md`, root `README.md`, `DEVELOPER-GUIDE.md`,
`TODO.md`, root `.gitattributes`, `.claude/plugins/cla/README.md`,
`.claude/plugins/cla/skills/_shared/README.md`,
`.claude/plugins/cla/skills/_shared/references/skill-authoring.md`,
`cla.io/overlays/codify-learnings.md`.

**Not edited:** `cla.io/decisions/`, `cla.io/lessons-learned/`, `cla.io/feedback/`,
`cla.io/checkpoints/`, `cla.io/retro/*.jsonl` — historical records of what was true when written.

**The load-bearing risk, and what catches it.** Every moved test resolves its subject by a
`Path(__file__).resolve().parents[N]` walk, and every `pythonpath` entry is relative to the scope
root. A tree move invalidates all of them, and the dangerous ones do not fail loudly — a wrong `N`
commonly lands on a plausible directory, so a test keeps passing while scanning nothing. The change
therefore requires: (1) `pytest --collect-only -q` captured before the move and asserted against a
re-derived arithmetic delta after; (2) an explicit audit that every `parents[N]` walk and every
`pythonpath` entry was re-pointed and resolves to what it names; (3) `git mv` for every move, so
each shows as a rename rather than delete+add; and (4) every numeric floor over a moved set
re-derived by running it.

**Interaction with change (a):** (a)'s tasks 3.7 and 6.1 edit and run `run_tests.py`. This change
deletes that file, so it must land strictly after (a). (a)'s task 3.10 finding on
`check_script_drift.py` is resolved here — and answered in advance from source, in design.md D5.

**Out of scope:** cutting the `0.11.0` release itself. The decision doc anticipates that version,
but a tag is cut deliberately from reviewed and merged work, and a published tag cannot be
corrected. This change adds the precondition; it does not exercise it.
