## Context

The `cla` plugin is published by a `git-subdir` marketplace entry whose `path` points at
`.claude/plugins/cla/`. That descriptor supports `url`, `path`, `ref`, `sha` and nothing else — no
exclusion field — so the entire subtree ships. Measured today: **171 tracked files** under that path
(`git ls-files .claude/plugins/cla | wc -l`), of which **71 (41.5%)** are validation machinery, plus
one skill (`release`) a consumer cannot run.

Change (a), `decouple-skills-from-dev-assets`, removed every dependency a shipped procedure had on
that machinery. Nothing shipped now reads anything dev-only. This change performs the move that (a)
made safe, keeps the tree lean afterwards with a release-time scan, and reconciles the documentation
that describes the old layout.

**Why those are one change and not three.** The original plan split relocation (b) from
guard-and-docs (c), on the reasoning that a rewrite and a move should not land in the same diff.
That reasoning is sound for *file contents* and is preserved below (D8: moves and edits are separate
commits). It fails at the level of the change, because
`consistency-checks/tests/test_doc_facts.py` is a drift guard whose subject is exactly the
documentation the split deferred. It pins four things the relocation falsifies simultaneously:

| What it pins | How the move breaks it | Measured |
|---|---|---|
| Every concrete `.claude/plugins/cla/...` path named in 4 docs still resolves | `run_tests.py`, `hooks/tests`, `mutate.py` and the Node test path stop resolving | 16 such paths named; **10 mentions** stop resolving |
| Stated pytest-scope count == real scope count, at 4 literal anchors | scopes leave `_PLUGIN_ROOT`; the real count goes to 0 | 4 anchors, not 3 |
| Stated skills-shipping-tests count == real count, at 3 anchors | no skill ships tests once `tests/` moves: 6 → 0 | 3 anchors |
| Root `README.md`'s "N workflow skills" == real skill count | `release` leaves the plugin: 21 → 20 | `ls -d .claude/plugins/cla/skills/*/SKILL.md \| wc -l` → **21** |

Commands: the path enumeration re-implements `test_no_doc_names_a_plugin_path_that_no_longer_exists`'s
own regex and `_DOCS` map over the four documents (scratch script, output recorded in this change's
PR body); the anchor counts are read from the `@pytest.mark.parametrize` lists at
`test_doc_facts.py:160-167` and `:188-194`; the skill count from the `ls` above.

So a relocation-only change leaves **its own gate** — the bare `pytest` it establishes — red on the
day it lands, and it cannot be reviewed against a green run, merged behind one, or reverted to one.
Splitting is not viable, so the two are one change.

**The constraint that still shapes the relocation half:** content rewrites belong to (a) and are
finished. The only edits this change makes to a *moved* file's contents are the ones the move itself
falsifies — a path that no longer resolves, a scan root that no longer exists, a floor over a set
that moved. Improving a test is still out of scope.

## Goals / Non-Goals

**Goals:**

- `.claude/plugins/cla/` contains only assets a consuming repo can use.
- All dev-only assets live in one place, `<repo>/plugin-tests/`, as **one** pytest scope.
- The verification gate becomes bare `pytest`; `run_tests.py` is deleted.
- `release` becomes a repo-local skill, and its now-dangling `run_tests.py` precondition is fixed.
- Every move is a `git mv`, so review reads renames rather than 71 delete+add pairs.
- The collected-test count is provably unchanged except for named, intended deletions.
- **The change lands green on its own gate**, with every guard the move collapses repaired rather
  than relaxed.
- A future edit that puts a test, a pytest config, a mutation corpus, or any other undeclared shape
  back into the plugin cannot reach a published tag without someone deliberately widening the
  allowlist and saying why.
- Every repo document describes the tree that exists afterwards, and every count in those documents
  was produced by a command run in this change's own commit.

**Non-Goals:**

- **Cutting the `0.11.0` release.** This change adds the precondition and does not exercise it.
- Improving, merging, splitting, or deleting any test for any reason other than the move. A test
  that is vacuous today stays vacuous today.
- Rewriting any test's import strategy. `pythonpath` re-pointing is the mechanism; converting tests
  to `importlib`-by-path is a rewrite and out of scope.
- Fixing the `consistency-checks` split, the 12 grandfathered mutant batches, or any other item
  `TODO.md` carries. This change **re-describes** those entries against the new layout; it does not
  discharge them.
- Re-litigating Q5's release-time-only enforcement. The week-one gap is the shape of the chosen
  option, and this design states it rather than quietly closing it with a second guard in the suite.

## Pinned implementation parameters

Every number below was measured, with the command named. Nothing here is "set during
implementation."

**Dev-tree root:** `<repo>/plugin-tests/`. Verified free: the repo root holds `.claude`,
`.claude-plugin`, `.gitattributes`, `.gitignore`, `cla`, `cla.cmd`, `cla.io`, `CLAUDE.md`,
`DEVELOPER-GUIDE.md`, `openspec`, `README.md`, `TODO.md` (`git ls-files | cut -d/ -f1 | sort -u`).
Root `.gitignore` is unanchored (`__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `.DS_Store`), so the
new tree's caches are ignored with no `.gitignore` edit.

**Repo-local skill root:** `<repo>/.claude/skills/release/`. `.claude/skills/` already exists and
holds six OpenSpec skills; `release/` is free.

**Dev-tree layout** (mutant batches deliberately outside `tests/`, so `testpaths` alone excludes
them from collection, exactly as the 12 old scopes did — and **mirroring the `tests/` subdirectory
names**, so the batch↔guard pairing stays a one-step mapping):

```
plugin-tests/
  pyproject.toml                    the single scope config
  mutate.py                         moved from the plugin root
  mutants/
    conformance/  test_skill_lint.py
    consistency/  test_doc_facts.py
    release/      test_check_shipped_tree.py      (new, this change)
  scripts/check_script_drift.py     moved from consistency-checks/scripts/
  node/mechanical-checks.test.mjs   run by its own `node --test`, not by pytest
  tests/
    conformance/    3 files   consistency/  12   launcher/  2
    hooks/         13 files   lib/           1
    skills/_shared/ 2   annotate/ 6   codify-retro/ 1   new-worktree/ 1
    skills/release/ 2   spec-to-pr/ 3   spec-to-pr-retro/ 1
```

`consistency/` is 12 rather than 13 because `test_source_only_markers.py` is deleted (D4) and
`test_runner_stream_encoding.py` is deleted (D3), against `test_check_script_drift.py` staying;
`skills/release/` is 2 because this change adds `test_check_shipped_tree.py`.

**The single `pyproject.toml`** — `testpaths` and the full `pythonpath`, both pinned at **10**
entries:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = [
  "scripts",
  "../.claude/skills/release/scripts",
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

**Derivation, corrected.** **Ten** of the twelve old scopes declared a `pythonpath` — all but
`conformance-checks` and `skills/release`, both of which state in a comment why they declare none.
Command: `for f in $(git ls-files '.claude/plugins/cla/**pyproject.toml'); do echo "$f $(grep -c
'^pythonpath' $f)"; done`. An earlier draft of this design said "eight of the twelve", which was
never measured; the 9-entry list it produced was nevertheless right, because the mapping is
many-to-one:

