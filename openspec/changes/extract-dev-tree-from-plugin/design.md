## Context

The `cla` plugin is published by a `git-subdir` marketplace entry whose `path` points at
`.claude/plugins/cla/`. That descriptor supports `url`, `path`, `ref`, `sha` and nothing else — no
exclusion field — so the entire subtree ships. Measured today: **171 tracked files** under that path,
of which **71 (41.5%)** are validation machinery, plus one skill (`release`) a consumer cannot run.

Change (a), `decouple-skills-from-dev-assets`, removed every dependency a shipped procedure had on
that machinery: the two downstream-live conformance guards became skill scripts, the mutation gate
became prose, and the two colliding `aggregate.py` module pairs were renamed. Nothing shipped now
reads anything dev-only. This change performs the move that (a) made safe.

**The constraint that shapes the whole design:** this is a *pure relocation*. Content rewrites
belong to (a) and are finished. The only edits this change makes to file *contents* are the ones the
move itself falsifies — a path that no longer resolves, a scan root that no longer exists, a
precondition naming a deleted file. Anything else defers to change (c).

## Goals / Non-Goals

**Goals:**

- `.claude/plugins/cla/` contains only assets a consuming repo can use.
- All dev-only assets live in one place, `<repo>/plugin-tests/`, as **one** pytest scope.
- The verification gate becomes bare `pytest`; `run_tests.py` is deleted.
- `release` becomes a repo-local skill, and its now-dangling `run_tests.py` precondition is fixed
  here rather than left for (c).
- Every move is a `git mv`, so review reads renames rather than 71 delete+add pairs.
- The collected-test count is provably unchanged except for a single, named, intended deletion.

**Non-Goals:**

- The release-time shipped-tree scan (change (c)).
- Reconciling `CLAUDE.md`, the plugin `README.md`, `DEVELOPER-GUIDE.md`, root `.gitattributes`,
  `TODO.md` (change (c)) — beyond the test-invocation commands this change makes actively wrong.
- Improving, merging, splitting, or deleting any test. A test that is vacuous today stays vacuous
  today; relocation is not the change that fixes it.
- Rewriting any test's import strategy. `pythonpath` re-pointing is the mechanism; converting tests
  to `importlib`-by-path is a rewrite and out of scope.

## Pinned implementation parameters

Every number below was measured, with the command named. Nothing here is "set during
implementation."

**Dev-tree root:** `<repo>/plugin-tests/` — i.e. `C:\Code\logic-artisan\plugin-tests\`. Verified free:
the repo root holds `.claude`, `.claude-plugin`, `.gitattributes`, `.gitignore`, `cla`, `cla.cmd`,
`cla.io`, `CLAUDE.md`, `DEVELOPER-GUIDE.md`, `openspec`, `README.md`, `TODO.md` (`git ls-files | cut
-d/ -f1 | sort -u`). Root `.gitignore` is unanchored (`__pycache__/`, `*.py[cod]`, `.pytest_cache/`,
`.DS_Store`), so the new tree's caches are ignored with no `.gitignore` edit.

**Repo-local skill root:** `<repo>/.claude/skills/release/`. `.claude/skills/` already exists and
holds six OpenSpec skills; `release/` is free.

**Dev-tree layout** (mutant batches deliberately outside `tests/`, so `testpaths` alone excludes
them from collection, exactly as the 12 old scopes did):

```
plugin-tests/
  pyproject.toml                    the single scope config
  mutate.py                         moved from the plugin root
  mutants/                          2 batches (test_skill_lint.py, test_doc_facts.py)
  scripts/check_script_drift.py     moved from consistency-checks/scripts/
  node/mechanical-checks.test.mjs   run by its own `node --test`, not by pytest
  tests/
    conformance/    3 files   consistency/  13   launcher/  2
    hooks/         13 files   lib/           1
    skills/_shared/ 2   annotate/ 6   codify-retro/ 1   new-worktree/ 1
    skills/release/ 1   spec-to-pr/ 3   spec-to-pr-retro/ 1
