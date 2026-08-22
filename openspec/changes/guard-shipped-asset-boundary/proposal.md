## Why

Changes (a) `decouple-skills-from-dev-assets` and (b) `extract-dev-tree-from-plugin` leave the
plugin lean but **unguarded and misdescribed**. Nothing checks that a future edit does not drop a
`tests/` directory back into `.claude/plugins/cla/`, and the repo's own documentation still
describes the tree that existed before them — 12 pytest scopes, a `run_tests.py` gate, a
`conformance-checks/` scope, a `/cla:release` skill. Two of those descriptions are not merely stale
but **false claims about what reaches a consuming repo**, which is the specific error class the
whole three-change program exists to end.

This is change (c) of three from `cla.io/decisions/ship-only-consumer-usable-assets-2026-08-22.md`,
and it runs last. Q5 chose *"a tree scan as a `release` precondition, not a guard in the test
suite"*, with the accepted tradeoff that *"drift introduced in week one is not detected until the
next release"*. Q5b then chose to *"move it to a repo-local skill at `<repo>/.claude/skills/release/`.
It takes the tree scan with it"* — because leaving the check inside a shipped-but-unusable skill
"would put the check against shipping unusable assets inside an unusable asset."

## What Changes

- **Add a shipped-tree scan as a `release` precondition**, in the relocated repo-local skill at
  `<repo>/.claude/skills/release/SKILL.md`, alongside the four preconditions already there (default
  branch, clean tree, green suite, reviewed-and-merged). It fires at the one deliberate gate the
  repo already has, and it refuses the release rather than warning.

- **The scan is a structural allowlist, not a denylist.** The plugin tree may contain only declared
  shapes; anything else fails and is named. Measured on the real tree, the denylist candidate
  (`tests/`, `pyproject.toml`, `mutants/`, `*.test.mjs`, `conftest.py`) catches 65 of the 72
  dev-only files and **misses 7** — including `run_tests.py`, `mutate.py`, all three
  `SOURCE-REPO-ONLY.md`, `check_script_drift.py`, and `skills/release/SKILL.md`. Those seven are
  precisely the assets Q2 and Q5b were written about, so a denylist would report clean on the exact
  drift the decision exists to prevent. design.md pins the allowlist and the commands that measured
  this.

- **Delete two false claims rather than reword them.** Both assert something untrue about what
  reaches a consuming repo:
  - The root `.gitattributes` comment claiming
    `hooks/tests/test_hooks_wiring.py::test_the_probe_has_no_carriage_returns` "ships with the
    plugin, so it also fires in a consuming repo." After (b) it definitively does not — and it did
    not before either, since nothing downstream ever invoked it. The surrounding comment block is
    load-bearing for a real CRLF hazard; only the false belt-and-braces bullet goes, and the
    `eol=lf` / `eol=crlf` **rules are unchanged**.
  - `CLAUDE.md`'s "`conformance-checks` is portable core that reaches consuming repos". After (a)
    and (b), three of its five guards live in the dev tree and the other two are skill scripts.

- **Reconcile the layout documentation** deferred by (a) and (b): `CLAUDE.md` (Commands, the
  12-scope description, the per-change gate table, the No-CI section, the script table, the skill
  layout tree, the fact/procedure-split section), the plugin `README.md`, `DEVELOPER-GUIDE.md`, and
  `TODO.md`. Change (b)'s task 8.2 hands this change an explicit list of lines it left deliberately
  stale; tasks.md enumerates them file by file rather than as one catch-all bullet.

- **Collect the findings (a) and (b) deferred here**: (a)'s task 3.10 finding on whether
  `check_script_drift.py` passes vacuously on a missing path, and (b)'s open question on whether
  `test_guards_have_mutant_batches.py` hardcodes a guard→batch pairing that the deletion of
  `test_source_only_markers.py` invalidates.

Not breaking. No shipped asset moves, no skill changes behaviour for a consumer. The only new
refusal is one a release operator sees in the canonical repo.

## Capabilities

### New Capabilities

None. The scan enforces a rule change (b) already added to the `cla-plugin` spec; it belongs in
that spec, not a new one.

### Modified Capabilities

- `cla-plugin`: one requirement added, one modified.
  - **ADDED — Release-time shipped-asset scan.** The plugin's publication workflow SHALL verify,
    before cutting a tag, that every file under the plugin directory matches a declared shape from
    a pinned allowlist; the scan SHALL name every offending file and SHALL refuse the release
    rather than warn; the allowlist SHALL grow only with a stated reason recorded beside the entry;
    and the scan SHALL fail rather than pass when it inspects nothing.
  - **MODIFIED — Shipped-asset boundary.** Change (b)'s text states the boundary as a structural
    obligation with no stated means of verification. It gains the enforcement clause naming the
    release-time scan as the point where the obligation is checked, plus the honest statement of
    the tradeoff Q5 accepted (drift is undetected between the edit and the next release). Every
    existing paragraph and all five of its scenarios are carried forward unchanged.

Deliberately **not** modified: *Conformance guard for the overlay separation* (change (b)'s
rewrite already reflects the post-move scan roots and the narrowed coverage gap), *Core/state
boundary* and *In-place activation and namespacing* (change (b) already gave both the dev-tree and
repo-local-skill carve-outs this change relies on). This change falsifies none of their text.

## Impact

**Edited — the scan:**
- `<repo>/.claude/skills/release/SKILL.md` — step 1's precondition command block and table gain the
  scan; the "Refuses rather than guesses" contract already in the skill's description covers it.

**Edited — documentation reconciliation** (the bulk of the work; every claim enumerated in
tasks.md):
- `CLAUDE.md` — Commands section, the 12-scope paragraph and its `pythonpath` enumeration, the
  per-change gate table, the No-CI section, the "Every script, and why it exists" table, the Skill
  layout tree, the fact/procedure-split section, and the four hand-watched-files list.
- `.claude/plugins/cla/README.md` — layout tree and any surviving dev-asset reference.
- `DEVELOPER-GUIDE.md` — change (b) recorded 9 hits, all deferred here.
- `TODO.md` — the source-repo-only entry, the `consistency-checks` split entry, the mutant-batch
  entry, and the unscanned-surface entry all describe a tree that no longer exists.
- `.gitattributes` (root) — one false bullet deleted; every `eol=` rule and every pinned path
  re-verified to resolve.

**Not edited:** `cla.io/decisions/`, `cla.io/lessons-learned/`, `cla.io/feedback/`,
`cla.io/checkpoints/`, `cla.io/retro/*.jsonl` — historical records of what was true when written.

**The discipline this change carries.** It is almost entirely prose asserting counts and structure,
which is exactly what root `CLAUDE.md` check 3 governs: for any measurement, *"name the command
that produced it, in the same commit."* The same file records six such claims caught in one review
session, one of which contained the very token it declared absent. Every count this change writes
into a doc — scope count, test count, file count, script-table rows — carries a task requiring the
command be run and its output recorded. No number reaches a doc because it was reasoned about.

**Dependency:** this change must land strictly after `extract-dev-tree-from-plugin`, which must
itself land after `decouple-skills-from-dev-assets`. It edits `.claude/skills/release/SKILL.md`,
which does not exist until (b) creates it, and it describes a tree (b) creates.

**Out of scope:** cutting the `0.11.0` release itself. The decision doc anticipates that version,
but a tag is cut deliberately from reviewed and merged work, and user memory records that a
published tag cannot be corrected. This change adds the precondition; it does not exercise it.