| Old declaration | New entry |
|---|---|
| `consistency-checks` `["scripts"]` | `scripts` (the dev tree's own — `check_script_drift.py` moves with the tests that import it) |
| `hooks` `["."]`, `lib` `["."]` | `../.claude/plugins/cla/hooks`, `.../lib` (scope root == the modules' home) |
| six skills' `["scripts"]` | that skill's scripts dir **inside the plugin** — the scripts stay shipped; only the tests move |
| `launcher-checks` `["scripts"]` | **dropped**: `launcher-checks/` has no `scripts/` directory (`git ls-files .claude/plugins/cla/launcher-checks` → 4 files, none under `scripts/`). A dead entry is silent, so reproducing it is how a wrong path survives a move. |

The tenth entry, `../.claude/skills/release/scripts`, is new: it is how the seeded-input tests reach
`check_shipped_tree.py` (D12).

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

Plus **70** Node tests (`node --test .../mechanical-checks.test.mjs` → `ℹ tests 70`).

**A measurement expiry, stated plainly.** 1105 and 70 were measured on the tree **before change (a)
lands**. (a) re-points two conformance test modules and renames four files, which moves the
conformance and retro scope counts. So `collected_before` MUST be re-captured on the (a)-landed tree
immediately before the first `git mv`. The table above is the reference and the sanity range, not
the assertion. The arithmetic below is what is actually asserted.

### The expected post-move count, re-derived

An earlier draft asserted `collected_after == collected_before − 9`, where 9 was
`test_source_only_markers.py`'s collected count. **That number is wrong, and the shape of the error
matters more than the number**: it counted the one deletion the author had in mind and not the ones
the deletion of `run_tests.py` forces. The cheapest fix to a pinned-but-wrong number is to edit the
number, so what follows is the derivation, not just the result.

`run_tests.py` is deleted (D3). Three collected units read that file and cannot survive it. Each was
counted with `python -m pytest --collect-only -q <file>`:

| Deleted unit | Why it cannot be re-pointed | Collected |
|---|---|---|
| `consistency-checks/tests/test_source_only_markers.py` | Imports `run_tests.py` by path and calls `_is_source_repo()` (line 30-32); its whole subject is the marker mechanism this change deletes (D4). | **9** |
| `consistency-checks/tests/test_runner_stream_encoding.py` | Exists solely to assert `run_tests.py` pins its own stdout: it `ast.parse`s the runner (line 69) and runs `import run_tests` in a cp1252 child (line 48). Its subject is the deleted file. | **5** |
| `test_doc_facts.py::test_the_scope_discovery_rule_here_matches_what_run_tests_finds` | `(_PLUGIN_ROOT / "run_tests.py").read_text(...)` at line 108, asserting the runner still keys discovery on `[tool.pytest.ini_options]`. It also asserts `len(scopes) >= 8`, which one scope cannot satisfy. Both halves are about the deleted runner. | **1** |

> `collected_after == collected_before − 15 + N_added`

where **N_added** is the count of the tests this change adds for `check_shipped_tree.py`, stated as
its own number in the PR body rather than folded into the subtraction. Any other delta is a dropped
test and fails the change.

Two mentions that are **not** deletions, checked so the list is not cherry-picked:
`consistency-checks/tests/test_mutate.py` (line 203) and `test_check_script_drift.py` (line 12) name
`run_tests.py` only in a docstring; both move and both keep their subject.
`consistency-checks/tests/test_subprocess_encoding.py` names `"run_tests.py"` as a *scan anchor*
(line 164) — that is a repair, not a deletion, and it is D9's.

**File counts.**

| | Files |
|---|---|
| Tracked under `.claude/plugins/cla/` today | 171 |
| …after change (a) lands (+2 promoted guard scripts) | 173 |
| **Remaining under `.claude/plugins/cla/` after this change** | **101** |
| **Under `<repo>/.claude/skills/release/`** | **2** (`SKILL.md`, `scripts/check_shipped_tree.py`) |
| **Under `<repo>/plugin-tests/`** | **54** moved + 2 added (`tests/skills/release/test_check_shipped_tree.py`, `mutants/release/test_check_shipped_tree.py`) |
| **Deleted outright** | **18** |

The 101 is **independently confirmed**, not carried: reconstructing the post-move tree from today's
tree by removing the dev-only set and adding (a)'s two promoted scripts yields exactly 101 lines
(the `git ls-files … | grep -vE … | sed …` reconstruction in D11's verification block, `wc -l` →
101). The 18 deletions are `run_tests.py` (1), the three `SOURCE-REPO-ONLY.md` (3),
`test_source_only_markers.py` and its batch (2), `test_runner_stream_encoding.py` (1), and 11 of the
12 `pyproject.toml` (12 removed, 1 new).

**Scanner root list, pinned.** `check_no_project_tokens.py`'s `SOURCE_SCAN_ROOTS` goes from **8
entries to 5**: keep `skills`, `agents`, `hooks`, `output-styles`, `lib`; drop
`conformance-checks`, `consistency-checks`, `launcher-checks`.

### The allowlist — the full pattern set, tightened

Matched against `git ls-files .claude/plugins/cla`, paths taken **relative to the plugin root**.
**Fourteen** patterns plus one leaf-name exclusion, each with the reason it exists:

| # | Pattern | Why this shape ships |
|---|---|---|
| 1 | `README.md` | The plugin's own front door; its install commands legitimately name this repo. |
| 2 | `.gitattributes` | Carries the `eol=lf` pin for `hooks/*.sh` **inside** the published tree, where a `git-subdir` install can see it. |
| 3 | `.claude-plugin/plugin.json` | The manifest. Exactly one file; the marketplace reads it. |
| 4 | `agents/[^/]+\.md` | Mechanical helper agents other skills delegate to. |
| 5 | `output-styles/[^/]+\.md` | The writing convention, `force-for-plugin: true`. |
| 6 | `lib/[^/]+\.py` | The shared writer every retro-logging skill invokes as a program (`log_run.py`). |
| 7 | `hooks/[^/]+\.py` | The 12 leaf hooks, the two dispatchers, and `_dispatch_lib.py`. |
| 8 | `hooks/hooks\.json` | The wiring the harness reads at load. |
| 9 | `hooks/[^/]+\.sh` | `probe-python.sh`, sourced by every wiring line. |
| 10 | `hooks/git/pre-push` | **No extension at all** — a `#!/bin/sh` script every clone copies into `.git/hooks/`. |
| 11 | `skills/_shared/README\.md` | The one `README.md` under `skills/` that is not a skill's; `_shared/` is not a skill. |
| 12 | `skills/[^/]+/SKILL\.md` | The skill itself. |
| 13 | `skills/[^/]+/references/[^/.]+\.(md\|json)` | Supporting docs, plus the two permission-set JSON files. Single-dot stem only. |
| 14 | `skills/[^/]+/scripts/[^/.]+\.(py\|mjs)` | Deterministic helpers a skill calls. Single-dot stem only. |
| — | **Exclusion:** a leaf named exactly `conftest.py` is rejected wherever it appears | A pytest fixture module is never a shipped helper, and it is the one dev-asset shape whose name is otherwise a legal script name. |

**Verification, with the command.** Against the post-(b) tree, reconstructed from today's tree:

```bash
git ls-files .claude/plugins/cla \
  | grep -vE '(^|/)tests/|(^|/)mutants/|pyproject\.toml$|run_tests\.py$|mutate\.py$|/(conformance|consistency|launcher)-checks/|skills/release/|SOURCE-REPO-ONLY\.md$|mechanical-checks\.test\.mjs$' \
  | sed 's|^\.claude/plugins/cla/||' > ship.txt
printf 'skills/sync-context/scripts/check_fact_paths.py\nskills/_shared/scripts/check_no_project_tokens.py\n' >> ship.txt
wc -l < ship.txt        # 101
grep -vE '^(README\.md|\.gitattributes|\.claude-plugin/plugin\.json|agents/[^/]+\.md|output-styles/[^/]+\.md|lib/[^/]+\.py|hooks/[^/]+\.py|hooks/hooks\.json|hooks/[^/]+\.sh|hooks/git/pre-push|skills/_shared/README\.md|skills/[^/]+/SKILL\.md|skills/[^/]+/references/[^/.]+\.(md|json)|skills/[^/]+/scripts/[^/.]+\.(py|mjs))$' ship.txt
```

Result: **101 files in, 0 unmatched.** The tightened allowlist covers the post-move tree exactly.

### Three corrections to the candidate allowlist, found by running it

The candidate list under discussion was `SKILL.md`, `references/**.md`, `scripts/**.{py,mjs}`,
`agents/*.md`, `hooks/**`, `output-styles/*.md`, `README.md`, `.claude-plugin/plugin.json`,
`.gitattributes`. Run against the real tree it produces **four false positives on day one**:

| Missed file | Why the candidate list missed it |
|---|---|
| `lib/log_run.py` | `lib/` is a top-level dir; `scripts/**.py` does not reach it. |
| `skills/_shared/README.md` | Neither a `SKILL.md` nor under a `references/` ancestor. |
| `skills/_shared/references/required-permissions.json` | `references/**.md` excludes `.json`. |
| `skills/spec-to-pr/references/required-permissions-narrow.json` | Same. |

Patterns 6, 11 and the `{md,json}` alternation in 13 exist for exactly these. Recorded rather than
silently substituted, because the difference between the candidate list and the pinned one is four
files a first run would have rejected.

## Decisions

### D1 — One scope, and the collision measurement that makes it possible

The 12-scope split existed for exactly one reason: pytest's default import mode cannot hold two test
modules with the same basename. Measured across all 49 test files
(`git ls-files '.claude/plugins/cla/**/tests/*.py' | xargs -n1 basename | sort | uniq -d`), the
duplicates are exactly **`conftest.py`** and **`test_aggregate.py`** — nothing else. `conftest.py` is
special-cased by pytest and legal once per directory; `test_aggregate.py` is renamed by change (a).
So after (a), the collision set is empty and one scope is viable.

**The justification rested on one real collision, not two.** `run_tests.py`'s own docstring (lines
8-9) states that "multiple scopes ship a top-level `scripts/aggregate.py` **and**
`scripts/log_run.py`". The second half is false: `git ls-files | grep 'log_run\.py'` returns exactly
two paths, `lib/log_run.py` and `lib/tests/test_log_run.py` — one module, one scope, no collision.
The runner's stated reason for existing was therefore half-stale before this change touched it,
which is a reason to trust the *measurement* above rather than the runner's account of itself.
(Change (a)'s task 3.7 may report the same clause; it is recorded here because it is evidence for
the single-scope case, not a defect to fix in a file this change deletes.)

The second fact: the *scripts* those tests import stay in the plugin. A single scope therefore needs
a `pythonpath` that reaches out of its own tree into nine directories at once. That union is only
safe if no two of them export the same module name — the same collision question, one level down,
and it is not answered by the test-basename measurement above. It gets its own verification task
rather than an assumption.

*Alternative rejected:* keep the scopes and just move them, one `pyproject.toml` each. It preserves
12 rootdirs and 12 `pythonpath` blocks to re-point instead of one, keeps the `run_tests.py`
aggregator alive (which D3 deletes), and buys isolation against a collision set now measured empty.

### D1a — A structural allowlist, and the superset claim withdrawn

**Chosen: the 14-pattern structural allowlist above, plus the `conftest.py` exclusion.**

*Why an allowlist.* The denylist candidate was: fail if the tree contains any `tests/` dir,
`pyproject.toml`, `mutants/`, `*.test.mjs`, or `conftest.py`. Run against today's tree (the state a
scan would have had to catch):