```

**The single `pyproject.toml`** — `testpaths` and the full `pythonpath`, both pinned:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = [
  "scripts",
  "../.claude/plugins/cla/hooks",
  "../.claude/plugins/cla/lib",
  "../.claude/plugins/cla/skills/_shared/scripts",
  "../.claude/plugins/cla/skills/annotate/scripts",
  "../.claude/plugins/cla/skills/codify-retro/scripts",
  "../.claude/plugins/cla/skills/new-worktree/scripts",
  "../.claude/plugins/cla/skills/spec-to-pr/scripts",
  "../.claude/plugins/cla/skills/spec-to-pr-retro/scripts",
]
```

Nine entries. Eight of the twelve old scopes declared a `pythonpath`; the mapping is
`["scripts"]` → that skill's scripts dir **inside the plugin** (the scripts stay shipped; only the
tests move), and `["."]` → the scope root itself, which is `hooks/` and `lib/`. Two old entries are
deliberately **not** carried: `conformance-checks` and `skills/release` declared none, and
`launcher-checks` declared `pythonpath = ["scripts"]` while having **no `scripts/` directory** —
a dead entry, dropped rather than reproduced. `plugin-tests/scripts` is the new first entry, for
`check_script_drift.py`, which moves with the tests that import it.

`../`-relative `pythonpath` resolution is **verified, not assumed**: a scratch probe
(`plugin-tests`-shaped tree with `pythonpath = ["../src"]`, run via
`python -c "os.chdir(devtree); pytest.main(['-q'])"`) collected and passed a test importing the
out-of-tree module. pytest resolves `pythonpath` entries against rootdir, and rootdir is the
`pyproject.toml`'s directory.

