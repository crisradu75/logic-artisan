## Why

The `cla` plugin ships from `.claude/plugins/cla/` as one `git-subdir` snapshot — the whole
directory, with no exclusion field — and 70 of its 171 tracked files (41%) are validation machinery
a consumer cannot invoke: every `tests/` tree, every `mutants/` corpus, 12 `pyproject.toml`,
`run_tests.py`, `mutate.py`, the three `SOURCE-REPO-ONLY.md` markers, and the Node test. One shipped
skill, `release`, is likewise unrunnable downstream: it edits the repo-root marketplace catalog a
consumer does not own and cuts `cla--v<version>` tags for this plugin.

Change (a), `decouple-skills-from-dev-assets`, has already cut every dependency a shipped procedure
had on that machinery. Nothing now reads it from a skill, so it can move. This is change (b) of
three from `cla.io/decisions/ship-only-consumer-usable-assets-2026-08-22.md`.

## What Changes

This change is a **pure relocation**: it moves and deletes, it does not rewrite content. Every
content rewrite happened in change (a), deliberately, so that each rewrite landed against a file
that had not moved. Git renders a rewritten-and-moved file as delete+add; keeping the two apart is
what makes both diffs reviewable.

- **Every dev-only asset moves out of the plugin into `<repo>/plugin-tests/`.** Each `tests/`
  directory under `.claude/plugins/cla/`, each `mutants/` directory, each `pyproject.toml`, and
  `skills/project-review/scripts/mechanical-checks.test.mjs` relocate there, **collapsing the 12
  isolated pytest scopes into one** with a single `pyproject.toml`. The collapse is possible only
  because change (a) renamed the two colliding module pairs (`aggregate.py`, `test_aggregate.py`) —
  those two collisions were the entire justification for the 12-scope split.

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
  deletes that file — is re-pointed at the bare-`pytest` gate **here, in this change**.

- **The three `SOURCE-REPO-ONLY.md` markers and `consistency-checks/tests/test_source_only_markers.py`
  are deleted.** Once the dev tree never ships, every asset in it is source-repo-only by
  construction: the marker mechanism, its guard, and `run_tests.py`'s skip logic all lose their
  subject at once.

- **`lib/log_run.py` STAYS in the plugin.** It is shipped code — every retro-logging skill invokes
  it as a program. Only `lib/tests/` moves.

Not breaking for consumers of any skill except `release`: no shipped skill loses a capability, and
nothing a consumer invokes today disappears. `/cla:release` does disappear — **BREAKING** for any
consumer who invoked it, though invoking it downstream never did anything useful (it edits a catalog
and tags a plugin that a consumer does not own).

## Capabilities

### New Capabilities

None — no new spec file. The rule this change establishes belongs to the existing `cla-plugin`
spec, which already owns the core/state boundary and the activation model. It enters that spec as
one **added requirement**, listed below with the three it modifies.

### Modified Capabilities

- `cla-plugin`: one requirement added, three modified.
  - **ADDED — Shipped-asset boundary.** The substantive rule: `.claude/plugins/cla/` SHALL contain
    only assets a consuming repo can use, because `git-subdir` has no exclusion field and everything
    under `path` ships; the plugin's own validation machinery lives at `<repo>/plugin-tests/` as a
    single pytest scope; the verification gate is bare `pytest`; and a workflow that operates on the
    plugin's own *distribution* rather than on a consuming repo's work is repo-local, not shipped.
    Change (c) adds the release-time scan that enforces this; the requirement states the rule the
    scan will check.
  - **Core/state boundary** — the plugin directory currently has exactly two declared companions
    (`cla.io/` for workflow data, `.claude/` for harness config). The dev tree is a third kind of
    asset, neither of those, so without this edit the two requirements contradict. It gains
    `<repo>/plugin-tests/` as the third home and a pointer to the added requirement above.
  - **In-place activation and namespacing** — currently reads "Each workflow SHALL be a skill … and
    SHALL be invoked under the plugin namespace as `/cla:<skill>`." After this change `release` is a
    repo-local skill at `<repo>/.claude/skills/release/` invoked as `/release`, so the requirement
    needs the carve-out.
  - **Conformance guard for the overlay separation** — change (a)'s final text states a known
    coverage gap: "files outside the checker's scan roots — `lib/`, the `*-checks/` scopes,
    `run_tests.py`, `mutate.py` — ship to consumers unscanned". This change makes that false by
    removing all but `lib/` from the shipped tree. The paragraph is rewritten rather than deleted:
    `lib/` still ships and is still outside the scan roots, so a real gap survives, just a much
    smaller one.