```bash
git ls-files .claude/plugins/cla | wc -l                                    # 171 tracked
git ls-files .claude/plugins/cla | grep -E '<dev-only union>' | wc -l       # 72 dev-only
git ls-files .claude/plugins/cla | grep -cE '(^|/)tests/|(^|/)mutants/|pyproject\.toml$|\.test\.mjs$|conftest\.py$'   # 65
```

**65 of 72 caught. Seven missed:** the three `SOURCE-REPO-ONLY.md`, `check_script_drift.py`,
`mutate.py`, `run_tests.py`, `skills/release/SKILL.md`. Those seven are `run_tests.py` and
`mutate.py` (Q2's entire subject), all three markers (Q4's), and `release` (Q5b's). **A denylist
would have reported clean on precisely the drift the decision doc was written to prevent.** The
structural reason behind the measurement: the set of things that *should* ship is small, stable and
enumerable — 14 shapes covering 101 files — while the set of things that should not is unbounded.

**The superset claim is withdrawn, because it was measured false.** An earlier draft rejected
running both checks on the grounds that "the allowlist is a strict superset of the denylist's
coverage on the measured tree". Run against six planted paths, the 11-pattern draft **accepted four
of them**:

| Planted path | 11-pattern draft | Denylist | Why the draft accepted it |
|---|---|---|---|
| `skills/project-review/scripts/mechanical-checks.test.mjs` | **accept** | catch | old pattern 11 `scripts/[^/]+\.(py\|mjs)` — `[^/]+` swallows the `.test` segment |
| `skills/foo/scripts/conftest.py` | **accept** | catch | same pattern; `conftest.py` is a legal script name |
| `hooks/tests/test_x.py` | **accept** | catch | old pattern 7 `hooks/.+` — any file, any depth |
| `hooks/pyproject.toml` | **accept** | catch | same |
| `skills/foo/mutants/test_x.py` | reject | catch | — |
| `skills/foo/tests/test_x.py` | reject | catch | — |

Command: the six paths in a file, `grep -vE '<11-pattern alternation>'` (prints what the allowlist
rejects) against `grep -E '<denylist alternation>'` (prints what the denylist catches).

**The fix is to make the allowlist true rather than to run both.** Old pattern 7 (`hooks/**`) is
replaced by four narrow patterns covering the 15 files `hooks/` actually holds
(`git ls-files .claude/plugins/cla/hooks | grep -v '/tests/\|pyproject'` → 12 `.py`, `hooks.json`,
`probe-python.sh`, `git/pre-push`); patterns 13 and 14 take `[^/.]+` stems, which rejects any
compound extension; and `conftest.py` is excluded by leaf name. Re-run against the same six planted
paths, the tightened list rejects all six, and against the reconstructed post-move tree it still
matches all 101 files with 0 unmatched. **Only now is the superset relation a measurement**, and
only now does running a second denylist add maintenance surface with no detection — which is why it
is rejected.

This also re-prices what the old design called "a stray file dropped under `hooks/`… the one thing
this scan will not catch". `hooks/` holds **13 of the moved test files plus a `pyproject.toml`**
today, making it the single most likely place for a dev asset to reappear. Waiving the one directory
with the highest prior is not a small hole, and the four narrow patterns cost four table rows.

### D2 — Mutant batches live outside `tests/`, and mirror its subdirectories

The old scopes kept `mutants/` as a sibling of `tests/`, and `testpaths = ["tests"]` is what stopped
pytest collecting a mutant batch as a test suite. The batches are `test_*.py` files by name, so if
they landed under `tests/` they would be **collected and run**, and `mutants/test_skill_lint.py`
would collide with `tests/conformance/test_skill_lint.py`. Keeping `mutants/` a sibling of `tests/`
in the dev tree preserves the exclusion by the same mechanism, with no `norecursedirs` needed.

The batches additionally mirror the `tests/` subdirectory names
(`mutants/conformance/`, `mutants/consistency/`, `mutants/release/`) because
`test_guards_have_mutant_batches.py` maps a guard to its batch positionally in both directions
(`path.parents[1] / "mutants" / path.name`, and `batch.parents[1] / "tests" / batch.name`). A flat
`mutants/` against a nested `tests/` breaks both mappings; a mirrored one keeps each a one-step
substitution. See D9.

### D3 — `run_tests.py` is deleted; `mutate.py` is moved

These are different dispositions and the change must not blur them. Q2 sends both runners out of the
plugin. Q4 then supersedes Q2 for `run_tests.py` alone: a single pytest scope has nothing to
aggregate, so the runner has no job left, and its three responsibilities all evaporate together —
multi-scope discovery (one scope now), near-miss detection (one `pyproject.toml` now), and
source-repo-only skipping (D4). `mutate.py` keeps its job; it just does it from `plugin-tests/`.

The deletion is what makes `test_runner_stream_encoding.py` subjectless. That file's entire content
is assertions about `run_tests.py` pinning its own stdout under cp1252 — it `ast.parse`s the runner
and spawns `import run_tests` in a child. There is nothing to re-point it at, so it goes with the
runner, taking **5** collected tests and one `_EXEMPT` grandfathering entry with it.

### D4 — The marker mechanism is deleted, not relocated

`SOURCE-REPO-ONLY.md` answered "which shipped assets do not really ship." Once nothing dev-only
ships, the question has no instances. All four parts go together — the three markers, the guard
(`test_source_only_markers.py`, 9 tests), that guard's mutant batch, and `run_tests.py`'s
`SOURCE_ONLY_MARKER` skip logic (deleted with the runner). Relocating the guard instead would leave
a test asserting a contract nothing implements: it calls `run_tests.py::_is_source_repo()` directly,
so it cannot even import after the deletion.

This and D3's deletion are the change's two intentional losses of test coverage, and they are why
the count gate is stated as an explicit subtraction rather than `== before`.

### D5 — `release` moves whole, and its tests go to the dev tree, not with it

`<repo>/.claude/skills/release/` receives `SKILL.md`, and then gains `scripts/check_shipped_tree.py`
(D12) — **two files**. Its `tests/test_release_preconditions.py` goes to
`plugin-tests/tests/skills/release/` like every other test — otherwise `.claude/skills/` would need
its own `pyproject.toml` and the repo would have two pytest scopes again, which is the thing D3
removed. Its `pyproject.toml` and `SOURCE-REPO-ONLY.md` are deleted.

**The reference audit, complete.** `SKILL.md` names a moved or deleted asset on **eight** lines
(`grep -n '${CLAUDE_PLUGIN_ROOT}\|run_tests\|/cla:release\|consistency-checks' SKILL.md`):

| Line | What it names | Becomes |
|---|---|---|
| 3 | `description:` "Triggers on /cla:release" | `/release` |
| 8 | `# /cla:release` heading | `# /release` |
| 42 | `python3 ${CLAUDE_PLUGIN_ROOT}/run_tests.py` | bare `pytest` from the repo root |
| 50 | precondition row "`run_tests.py` fully green \| There is no CI." | same reason verbatim, new command |
| 59 | `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json` | repo-relative |
| **76** | `consistency-checks/tests/test_marketplace_manifest.py` | its dev-tree path |
| **78** | `consistency-checks/tests/test_doc_facts.py` | its dev-tree path |
| 80, 89, 90 | `${CLAUDE_PLUGIN_ROOT}/…` (3 more) | repo-relative; 89 is the second `run_tests.py` |

Lines 76 and 78 were absent from the earlier draft's audit, which enumerated only the five
`${CLAUDE_PLUGIN_ROOT}` references and line 50. They are load-bearing rather than incidental: they
are how the skill tells a release operator **which check catches a half-done version bump**, and
both files leave the plugin tree in this change.

`${CLAUDE_PLUGIN_ROOT}` is defined only for a file loaded as part of a plugin, so every one of those
five resolves to nothing after the move — this is not cosmetic re-pointing.

**`test_release_preconditions.py` straddles the split, and all four of its tests fail on the move.**
It derives `_PLUGIN_ROOT = Path(__file__).resolve().parents[3]` (line 31), `_REPO_ROOT =
_PLUGIN_ROOT.parents[2]` (32), `_PLUGIN_JSON = _PLUGIN_ROOT/".claude-plugin"/"plugin.json"` (34) and
`_SKILL_MD = _PLUGIN_ROOT/"skills"/"release"/"SKILL.md"` (36). After the move the test sits in
`plugin-tests/`, its `SKILL.md` subject sits in `.claude/skills/release/`, and `plugin.json` stays in
the plugin — **three different roots from one `parents[N]`**. A corrected depth cannot express that;
the file needs the repo root resolved once and the three subjects derived from it. This is a design
consequence of the split, not a routine re-point, which is why it is named here.

### D6 — Position-dependent resolution is the real risk, and it fails quietly

**31** occurrences of `Path(__file__).resolve().parents[N]` exist in the plugin
(`grep -rn "Path(__file__).resolve().parents\[" .claude/plugins/cla --include=*.py`), and **every one
is in a file this change moves**. Today: 21 use `parents[2]` to reach the plugin root from a
`<scope>/{tests,mutants,scripts}/` file, 7 use `parents[1]` to reach a scope root,
`skills/release/tests/` uses `parents[3]`, `launcher-checks/tests/test_cla_launcher.py` uses
`parents[5]` to reach the **repo root** (the only `parents[5]` in the tree), and one is a docstring
example inside `mutate.py`, not live code. Six further roots are derived on top
(`_REPO_ROOT = _PLUGIN_ROOT.parents[2]`), so a wrong plugin root silently produces a wrong repo root.

A wrong `N` does not raise. It lands on a real directory — a `rglob` over it yields fewer files, or
none, and the test reports clean. This is the same vacuity failure `CLAUDE.md` records for the
ledger-dir resolver ("the retro reports zero runs, which reads as a cold start"). Hence the audit is
a required task that names every walk, not a line in a checklist.

**One resolver fails differently, and one does not fail at all — the earlier draft got this pair
wrong.** `conformance-checks/tests/test_no_project_tokens.py` walks
`Path(__file__).resolve().parents` looking for a directory named `cla` whose parent is `plugins`
(lines 38-39), falling back to `parents[2]` (line 42). From `<repo>/plugin-tests/` there is **no such
ancestor at all**, and the fallback lands on the repo root — a real directory, so it fails silently.
That one needs the plugin root resolved explicitly.

`conformance-checks/tests/test_project_facts_paths.py` does **not** have that walk, contrary to the
earlier draft. It resolves the repo root via `git rev-parse --show-toplevel` first, and its fallback
walks for a `.claude` ancestor while explicitly refusing the user's global `~/.claude` (lines
138-146), returning `Path.cwd()` if nothing resolves. From the dev tree the git call still returns
the repo root, so the file **survives the move unchanged** in a git checkout; only its non-git
fallback degrades, and it degrades to `cwd`, not to a wrong repo. Re-pointing it as though it shared
its sibling's walk would have been an edit with no defect behind it.