**Pre-move collected-test count (the gate's baseline).** Command:
`python -m pytest --collect-only -q .claude/plugins/cla/<scope>/tests` per scope.

| Scope | Collected | | Scope | Collected |
|---|---|---|---|---|
| `conformance-checks` | 98 | | `skills/annotate` | 178 |
| `consistency-checks` | 116 | | `skills/codify-retro` | 24 |
| `hooks` | 497 | | `skills/new-worktree` | 51 |
| `launcher-checks` | 3 | | `skills/release` | 4 |
| `lib` | 20 | | `skills/spec-to-pr` | 54 |
| `skills/_shared` | 18 | | `skills/spec-to-pr-retro` | 42 |
| | | | **Total, 12 scopes** | **1105** |

Plus **70** Node tests (`node --test .../mechanical-checks.test.mjs` → `ℹ tests 70`). Combined
surface: **1175**.

**The expected post-move count, as arithmetic rather than a hope:**

> `collected_after == collected_before − 9`

where **9** is the collected count of the single deliberately-deleted file
(`python -m pytest --collect-only -q .claude/plugins/cla/consistency-checks/tests/test_source_only_markers.py`
→ `9 tests collected`). Any other delta is a dropped test, and fails the change.

**A measurement expiry, stated plainly.** 1105 and 1175 were measured on the tree **before change (a)
lands**. (a) re-points two conformance test modules and renames four files, which moves the
conformance and retro scope counts. So `collected_before` MUST be re-captured on the (a)-landed tree
immediately before the first `git mv` — the numbers above are the reference and the sanity range,
not the assertion. The `− 9` arithmetic is what is actually asserted.

**File counts.**

| | Files |
|---|---|
| Tracked under `.claude/plugins/cla/` today | 171 |
| …after change (a) lands (+2 promoted guard scripts) | 173 |
| Dev-only set (moves or is deleted) | 71 |
| `skills/release/` (4 files; 3 already inside the dev-only set) | +1 unique |
| **Remaining under `.claude/plugins/cla/` after this change** | **101** |
| **Under `<repo>/plugin-tests/` after this change** | **54** |
| **Under `<repo>/.claude/skills/release/` after this change** | **1** (`SKILL.md`) |
| **Deleted outright** | **17** |

`101 + 54 + 1 = 156`, and `173 − 156 = 17`. The 17 deletions are: `run_tests.py` (1), the three
`SOURCE-REPO-ONLY.md` (3), `consistency-checks/tests/test_source_only_markers.py` (1), its mutant
batch `consistency-checks/mutants/test_source_only_markers.py` (1), and 11 of the 12
`pyproject.toml` (12 removed, 1 new). Source: `git ls-files` over each pattern.

**Scanner root list, pinned.** `check_no_project_tokens.py`'s `SOURCE_SCAN_ROOTS` goes from **8
entries to 5**: keep `skills`, `agents`, `hooks`, `output-styles`, `lib`; drop
`conformance-checks`, `consistency-checks`, `launcher-checks`.

## Decisions

### D1 — One scope, and the two facts that make it possible

The 12-scope split existed for exactly one reason: pytest's default import mode cannot hold two test
modules with the same basename, and two scopes shipped colliding pairs. Measured across all 49 test
files (`git ls-files '.claude/plugins/cla/**/tests/*.py' | xargs -n1 basename | sort | uniq -d`), the
duplicates are exactly **`conftest.py`** and **`test_aggregate.py`** — nothing else. `conftest.py` is
special-cased by pytest and legal once per directory; `test_aggregate.py` is renamed by change (a).
So after (a), the collision set is empty and one scope is viable.

The second fact: the *scripts* those tests import stay in the plugin. A single scope therefore needs
a `pythonpath` that reaches out of its own tree into eight plugin directories at once. That union is
only safe if no two of those directories export the same module name — the same collision question,
one level down, and it is not answered by the test-basename measurement above. It gets its own
verification task rather than an assumption.

*Alternative rejected:* keep the scopes and just move them, one `pyproject.toml` each. It preserves
12 rootdirs and 12 `pythonpath` blocks to re-point instead of one, keeps the `run_tests.py`
aggregator alive (which Q4 deletes), and buys isolation against a collision set now measured empty.

### D2 — Mutant batches live outside `tests/`

The old scopes kept `mutants/` as a sibling of `tests/`, and `testpaths = ["tests"]` is what stopped
pytest collecting a mutant batch as a test suite. The batches are `test_*.py` files by name, so if
they landed under `tests/` they would be **collected and run**, and `mutants/test_skill_lint.py`
would collide with `tests/conformance/test_skill_lint.py`. Keeping `mutants/` a sibling of `tests/`
in the dev tree preserves the exclusion by the same mechanism, with no `norecursedirs` needed.

### D3 — `run_tests.py` is deleted; `mutate.py` is moved

These are different dispositions and the change must not blur them. Q2 sends both runners out of the
plugin. Q4 then supersedes Q2 for `run_tests.py` alone: a single pytest scope has nothing to
aggregate, so the runner has no job left, and its three responsibilities all evaporate together —
multi-scope discovery (one scope now), near-miss detection (one `pyproject.toml` now), and
source-repo-only skipping (D4). `mutate.py` keeps its job; it just does it from `plugin-tests/`.

### D4 — The marker mechanism is deleted, not relocated

`SOURCE-REPO-ONLY.md` answered "which shipped assets do not really ship." Once nothing dev-only
ships, the question has no instances. All four parts go together — the three markers, the guard
(`test_source_only_markers.py`, 9 tests), that guard's mutant batch, and `run_tests.py`'s
`SOURCE_ONLY_MARKER` skip logic (deleted with the runner). Relocating the guard instead would leave
a test asserting a contract nothing implements: it calls `run_tests.py::_is_source_repo()` directly,
so it cannot even import after the deletion.

This is the change's one intentional loss of test coverage, and it is why the count gate is stated as
`before − 9` rather than `== before`.

### D5 — `release` moves whole, and its tests go to the dev tree, not with it

`<repo>/.claude/skills/release/` receives `SKILL.md` only. Its `tests/test_release_preconditions.py`
goes to `plugin-tests/tests/skills/release/` like every other test — otherwise `.claude/skills/`
would need its own `pyproject.toml` and the repo would have two pytest scopes again, which is the
thing Q4 removed. Its `pyproject.toml` and `SOURCE-REPO-ONLY.md` are deleted.

Five `${CLAUDE_PLUGIN_ROOT}` references in `SKILL.md` (lines 42, 59, 80, 89, 90) become repo-relative
`.claude/plugins/cla/...` paths — that variable is defined only for a file loaded as part of a
plugin, so all five resolve to nothing after the move. Two of them (42, 89) name `run_tests.py`,
which this same change deletes: they become the bare `pytest` gate. A third mention, the precondition
table row at line 50 ("`run_tests.py` fully green | There is no CI"), is prose naming the same file
and changes with them.

That last point is the reason Q5b exists. The skill's own `SOURCE-REPO-ONLY.md` asserts it "remains
fully usable" downstream — false, and the file asserting it is deleted here.

### D6 — Position-dependent resolution is the real risk, and it fails quietly

**31** occurrences of `Path(__file__).resolve().parents[N]` exist in the plugin
(`grep -rn "Path(__file__).resolve().parents\[" .claude/plugins/cla --include=*.py`), and **every one
is in a file this change moves**. Today: 21 use `parents[2]` to reach the plugin root from a
`<scope>/{tests,mutants,scripts}/` file, 7 use `parents[1]` to reach a scope root, `skills/release/tests/`
uses `parents[3]`, `launcher-checks/tests/test_cla_launcher.py` uses `parents[5]` to reach the **repo
root** (the only `parents[5]` in the tree), and one is a docstring example inside `mutate.py`, not
live code. Six further roots are derived on top (`_REPO_ROOT = _PLUGIN_ROOT.parents[2]`), so a wrong
plugin root silently produces a wrong repo root.

A wrong `N` does not raise. It lands on a real directory — a `rglob` over it yields fewer files, or
none, and the test reports clean. This is the same vacuity failure `CLAUDE.md` records for the
ledger-dir resolver ("the retro reports zero runs, which reads as a cold start"). Hence the audit is
a required task that names every walk, not a line in a checklist.

Two resolvers fail *differently* and are easy to miss because they contain no `parents[N]` at all:
`test_no_project_tokens.py` and `test_project_facts_paths.py` each walk `Path(__file__).resolve().parents`
looking for a `cla` directory whose parent is `plugins`. That walk is deliberately position-independent
(their docstrings explain it must survive a marketplace cache) — and from `<repo>/plugin-tests/` it
finds **no such ancestor at all**. Change (a) leaves these files as thin test wrappers over the
promoted scripts, so what survives to be moved may be smaller, but whatever remains needs its root
resolution re-pointed at the plugin explicitly.

### D7 — Dangling references the move creates are in scope; everything else is not

The boundary: fix a reference **this change breaks** that would otherwise leave the change
incoherent. Three qualify.

1. **`SOURCE_SCAN_ROOTS`** in the promoted `check_no_project_tokens.py` names all three `*-checks`
   dirs. The iteration is `if not root.is_dir(): continue` — a vanished root is skipped **silently**.
   Left alone, the shipped guard would quietly scan 5 roots while claiming 8, and still exit 0. This
   is precisely the "scan that inspected nothing" failure its own spec text warns about, so it is
   pruned here. (Verified: `.claude/plugins/cla/conformance-checks/tests/test_no_project_tokens.py:236-263`.)
2. **The `release` skill's `run_tests.py` precondition** — D5. The brief names this explicitly.
3. **The test-invocation commands** in `CLAUDE.md` and the plugin `README.md` — the literal commands
   a person or agent copies to run the suite. After this change every one of them names a path that
   does not exist. Leaving them is not deferral, it is shipping instructions that fail on first use.
   Everything *else* in those files — the 12-scope enumeration, the architecture prose, the script
   table, `DEVELOPER-GUIDE.md`, `.gitattributes`, `TODO.md` — is stale but harmless and defers to (c).

### D8 — `git mv`, and why it is a requirement rather than a preference

71 files move. Git infers renames from content similarity at diff time, and a plain delete+add of a
file that also had one line edited can fall below the similarity threshold and render as an unrelated
deletion plus an unrelated addition. At this volume that turns a reviewable change into an unreadable
one, and a genuinely dropped file becomes indistinguishable from a moved one. `git mv` records the
intent, and `git log --follow` still reaches the history afterwards. Moves and content edits are
therefore also **separate commits**: move first, re-point second.

## Risks / Trade-offs

- **A test is silently dropped in the move.** → The count gate: `collected_after == collected_before − 9`,
  with `collected_before` captured on the (a)-landed tree immediately before the first `git mv`. A
  green suite is not the evidence; the arithmetic is.
- **A `parents[N]` walk re-points to a plausible-but-wrong directory and the test keeps passing over
  nothing.** → D6's audit enumerates all 31 plus the two ancestor-walks, and each must be shown to
  resolve to what it names — a non-zero count of files actually inspected, not merely exit 0.
- **Two plugin `scripts/` dirs on one `pythonpath` export the same module name.** → Verified
  explicitly (D1). The test-basename measurement does not answer this and must not be mistaken for it.
- **The `../`-relative `pythonpath` behaves differently under some pytest invocation.** → Mitigated by
  the scratch probe, but rootdir is derived from where pytest is invoked; the gate is pinned as
  `pytest` **run from the repo root** against `plugin-tests/`, and the task states the exact command.
- **The shipped guard silently narrows its scan.** → D7.1 prunes `SOURCE_SCAN_ROOTS`, and the change
  requires the guard to report a non-zero scanned-file count across more than one root afterwards.
- **Losing 9 tests of coverage over the marker contract.** → Accepted, D4: the contract itself is
  deleted. Not a coverage regression, a subject that no longer exists.
- **A consumer who invoked `/cla:release` loses it.** → Accepted and noted as BREAKING. It never did
  anything useful downstream; it edits a catalog and tags a plugin they do not own.
- **The window between (b) and (c) has a lean tree with no ship-check.** → The decision doc names this
  as the shape of Q5's chosen option rather than a defect. (c) closes it.
- **Platform divergence.** Several moved tests branch on Windows vs POSIX (`make_dir_alias` takes a
  junction path on Windows, a symlink elsewhere), and there is no CI. A green run here is evidence
  about this machine only — unchanged by this change, but the move touches every one of those files.

## Migration Plan

1. Land change (a) first. It is a hard dependency: (a)'s tasks 3.7 and 6.1 edit and run
   `run_tests.py`, which this change deletes.
2. Capture `collected_before` on the (a)-landed tree.
3. Move in `git mv` commits, then re-point in separate commits, then delete.
4. Assert the count, audit the walks, run the gate.

**Rollback:** the change is renames plus 17 deletions with no data migration, so `git revert` of the
commit range restores the tree exactly. Nothing outside the repo has consumed it — the plugin is
published only by tag, and no tag is cut here (`0.11.0` is the version the decision doc anticipates,
cut later by change (c)'s reworked `release`).

## Open Questions

- **Does `check_script_drift.py` pass vacuously on a missing path?** Change (a)'s task 3.10 asks this
  and records a finding if so. The file moves here, and its `PLUGIN_ROOT` is one of the 21
  `parents[2]` walks, so if (a) reported vacuity, this change inherits both the file and the finding.
  Resolving it is (c)'s, unless the move itself is what makes it vacuous — in which case it is this
  change's, because this change caused it.
- **Does `test_guards_have_mutant_batches.py` derive its guard list or hardcode it?** Deleting
  `test_source_only_markers.py` and its batch removes one pair; if the list at line ~147 is a literal,
  it needs the same edit. Determined in the implementation, not guessed here.