**Deliberately NOT modified:** *Project-facts staleness guard*. Change (a) already re-homed it to
`skills/sync-context/scripts/check_fact_paths.py` as a program needing no pytest; nothing in that
requirement's post-(a) text names `conformance-checks/`, the dev tree, or a runner, so this change
falsifies none of it. *Repo-state resolution seam* is likewise untouched — the two aggregators it
names stay in the plugin, and only their tests move.

## Impact

**Scale:** roughly 70 files move. The failure mode is a silently dropped test, so this change
carries a before/after collected-test count as a hard gate rather than a green suite as evidence.

**Moved into `<repo>/plugin-tests/`** (one pytest scope, one `pyproject.toml`):
- every `tests/` directory under `.claude/plugins/cla/` — the 6 test-bearing skills, plus
  `skills/_shared/`, `lib/`, `hooks/`, `conformance-checks/`, `consistency-checks/`,
  `launcher-checks/`
- every `mutants/` directory, `mutate.py`
- `consistency-checks/scripts/check_script_drift.py` and `launcher-checks/scripts/`
- `skills/project-review/scripts/mechanical-checks.test.mjs`

**Moved to `<repo>/.claude/skills/release/`:** the whole `skills/release/` tree.

**Deleted:** `.claude/plugins/cla/run_tests.py`; the three `SOURCE-REPO-ONLY.md`
(`consistency-checks/`, `launcher-checks/`, `skills/release/`);
`consistency-checks/tests/test_source_only_markers.py`.

**Stays in the plugin:** `lib/log_run.py`, every skill except `release`, `agents/`, `hooks/*.py` and
`hooks/hooks.json`, `output-styles/`, `.claude-plugin/plugin.json`, the plugin `README.md`, and the
two guards change (a) promoted (`skills/sync-context/scripts/check_fact_paths.py`,
`skills/_shared/scripts/check_no_project_tokens.py`).

**The load-bearing risk, and what catches it.** Every moved test resolves its subject by a
`Path(__file__).resolve().parents[N]` walk, and every `pythonpath` entry is relative to the scope
root. A tree move invalidates all of them, and the dangerous ones do not fail loudly — a wrong `N`
commonly lands on a plausible directory, so a test keeps passing while scanning nothing. The change
therefore requires: (1) `pytest --collect-only -q` captured before the move and asserted identical
after; (2) an explicit audit that every `parents[N]` walk and every `pythonpath` entry was
re-pointed and resolves to what it names; (3) `git mv` for every move, so each shows as a rename
rather than delete+add.

**Interaction with change (a):** (a)'s tasks 3.7 and 6.1 edit and run `run_tests.py`. This change
deletes that file, so it must land strictly after (a). If (a)'s task 3.10 recorded a finding about
`check_script_drift.py` passing vacuously, that file moves here and the finding travels with it.

**Out of scope**, owned by change (c) `guard-shipped-asset-boundary`: the release-time shipped-tree
scan itself, and the reconciliation of `CLAUDE.md`, the plugin `README.md`, `DEVELOPER-GUIDE.md`,
root `.gitattributes`, and `TODO.md`. This change fixes only doc lines it makes false **and** that
would otherwise leave it incoherent — chiefly the test-invocation commands people follow.