### D7 — Dangling references the move creates are in scope

The boundary: fix a reference **this change breaks**. Five classes qualify.

1. **`SOURCE_SCAN_ROOTS`** in the promoted `check_no_project_tokens.py` names all three `*-checks`
   dirs. The iteration is `if not root.is_dir(): continue` — a vanished root is skipped **silently**.
   Left alone, the shipped guard would quietly scan 5 roots while claiming 8, and still exit 0. This
   is precisely the "scan that inspected nothing" failure its own spec text warns about, so it is
   pruned here.
2. **The `release` skill's eight lines** — D5.
3. **The test-invocation commands** in `CLAUDE.md`, both `README.md`s and `DEVELOPER-GUIDE.md` — the
   literal commands a person or agent copies. After this change every one of them names a path that
   does not exist.
4. **Two shipped `_shared/` files that mandate the deleted runner.** Both are in the published tree
   and both would ship a command that no longer exists to every consuming repo:
   - `skills/_shared/README.md` (~line 40): "`run_tests.py` fails the whole run as a 'near-miss' if
     a directory has a pytest-configured `pyproject.toml` without a `tests/`, or the reverse, so the
     three move together or not at all." The rule it describes is deleted with the runner (D3), and
     the "three files move together" instruction it justifies is falsified by this very change.
   - `skills/_shared/references/skill-authoring.md` (~line 56): "✅ ``run_tests.py`` exits 0 with no
     near-miss warning." — offered as the model of a step whose done-condition is one command and
     one bit. The teaching point survives; the example must become the bare-`pytest` gate.
   Neither is reached by either conformance scanner (the project-token scanner covers `.py`/`.md`
   under the synced roots but flags only *tokens*; nothing checks that a shipped file names a
   command that exists), so nothing but this task will catch them.
5. **The live overlay** `cla.io/overlays/codify-learnings.md` — a stale command there is executed,
   not just read.

### D8 — `git mv`, and why it is a requirement rather than a preference

71 files move. Git infers renames from content similarity at diff time, and a plain delete+add of a
file that also had one line edited can fall below the similarity threshold and render as an unrelated
deletion plus an unrelated addition. At this volume that turns a reviewable change into an unreadable
one, and a genuinely dropped file becomes indistinguishable from a moved one. `git mv` records the
intent, and `git log --follow` still reaches the history afterwards. Moves and content edits are
therefore **separate commits**: move first, re-point second. This is the one part of the (b)/(c)
split that survives the merge, and it survives at the commit level where it actually buys something.

### D9 — Every numeric floor over a moved set is re-derived, never lowered to go green

This is the decision the merge exists to make, and it is where a change of this shape historically
goes wrong. Nine assertions in the moved tests are floors of the form `assert len(x) >= N` over a
set the move re-homes (`grep -rnE "assert (len\(|total)[^,]*>=\s*[0-9]+"` across the five moving test
directories). A floor whose subject moved has exactly two honest outcomes: it is re-pointed and the
floor still holds, or the real count genuinely changed for a structural reason and the floor moves
**with that reason recorded**. Lowering one to make a red run green is the third outcome, and it is
worse than never having written the floor, because the assertion then certifies the thing it stopped
checking.

| Guard | Floor | Today | After, if re-pointed | Disposition |
|---|---|---|---|---|
| `test_guards_have_mutant_batches.py::test_the_scan_is_not_vacuous` | `len(files) >= 6` | 17 guard files | 13–15 | **floor unchanged**; re-point `_CHECK_SCOPES` |
| `test_guards_are_not_vacuous.py::test_the_scan_is_not_vacuous` | `len(files) >= 6` and `total_asserts >= 5` | 17 | 13–15 | **both unchanged**; re-point `_GUARD_TEST_DIRS` |
| `test_subprocess_encoding.py` | `len(names) >= 55` | 80 `.py` tracked under the plugin | 27 if left pointed at the plugin | **scan BOTH trees**; re-derive |
| `test_no_hardcoded_plugin_paths.py` | `len(files) >= 95` | 126 in-scope files | **96** | **floor unchanged, clears by 1** |
| `test_skill_lint.py` | `len(files) >= 17` SKILL.md | 21 | 20 | floor unchanged |
| `test_overlays_are_reachable.py` | `len(found) >= 8` | overlays live in `cla.io/` | unchanged | root resolution only |
| `test_doc_facts.py::…run_tests_finds` | `len(scopes) >= 8` | 12 | — | **deleted with the runner** (D3) |
| `test_hooks_wiring.py` | `len(refs) >= 3` | — | unchanged | root resolution only |

Counts from `ls .../tests/test_*.py | wc -l` (guard files: 5 in `conformance-checks/tests`, 12 in
`consistency-checks/tests`), `git ls-files … | grep -c '\.py$'` (80), the post-move reconstruction
(27, 96), and `ls -d skills/*/SKILL.md | wc -l` (21).

**These "today" figures are pre-(a) and expire when (a) lands.** The guard-file column is the one
where that matters: (a) promotes two conformance guards to skill scripts, so the post-(a)
`conformance-checks/tests` set is smaller than 5 (the dev-tree layout above pins it at 3), which puts
the post-move guard count at **13–15** rather than a single number. The floor of 6 holds across that
whole range, which is why the range is acceptable here and a re-capture is still required before the
floor is touched. The same expiry applies to the 80 and the 126: (a) adds two promoted scripts and
re-points two test modules. Every one of these is re-captured on the (a)-landed tree, per task 7.1.

Three of these need more than a re-point:

- **`test_guards_have_mutant_batches.py`** hardcodes `_CHECK_SCOPES = ("conformance-checks",
  "consistency-checks")` (line 26) as literal directory names and globs `_PLUGIN_ROOT / scope /
  "tests"` (line 71). After the move both globs return `[]` — `glob()` on a missing directory does
  not raise. Its `_EXEMPT` dict has **14** keys (12 of them `"grandfathered"`, counted by parsing the
  literal with `ast`), every one a `<scope>/tests/<file>.py` path that stops resolving. And
  `batch = path.parents[1] / "mutants" / path.name` assumes the per-scope sibling layout the move
  flattens (D2 restores it by mirroring). All four parts are this change's, and the `>= 6` floor is
  what makes the failure loud rather than silent. Deleting `test_runner_stream_encoding.py` (D3)
  removes one `_EXEMPT` key: **14 → 13 keys, 12 → 11 grandfathered**, which is a *shrink* and so is
  exactly what `test_the_grandfather_list_only_shrinks`'s `<= 12` cap permits — the cap does not
  move.
- **`test_guards_are_not_vacuous.py`** has the identical collapse: `_GUARD_TEST_DIRS =
  ("conformance-checks/tests", "consistency-checks/tests")` (line 42) globbed under `_PLUGIN_ROOT`
  (line 48). It is named by neither original change. **It is not, however, floorless** — an earlier
  reading claimed it would "go silently vacuous rather than red"; it carries *two* floors at lines
  132 and 139 (`>= 6` files, `>= 5` recognised assertions), so it fails as loudly as its sibling.
  That correction does not reduce the work; it removes the argument that this one could be deferred.
- **`test_subprocess_encoding.py`** is the case a floor alone would not have caught, because its
  named anchors go first. It asserts `len(names) >= 55` over every `.py` under `_PLUGIN_ROOT`, and
  then requires five specific paths to be in that set — including `"run_tests.py"` (deleted),
  `"hooks/tests/test_dispatch.py"` and `"skills/spec-to-pr/tests/conftest.py"` (both moved). Its
  subject is "every `.py` this repo owns that could spawn a subprocess", which after the split is
  **two trees**, not one. It must scan the plugin and the dev tree, drop the `run_tests.py` anchor
  with a reason, re-point the two moved anchors, and re-derive the floor from the union by running
  it — its own comment already states the rule: *"Lower it to the new real count, never to a number
  chosen to be safe from future deletions."*

### D10 — `test_doc_facts.py` is a gate, not a doc chore

The file is a drift guard over four documents (`_DOCS`, lines 38-43: `CLAUDE.md`, root `README.md`,
`DEVELOPER-GUIDE.md`, the plugin `README.md` — **`TODO.md` is not among them**, so `TODO.md`'s
staleness is real but is not what turns this file red). Its docstring advertises five pinned numbers;
the file carries **eight** test functions, and two of them pin existence facts the docstring never
mentions. Enumerated by reading it, because a list of failures is only as good as its completeness:

| Test | Params | Fate |
|---|---|---|
| `test_the_scope_discovery_rule_here_matches_what_run_tests_finds` | 1 | **Deleted** (D3): reads `run_tests.py`; asserts `>= 8` scopes |
| `test_the_release_version_agrees_across_the_manifest_and_the_prose` | 1 | Survives. `CLAUDE.md`'s `**Current release: `cla--v<version>`**` phrasing must be preserved verbatim through the rewrite, and the version must **not** be bumped |
| `test_no_doc_names_a_plugin_path_that_no_longer_exists` | 4 | Survives, and is the sharpest gate: 10 path mentions across the 4 docs stop resolving |
| `test_the_skill_count_in_the_readme_is_the_real_one` | 1 | Survives; real count 21 → **20** when `release` leaves, so root `README.md`'s "21 workflow skills" must become 20 |
| `test_every_stated_pytest_scope_count_is_the_real_one` | **4** | Survives only if `real_scope_dirs()` is re-pointed at the repo (it scans `_PLUGIN_ROOT` today, which would give 0) — then the real count is **1** and all four docs must say one scope |
| `test_every_stated_skills_with_tests_count_is_the_real_one` | 3 | The decision below |
| `test_every_stated_leaf_hook_count_is_the_real_one` | 3 | Survives untouched but for `_PLUGIN_ROOT`; `hooks/*.py` stays shipped |
| `test_every_named_leaf_hook_exists` | 1 | Same |

The 4-anchor parametrization at lines 160-167 is worth stating explicitly because an earlier reading
counted three: `("CLAUDE.md", "pytest scope —")`, `("README.md", "every pytest scope")`,
`("DEVELOPER-GUIDE.md", "all pytest scopes")`, `("plugin README.md", "isolated\npytest scope")`.
Missing the fourth means missing one document in the reconciliation.

**`test_every_stated_skills_with_tests_count_is_the_real_one` is re-pointed, not deleted.**
`real_skills_with_tests()` counts scope directories directly under `skills/` that carry a
`SKILL.md`; after the move that is 0, and the three anchors ("skill that ships tests", "skills with
tests", "that ships tests*") would fail with "no longer states". The tempting reading is that the
subject is gone — no skill ships tests any more — which would make deletion honest, as it is for the
marker guard in D4. It is not the same case: the *fact* is still true and still worth pinning, it has
only moved. Six skills have tests; they live at `plugin-tests/tests/skills/<name>/` instead of
`skills/<name>/tests/`, and a reader of these documents still needs to know which. So the helper is
re-derived over the dev tree, the documents keep the claim in re-pointed words, and the anchors keep
resolving. **If a reconciled document genuinely stops making the claim, dropping its anchor requires
the reason stated in the same commit** — the same rule this design applies to a floor.

**The order is fixed and it is the point.** Edit the doc, run the guard, read *which* failure it is.
A derived-count failure means the document is wrong — fix the document. An anchor failure ("no
longer states…") means the rewrite dropped a claim the repo deliberately pins — restore a phrase the
anchor can find, or move the anchor *and say why in the same commit*. What must not happen is
editing the guard first, which lands the document against an expectation already loosened to accept
it.

### D11 — The scan is a script, at `<repo>/.claude/skills/release/scripts/check_shipped_tree.py`

The bar this must clear is root `CLAUDE.md`'s: *"A script earns its place only by doing something a
direct command plus a sentence of prose cannot do reliably."* Seven scripts were deleted for failing
it, and the standing preference is prose over machinery. The "keep the plugin lean" concern does not
apply — this asset lives outside the published tree — so the decision rests on the merits.

**The prose-and-command alternative, stated fairly.** It is nearly sufficient: one `git ls-files |
sed | grep -vE '<the 14-pattern alternation>'` plus "if it prints anything, refuse; if it prints
nothing *and* the file count is non-zero, proceed", with the reason column as a markdown table in
`SKILL.md`.

**Chosen: the script**, on three grounds the command cannot cover:

1. **The exit contract is inverted and three-valued.** `grep -v` exits 0 when it prints violations
   and 1 when clean — backwards for a precondition read by exit status. And it has no third value:
   "I could not look" (zero files enumerated) is indistinguishable from "I looked and found
   nothing". That third value is the whole non-vacuity guarantee.
2. **A regex transcribed by hand is where a silent widening enters.** The alternation is ~250
   characters. A typo that *narrows* it produces a false positive, caught instantly. A typo that
   *widens* it — a stray `.*`, a dropped anchor — produces a clean report over an unscanned shape,
   invisible for a release cycle. D1a is that failure caught on paper before it shipped; a hand-typed
   regex would reintroduce it every release.
3. **A script is the only form this repo can test.** The release skill's tests live at
   `plugin-tests/tests/skills/release/` and the gate is `pytest`. A regex in a markdown code block
   has no test and cannot acquire one. A script gets seeded-input tests and a mutant batch, which is
   what `CLAUDE.md` requires of a new script anyway.

**Home:** beside the only skill that invokes it, so deleting the skill deletes its check.
*Alternative considered — `plugin-tests/scripts/`, beside `check_script_drift.py`:* that precedent is
real and would need no `pyproject.toml` edit. Rejected because the scan has one caller and belongs
with it; the cost is the 10th `pythonpath` entry, pinned once above rather than amended later.

**Size discipline.** The script is an enumeration, a pattern list, and a match loop. If it exceeds
roughly 120 lines excluding the pattern table and its reasons, it has grown a second job, and the
second job should be questioned rather than accommodated.

### D12 — The allowlist grows only with a stated reason

Modelled on `test_guards_have_mutant_batches.py`'s `_EXEMPT` block, which already runs this exact
discipline in this repo (lines 28-30: *"Keep this list short and justified — it is the pressure
valve that could quietly empty this test if it grew without argument"*) and enforces it with a
companion cap test asserting `grandfathered <= 12`.

The allowlist carries the same two parts: the reason column is **required per entry**, and a
companion test caps the pattern count at **14**, its size when the convention landed. The cap is not
a prohibition on growth — it is a prohibition on growth nobody argued for. A fifteenth pattern lands
by editing the cap in the same commit that adds the pattern and its reason.

**Enumeration source: `git ls-files`, not a filesystem walk.** `git-subdir` publishes from the
repository, so **tracked files are exactly the files that ship**. A walk would additionally flag
`__pycache__/` and `.pytest_cache/`, which the root `.gitignore` already excludes from tracking and
which therefore never ship.

**Non-vacuity and the exit contract:**

| Exit | Meaning | Output |
|---|---|---|
| `0` | Every enumerated file matched a pattern. | One line naming the counts, e.g. `check_shipped_tree: 101 files, 14 patterns, 0 violations`. |
| `1` | One or more files matched no pattern. | Every offending repo-relative path, one per line, all in one run. |
| `2` | Could not do its job: `git ls-files` failed, or it enumerated **zero** files. | A diagnostic to stderr. |

Exit `2` on an empty enumeration is the load-bearing row. A scan run from the wrong directory
enumerates nothing and would otherwise report "0 violations" — the identical shape `CLAUDE.md`
records for the ledger-dir resolver.

### D13 — The two false claims are deleted, and the `.gitattributes` rules are re-verified

Both need deleting rather than rewording, because a reworded false claim is still a claim about a
consuming repo that nobody has checked.

**Root `.gitattributes`.** The comment block's "TWO BELTS" list ends with a second belt asserting
that `hooks/tests/test_hooks_wiring.py::test_the_probe_has_no_carriage_returns` "ships with the
plugin, so it also fires in a consuming repo." After this change that file lives in `plugin-tests/`
and does not ship. It was also never true: nothing downstream ever invoked it — a consuming repo has
no pytest gate over the plugin cache.

The surrounding block is **load-bearing and stays**. It documents a measured, platform-divergent
CRLF hazard (Cygwin/Git Bash strip the CR, `dash` syntax-errors), and it records a *previous*
correction where an earlier version of the same comment asserted a failure mode that does not occur
"and got the mechanism backwards besides". Deleting more than the one false bullet would repeat that
error in the opposite direction. The first belt — `.claude/plugins/cla/.gitattributes` carrying the
same pin inside the published tree — is true, stays true, and stays.

**Every `eol=` rule is unchanged**, and every pinned path is re-checked to resolve, because one of
them (`.claude/plugins/cla/hooks/git/pre-push`) names a path inside the plugin. Expected to hold —
`hooks/` stays shipped in full — but "it did not move" is a fact to verify, not to assume.
Separately, the same block pins `consistency-checks/tests/test_pre_push_is_installed.py`, which
**moves**: that one is a path fix, not a deletion, and the two edits are adjacent and read similarly.
That adjacency is the trap.

**`CLAUDE.md`'s "portable core that reaches consuming repos".** After (a) and this change,
`conformance-checks` does not exist as a directory: two of its five guards are skill scripts in the
plugin, three are tests in `plugin-tests/`. The sentence has no true reading, so it goes rather than
being narrowed. What replaces it is the honest statement — the two promoted checkers reach consumers
because they are skill scripts inside the shipped tree, and the three plugin-data guards do not
reach consumers at all and are not meant to.

### D14 — Every count in a doc is produced by a command in this change's own commit

This change writes numbers into prose: how many pytest scopes, how many tests, how many files ship,
how many rows the script table has. `CLAUDE.md` records six such claims caught in one review session
— *"in one of them the comment's own text contained the token it declared absent"* — and a seventh
caught on the PR that added the rule.

So the rule is mechanical: **a number reaches a doc only as the recorded output of a command run in
the same commit**, and the whole block is re-run before the PR, because a number measured at the
start of a long prose change has expired by the end of it. This design has already had to apply that
rule to itself twice: the `− 9` collected-count gate (wrong, see the derivation above) and "eight of
the twelve old scopes declared a `pythonpath`" (ten, see the derivation table). Both were numbers
carried forward as "unchanged" rather than re-run.

### D15 — `TODO.md` entries are re-described, not discharged

Four `TODO.md` entries describe a tree that no longer exists. A re-layout does not pay a debt.

- **"Source-repo-only scopes — chosen: a per-scope marker file"** — the mechanism is deleted here.
  The entry's *decision* is moot and is replaced by one sentence recording that source-repo-only
  became structural, so the marker mechanism has no subject.
- **"Split `consistency-checks` so consumers keep its portable half"** — **moot, and worth saying
  why**: consumers never receive `consistency-checks` after this change, so there is no portable half
  to preserve for them. The entry goes, with the reason recorded.
- **"Write mutant batches for the 12 grandfathered guards"** — **live, unchanged in substance**, but
  every path in it moved, and the count drops to **11** because `test_runner_stream_encoding.py` is
  deleted (D3, D9). Re-point, record the new count and why it shrank, keep the `_EXEMPT` cap.
- **"Remaining unscanned surface after the scan-root widening"** — the file counts and the four-file
  list are falsified (`run_tests.py` and `mutate.py` were two of the four and no longer ship).
  Re-measure with the command; do not adjust the numbers by arithmetic. `hooks/probe-python.sh`
  remains outside both scanners and stays on the list.

### D16 — The inherited findings, resolved from source rather than deferred

**Does `check_script_drift.py` pass vacuously on a missing path?** (a)'s task 3.10 asks this and both
earlier drafts deferred it to each other. **Answered by reading `check_group` (lines ~134-146): it
does not.** A file in a group that is not `is_file()` appends
`f"{rel}: file not found (listed in {group['name']!r})"` to `problems` and continues — deliberately
collecting rather than returning, per its own comment. `main()` prints every problem and exits
non-zero. It fails loudly.

**But it must resolve TWO trees after this change, not get a corrected depth.** Its
`PLUGIN_ROOT = Path(__file__).resolve().parents[2]` (line 35) is the root for all three sibling
groups. Groups 1 and 2 name `lib/log_run.py` and the two retro aggregators — **all of which stay in
the plugin**. Group 3 names `hooks/tests/test_block_worktree_path_escape.py`,
`hooks/tests/test_block_unsafe_recursive_delete.py` and
`skills/new-worktree/tests/test_manual_worktree.py` — **all three of which move to `plugin-tests/`**,
while their subjects stay behind. One root cannot address both sets, so each group declares which
tree its paths are relative to. Because the checker fails loudly on a missing path, getting this
wrong is a red run rather than a silent pass — which is the good case, and is why it is a re-point
rather than a redesign.

**Does `test_guards_have_mutant_batches.py` hardcode a guard→batch pairing the deletion
invalidates?** **No, as asked** — `_EXEMPT` is a hardcoded literal but `test_source_only_markers.py`
is not in it (it has a batch), and the guard list is derived from the tree by `_guard_files()`. The
question was the wrong question: the file's real problem is the scope-literal collapse in D9, and
the `_EXEMPT` edit it does need is the removal of `test_runner_stream_encoding.py`, a file the
original question never mentioned.

## Risks / Trade-offs

- **A test is silently dropped in the move.** → The count gate,
  `collected_after == collected_before − 15 + N_added`, with `collected_before` captured on the
  (a)-landed tree immediately before the first `git mv`. A green suite is not the evidence; the
  arithmetic is.
- **A `parents[N]` walk re-points to a plausible-but-wrong directory and the test keeps passing over
  nothing.** → D6's audit enumerates all 31 plus the ancestor-walk resolver, and each must be shown
  to resolve to what it names — a non-zero count of files actually inspected, not merely exit 0.
- **A floor is lowered to make a red run green.** → D9. This is the most likely way this change
  ships broken while looking finished, because six floors go red at once and the cheapest fix to
  each is a smaller number. Every floor change carries its re-derivation command and its reason.
- **Two plugin `scripts/` dirs on one `pythonpath` export the same module name.** → Verified
  explicitly (D1). The test-basename measurement does not answer this and must not be mistaken for it.
- **The `../`-relative `pythonpath` behaves differently under some pytest invocation.** → Mitigated
  by the scratch probe, but rootdir is derived from where pytest is invoked; the gate is pinned as
  `pytest` **run from the repo root**, and the task states the exact command.
- **The shipped guard silently narrows its scan.** → D7.1 prunes `SOURCE_SCAN_ROOTS`, and the change
  requires the guard to report a non-zero scanned-file count across more than one root afterwards.
- **The allowlist is transcribed wrong and silently widens.** → The exact defect D11 chose a script
  to prevent, and choosing a script does not by itself prevent it. Mitigation: seeded-input tests
  planting a violating file of each excluded shape — including the four D1a caught the draft
  accepting — plus the empty-enumeration exit-2 test, plus a mutant batch.
- **A doc gets a number that was reasoned about.** → D14, and this design has already produced two
  such numbers itself.
- **A rewrite drops a rule while "reading better".** → `CLAUDE.md` check 2. Several sections are
  substantially rewritten rather than line-edited. Mitigation: the rewrite audit diffs old against
  new per section and states what was dropped, and the two *deliberate* deletions (D13) are named in
  advance so an accidental third is visible against them.
- **The `.gitattributes` edit takes the rules with the comment.** → The block's own history is the
  warning. Mitigation: assert the four `text eol=` lines are byte-identical and each pinned path
  resolves.
- **Losing 14 tests of coverage over two deleted subjects.** → Accepted, D3 and D4: both contracts
  are deleted. Not a coverage regression, two subjects that no longer exist.
- **A consumer who invoked `/cla:release` loses it.** → Accepted and noted as BREAKING.
- **Week-one drift ships.** → Accepted, and it is Q5's chosen tradeoff verbatim: "drift introduced in
  week one is not detected until the next release." Stated in the spec text so a reader meets the
  tradeoff rather than discovering it.
- **This is now one large change rather than two reviewable ones.** → Accepted, because the
  alternative is two changes of which the first cannot go green. Mitigated at the commit level (D8:
  moves, then re-points, then docs, as separate commits) rather than at the change level.
- **Platform divergence.** Several moved tests branch on Windows vs POSIX (`make_dir_alias` takes a
  junction path on Windows, a symlink elsewhere), and there is no CI. A green run here is evidence
  about this machine only.

## Migration Plan

1. Land change (a) first. Hard dependency: (a)'s tasks 3.7 and 6.1 edit and run `run_tests.py`,
   which this change deletes.
2. Capture `collected_before` and the whole measurement block on the (a)-landed tree.
3. Move in `git mv` commits.
4. Re-point resolvers and repair the collapsed floors in separate commits.
5. Delete what is subjectless; assert the count arithmetic.
6. Write the scan, its tests and its batch; wire it into the release skill.
7. Reconcile the documents, measuring every count as it is written; run `test_doc_facts.py` in D10's
   order.
8. Re-run the measurement block, then `pytest` from the repo root, once.

**Rollback:** renames plus 18 deletions plus prose, with no data migration, so `git revert` of the
commit range restores the tree exactly. Nothing outside the repo has consumed it — the plugin is
published only by tag, and no tag is cut here (`0.11.0` is the version the decision doc anticipates,
cut later from this reviewed and merged work using the precondition this change adds).

## Open Questions

None blocking. Both of the earlier drafts' open questions are answered in D16 from source. One item
is recorded for the implementer to settle with a command rather than a guess:

- **Does any pair of the nine plugin `scripts/` directories on the union `pythonpath` export the
  same module basename?** D1 states this is a separate question from the test-basename measurement
  and it has not been run. If a collision exists, the single scope is not viable as designed and the
  change needs re-shaping, not a workaround — so it is answered before the first `git mv`, not after.
