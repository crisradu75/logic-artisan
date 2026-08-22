## Context

`.claude/plugins/cla/` is published verbatim as one `git-subdir` marketplace snapshot. The docs for
that source type list exactly `url`, `path`, `ref?`, `sha?` — **no exclusion field** — so the only
lever on what a consumer receives is what lives under `path`. `extract-dev-tree-from-plugin` — the
single successor, which merges what the decision doc sketched as changes (b) and (c) — uses that
lever by moving the dev tree out. This change is the prerequisite: it severs the three ties that
would otherwise break when the dev tree leaves.

Three ties, and they are not the same kind of problem:

1. **Two shipped skills mandate a dev-only runner.** `lite-pr/SKILL.md:132` and
   `spec-to-pr/references/revise.md:97` both instruct `python3 ${CLAUDE_PLUGIN_ROOT}/mutate.py`.
   After the successor that path does not exist in a consuming repo, so the mandate becomes an
   instruction to run a missing file.
2. **Two guards that read the *consuming* repo's data are trapped in a pytest scope.** Commit
   `a9ea9cf` ("Fix both conformance guards being silently inert in every consuming repo") records
   that these two were deliberately engineered to run from an installed copy against the consuming
   repo — and once fixed "immediately found a stale path there that had been invisible". A consumer
   has no pytest gate over the plugin cache, so today the only way to run them is by hand as
   `python3 -m pytest <path-inside-the-cache>`. They already behave as skill helpers; they are just
   filed as tests.
3. **Two duplicated basenames block the successor's single pytest scope.** `scripts/aggregate.py`
   and `tests/test_aggregate.py` each exist twice (codify-retro and spec-to-pr-retro). This is
   **not** a defect that bites today — see D0 — but it is what stops the successor collapsing
   twelve scopes into one.

The decomposition rule from the decision doc governs the shape of this change: **every content
rewrite lands before any relocation.** Git renders a rewritten-and-moved file as delete+add, so
bundling these rewrites with the successor's ~70 renames would make the highest-risk edits the least
reviewable ones in the diff.

## Goals / Non-Goals

**Goals:**

- Both downstream-live guards become programs a consumer can run: `python3 <script>`, exit 0 clean,
  non-zero with the offending paths named. No pytest needed downstream.
- Every assertion the two original pytest modules made against the real repo survives the rewrite,
  demonstrably — not by the author's recollection.
- The mutation gate survives as an obligation while its tool reference goes, with every named
  precedent in both blocks preserved verbatim.
- The two duplicated `aggregate.py` basenames are gone, and every consumer of the old names —
  including the three in `consistency-checks/` that the decision doc does not mention — is updated
  in the same commit.
- Every consumer of the two *promoted* modules is updated too, including
  `consistency-checks/tests/test_token_list_is_curated_here.py`, which imports the token guard by
  module name and reads three symbols off it (see D7).
- The tree is left in a state where `extract-dev-tree-from-plugin` is a pure `git mv` exercise.

**Non-Goals:**

- **No file moves and no deletions of the dev tree.** `conformance-checks/` still exists as a scope
  when this change lands; the three plugin-data guards stay in it; `run_tests.py` and `mutate.py`
  both still exist. All of that is `extract-dev-tree-from-plugin`.
- **No release-time shipped-tree scan**, no `release`-skill relocation — also the successor.
- **No broad doc reconciliation.** `CLAUDE.md`'s scope count, layout tree, `DEVELOPER-GUIDE.md`, the
  plugin `README.md`, root `.gitattributes` and `TODO.md` are the successor's. This change fixes
  only doc lines it *itself* makes factually false.
- **No behaviour change to what the guards check.** Same scan roots, same exclusions, same
  extraction heuristics, same failure text. Only the invocation shape changes.
- Not re-litigating whether `mutate.py` earns its keep — the decision doc settled that.

## Pinned implementation parameters

Every load-bearing value, fixed here rather than "set during implementation".

### Exit-code contract (identical for both promoted checkers)

| Exit | Meaning | Output |
|---|---|---|
| `0` | Clean — nothing to report. Also the **trivial-pass** cases below. | One summary line to stdout naming what was checked and the count (e.g. `check_fact_paths: 2 files scanned, 0 stale paths`). A trivial pass states its reason explicitly. |
| `1` | Violations found. | Every violation to stdout, **one per line**, in the original guards' format — repo-relative path, line number, and the offending token/path (plus the matched token and excerpt for the token checker). All violations in one run; never stop at the first. |
| `2` | The checker could not do its job — bad arguments, or an input that exists but cannot be read. | A diagnostic to stderr. Never conflated with `1`: "I found problems" and "I could not look" are different answers, and a consumer scripting the exit code must be able to tell them apart. |

**Trivial pass vs. failure, carried over verbatim from the existing spec requirements — do not
re-derive these:**

- `check_fact_paths.py`: `cla.io/project-facts.md` absent → **exit 0** with a stated reason (a fresh
  repo that has not run `/cla:sync-context` must not fail).
- `check_no_project_tokens.py`: token-list overlay absent → **exit 0** with a stated reason.
  Token-list overlay **present but yielding no tokens** → **exit 1**, with the message noting that
  deleting the file is the way to intentionally disable the guard. A populated list broken by a
  later formatting change is a defect, not a fresh repo.

### CLI surface

Both scripts: `python3 <script> [--repo-root <path>]`. No required arguments — the default is the
existing self-resolution (`git rev-parse --show-toplevel` from the process cwd, with the
non-global-`.claude` walk as fallback). `--repo-root` exists so the CLI layer itself is testable
against a `tmp_path` fixture; it is not part of the consumer-facing contract and the skills invoke
the bare form.

### Chosen names

| Old | New |
|---|---|
| `skills/codify-retro/scripts/aggregate.py` | `skills/codify-retro/scripts/codify_aggregate.py` |
| `skills/spec-to-pr-retro/scripts/aggregate.py` | `skills/spec-to-pr-retro/scripts/spec_to_pr_aggregate.py` |
| `skills/codify-retro/tests/test_aggregate.py` | `skills/codify-retro/tests/test_codify_aggregate.py` |
| `skills/spec-to-pr-retro/tests/test_aggregate.py` | `skills/spec-to-pr-retro/tests/test_spec_to_pr_aggregate.py` |
| `conformance-checks/tests/test_project_facts_paths.py` (module) | `skills/sync-context/scripts/check_fact_paths.py` |
| `conformance-checks/tests/test_no_project_tokens.py` (module) | `skills/_shared/scripts/check_no_project_tokens.py` |

Underscores, not hyphens: these are importable Python module names, and the retro tests reach them
both as subprocesses (`SCRIPT`) and by an explicit `spec_from_file_location` load.

### Where the old tests point after the promotion

The pytest files stay in `conformance-checks/tests/` for this change and import the promoted module
**by file path via `importlib.util.spec_from_file_location`**, not by adding a `pythonpath` entry to
`conformance-checks/pyproject.toml`. Two reasons: that scope deliberately has no `pythonpath` today
(its tests import nothing), and a path-based load survives the successor's relocation with a one-line
edit instead of a scope-config change.

## Decisions

### D0 — The `aggregate.py` rename is a forward dependency, not a present collision

An earlier draft of this change justified the rename as removing a collision — "one process cannot
import both". **That is false today, and the check that would have caught it is root `CLAUDE.md`'s
rule 3: search the source for counterexamples, not only for supporting cases.** The counterexamples:

- `codify-retro/tests/test_aggregate.py:262` and `spec-to-pr-retro/tests/test_aggregate.py:536` each
  load their sibling aggregator via `importlib.util.spec_from_file_location` under a **distinct**
  module name — `_ut_codify_aggregate` and `_ut_s2p_aggregate` respectively. Neither file contains
  `import aggregate`; the only other reference is `SCRIPT = … / "scripts" / "aggregate.py"`, run as a
  subprocess.
- `run_tests.py` runs every scope as its own `pytest` subprocess, so the two test files are never
  in one interpreter together regardless.

So the two modules do not collide, and nothing in the tree would break if they were left alone.

**The real reason to rename is the successor.** `extract-dev-tree-from-plugin` consolidates all
twelve scopes into a single `plugin-tests/` pytest scope. Its design records the measurement —
duplicate basenames across all 49 test files
(`git ls-files '.claude/plugins/cla/**/tests/*.py' | xargs -n1 basename | sort | uniq -d`) are
exactly `conftest.py` and `test_aggregate.py`, with `conftest.py` legal once per directory and
`test_aggregate.py` "renamed by change (a)". Two `test_aggregate.py` files in one rootdir break
pytest **collection**, not import. That is the dependency, and it is a dependency in the other
direction from the rest of this change: the successor cannot land without this rename, and this
rename buys this change nothing on its own.

The rename is therefore kept — but stated as what it is. The consequence for the spec delta is that
the distinct-name requirement is worded as a *forward* obligation, not as a fix for a live defect.

*Alternative considered:* drop the rename from this change and let the successor do it. Rejected —
the successor is a pure-relocation change by design, and folding a content rename into ~70 `git mv`s
reproduces the delete+add reviewability problem this decomposition exists to avoid.

### D1 — Keep every pure function byte-identical; convert only the repo-level `test_*` functions

The two modules are ~900 lines each, and almost all of it is extraction heuristics with hard-won
edge cases (possessive stripping, markdown-link seams, emphasis markers, `:line:col` suffixes,
tracked-vs-untracked top-level names). **Those functions are not rewritten.** They move across
unchanged, keeping their exact names and signatures, so the existing unit tests that call them
directly (`extract_path_candidates`, `scan`, `find_stale_paths`, `find_violations`,
`find_source_violations`, `find_absolute_path_leaks`, `find_unreadable_files`, `load_tokens`) keep
passing with only their import line changed.

What actually gets rewritten is small and enumerable: the `test_*` functions that assert against the
**real repo** become the body of `main()`.

*Alternative considered:* rewrite the checkers cleanly from the spec text. Rejected — the spec
describes the contract, not the accumulated heuristics, and every one of those heuristics exists
because a false positive or a missed leak was found in practice. A clean rewrite would silently drop
them.

### D2 — `check_no_project_tokens.py` carries **four** repo-level checks into `main()`, not one

This is the single most likely thing to go wrong. The module's real-repo assertions are:

1. `test_no_project_tokens_in_synced_core` — the prose scan over `SKILL.md` / `references/**/*.md`.
2. `test_no_project_tokens_in_synced_source` — the source scan over the eight `SOURCE_SCAN_ROOTS`
   (`.py` plus `agents/*.md` and `output-styles/*.md`, frontmatter-exempt).
3. `test_no_absolute_developer_paths_in_synced_source` — the hardcoded-developer-path scan, a
   *different* scanner with its own regexes (`MANGLED_WIN_PATH`, `WIN_ABS_PATH`, `HOME_ABS_PATH`)
   and its own `path-fixture-ok` exemption marker.
4. `test_every_scanned_file_is_actually_readable` — the non-vacuity guard: a file that cannot be
   read is silently "clean" to every scanner above, so unreadability is itself a failure.

`main()` runs **all four**, accumulates violations across them, and exits `1` if any produced
output — it does not short-circuit on the first failing check, because the whole point of the
original guards' "surface all violations in a single run" rule is that a fix-one-rerun loop wastes a
consumer's time. Check (4) is the one most at risk of being dropped as "not really a check"; it is
the reason the other three cannot pass vacuously.

`check_fact_paths.py` is simpler: one repo-level assertion
(`test_no_stale_paths_in_project_facts_or_overlays`) becomes `main()`. Its second real-repo-adjacent
test, `test_the_repo_root_is_the_process_repo_not_the_users_home`, is a monkeypatched unit test of
the resolver and stays a test.

### D3 — Fix `_plugin_root()`'s fallback depth, which the move silently invalidates

`check_no_project_tokens.py`'s `_plugin_root()` walks parents for a directory named `cla` whose
parent is `plugins`, then falls back to `Path(__file__).resolve().parents[2]` with the comment
`# Fallback for an unexpected layout: tests/ -> conformance-checks/ -> cla/`.

From the new home `skills/_shared/scripts/`, `parents[2]` is `skills/`, not the plugin root — the
correct depth is `parents[3]`. The primary walk still succeeds in every normal layout, so this
**fails silently and only in the unexpected-layout case the fallback exists to cover**. Update the
depth and the comment together; the comment is what makes the depth checkable.

`check_fact_paths.py`'s `_repo_root_from_here()` needs no such fix — it is already fully
position-independent (git first, then a `.claude` walk that explicitly refuses the user's global
`~/.claude`, then cwd), with no `parents[N]` guess anywhere. Verified by reading it, not assumed
from symmetry with its sibling.

### D4 — The mutation gate becomes prose, keeping the obligation and every precedent

Both 2b blocks are rewritten so that the *only* thing removed is the
`python3 ${CLAUDE_PLUGIN_ROOT}/mutate.py <batch.py>` invocation and the words that exist purely to
operate it. Everything else is preserved verbatim, in place:

- "required before the commit in step 3"
- "A fix for a Critical/Important finding is a change like any other and earns the same evidence the
  original code needed — 'the reviewer's finding is now handled' is not that evidence."
- break **what the fix touches**, not only what it targets
- the default-path/overlay-path precedent — "correcting one return path routinely breaks another,
  which is how a real fix here once traded a silent no-op on the default path for the identical
  no-op on the overlay path"
- "Fix a surviving mutant, or name it in the final report / Handoff report with a reason" (the two
  blocks differ here — `lite-pr` says *final report*, `revise.md` says *Handoff report*; keep each
  as it is)
- "A clean run is evidence about the mutants you thought of and nothing else — two commits in this
  repo each recorded 'three mutations checked, all caught' and each shipped a critical a later
  review found."

The replacement for the invocation is the manual procedure the tool automated: break what the fix
touches, run the affected test, confirm it fails, restore. The word "mutant" stays — it names the
concept, and both surviving-mutant sentences depend on it.

*Alternative considered:* delete step 2b entirely. Rejected — the decision doc says "downgraded to
prose", and the precedents in these blocks are the repo's most expensive lessons. Losing the
obligation is a bigger regression than losing the tool.

### D5 — Update the three `consistency-checks/` consumers the decision doc does not name

Grep found four places outside the retro skills that hardcode `aggregate.py`, none listed in the
decision's task sketch:

- `consistency-checks/scripts/check_script_drift.py` — two `paths` lists (lines 52–53, 60–61) and a
  check `name` string ("retro aggregate.py record loading")
- `consistency-checks/tests/test_ledger_names_agree.py` — two
  `_PLUGIN_ROOT / "skills" / … / "scripts" / "aggregate.py"` constructions
- `consistency-checks/tests/test_check_script_drift.py` — an expected-paths fixture
- `run_tests.py`'s module docstring, which justifies the multi-scope split by naming the collision

`check_script_drift.py` is the dangerous one. Its whole purpose is comparing the ledger-dir resolver
across the writer and both readers, and `CLAUDE.md` records why: *"A divergence is silent — the
retro reports zero runs, which reads as a cold start."* If its path list still names a file that no
longer exists, the drift check has nothing to compare and the silent-divergence detector is itself
silently disabled. **Whether it fails loudly or passes vacuously on a missing path is a fact to
establish by running it, not to assume** — a task covers exactly that.

### D6 — Docs: fix only what this change falsifies

Four doc edits, and a deliberate boundary:

- `skills/sync-context/SKILL.md:151` — names
  `${CLAUDE_PLUGIN_ROOT}/conformance-checks/tests/test_project_facts_paths.py` as the linting guard.
  Re-point at `${CLAUDE_PLUGIN_ROOT}/skills/sync-context/scripts/check_fact_paths.py`. This one is
  more than a path swap: the guard is now *this skill's own* script, so the sentence can say so.
- `skills/_shared/references/skill-authoring.md:39` — mandates
  `python3 -m pytest ${CLAUDE_PLUGIN_ROOT}/conformance-checks/tests/test_no_project_tokens.py -q`.
  Becomes `python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/check_no_project_tokens.py`, with
  "MUST pass" restated as "MUST exit 0". This is a shipped file telling a consumer to run a pytest
  scope that is about to vanish — exactly the coupling this change exists to cut.
- `skills/codify-retro/SKILL.md:29` and `skills/spec-to-pr-retro/SKILL.md:27` — the invocation lines.
- `CLAUDE.md:259` — the "Every script, and why it exists" row naming
  `codify-retro`, `spec-to-pr-retro` `scripts/aggregate.py`.

Everything else in `CLAUDE.md` — the scope count, the layout tree at line 234, line 96's
"several scopes ship same-named helper modules", line 93's "portable core that reaches consuming
repos" — is **left alone on purpose** and belongs to `extract-dev-tree-from-plugin`.
Line 96 is a borderline call worth naming: after this change no two scopes share a module basename,
so its stated justification is weakened. But the 12-scope split it justifies still exists until the
successor collapses it, so rewriting it here would describe a tree that does not yet exist. Left to
the successor.

Generic mentions in `_shared/references/retro-skeleton.md` ("the calling skill's `aggregate.py`")
and `run-log-schema.md` are **not** path references — they name a role, and each retro skill still
has exactly one aggregator. A task checks them rather than assuming; the expected outcome is that
the role-shaped ones stand and only path-shaped ones change.

### D7 — The promotion has a consumer the rename enumeration misses, and it is the token guard's own guard

D5 enumerates consumers of the renamed `aggregate.py` modules. A **separate** enumeration is owed by
the *promotion*, and it has exactly one entry outside the two `conformance-checks` test files
already covered by tasks 1.7 and 2.7:

`consistency-checks/tests/test_token_list_is_curated_here.py` hardcodes
`_GUARD = _PLUGIN_ROOT / "conformance-checks" / "tests" / "test_no_project_tokens.py"` (line 25),
puts `_GUARD.parent` on `sys.path`, and does `import test_no_project_tokens as guard` (line 40). It
then reads three symbols off the imported module:

| Symbol | Used as |
|---|---|
| `_repo_root()` | `resolved_root = guard._repo_root()` |
| `TOKEN_LIST_RELPATH` | `token_path = resolved_root / guard.TOKEN_LIST_RELPATH` |
| `load_tokens` | `tokens = guard.load_tokens(token_path)` |

All three must remain **module-level names on the promoted script** — not locals inside `main()`,
and not renamed. D1 already commits to carrying every non-test function across with its exact name
and signature, which covers `load_tokens` and `TOKEN_LIST_RELPATH`; `_repo_root` is named here
explicitly because it is a private helper and is exactly the kind of thing a rewrite folds into
`main()`.

Why this one matters more than its size suggests: its `_load_guard` docstring states the rule it
exists to enforce — *"Everything below comes from the guard — the relative path AND the root it
resolves against. Recomputing either here would check that the file exists where THIS test looks,
which is not the question… Measured: a version of this check that computed its own repo root passed
happily while the guard's anchor was off by one level and the guard skipped."* A promotion that
leaves it importing a module whose implementation has moved breaks the guard that guards the token
list — the exact silent failure the file was written against. And it sits in a scope
(`consistency-checks/`) that this change's task list otherwise touches only for the rename, so it is
easy to miss.

Note the interaction with D3: this file consumes `_repo_root()`, not `_plugin_root()`, so the
fallback-depth fix is orthogonal to it. Both need doing; neither substitutes for the other.

## Risks / Trade-offs

**[The rewrite drops an assertion nobody notices]** → This is the change's defining risk and the
exact shape root `CLAUDE.md`'s check 2 warns about ("Rewrote a file rather than edited it? Diff old
against new and state what you dropped"). `test_no_project_tokens.py` has four real-repo assertions
where a reader expects one; `test_every_scanned_file_is_actually_readable` in particular reads like
plumbing and is the one holding the other three honest. Mitigation is a required task that
enumerates every `def test_*` in both originals, classifies each as *carried into `main()`* /
*stayed a unit test* / *deliberately dropped, with reason*, and states the result — with the
enumeration produced by grepping the original files, not from memory of them. A rewrite with nothing
in the "dropped" column is a claim that needs the same evidence as any other.

**[A promoted checker passes vacuously in a consuming repo]** → The precise failure mode of upstream
issue #52, where both guards resolved the repo root to the user's home directory, found no
`cla.io/`, and skipped green in every marketplace install simultaneously. Promotion changes the
invocation, so the resolution path gets exercised from a new location. Mitigation: keep the
non-vacuity checks (`test_source_scan_of_the_real_plugin_is_non_vacuous`,
`test_the_scanner_is_not_vacuous`, `test_the_repo_root_is_the_process_repo_not_the_users_home`) as
tests against the promoted module, and have `main()` print what it scanned and how many files —
a zero-file scan reported as "0 stale paths" is the bug, and a printed count is what makes it
visible.

**[Exit `1` and exit `2` get conflated]** → An unreadable input returning "clean" is the vacuous-pass
bug wearing a different hat; an unreadable input returning "violations found" sends a consumer
hunting a leak that does not exist. Mitigation: the table above is normative, and the spec delta
carries a scenario for it.

**[The `aggregate.py` rename breaks the drift check silently]** → See D5. Mitigation: run
`check_script_drift.py` after the rename and confirm it *reports on the renamed files* rather than
merely exiting 0.

**[The 2b rewrite loses a precedent while "reading better"]** → Both blocks are dense, cross-
referencing prose, and the temptation when replacing a command with a sentence is to tighten the
paragraph around it. Mitigation: a task that diffs old 2b against new 2b line by line and confirms
every sentence except the invocation is preserved verbatim, with the `lite-pr` / `revise.md`
report-name divergence explicitly checked rather than normalised.

**[Trade-off: the mutation gate loses its forcing function downstream]** → Accepted, and it was
already true. The decision doc records that downstream `mutate.py` has "a mandate in two skills, no
forcing function (the pairing guard is source-only), no example batch, and no evidence of use". This
change makes the honest state visible rather than creating it.

**[Trade-off: two guards leave the test gate, permanently]** → Once they are programs, nothing in
`run_tests.py` fails when the *real repo* has a stale path or a leaked token; only their unit tests
run. **This is not a gap that closes later in the batch, and an earlier draft of this design claimed
it was** ("until change (c)'s release-time tree scan lands"). That claim is false and is withdrawn:
the successor's shipped-tree scan is a **filename-shape allowlist** over `git ls-files` output — it
decides whether each shipped path matches one of eleven structural patterns — and it never invokes
`check_no_project_tokens.py` or `check_fact_paths.py`. Nothing else in the successor wires them into
a gate either; its only contact with them is pruning `SOURCE_SCAN_ROOTS` and running the pruned
guard once by hand.

State it plainly, then: **after the whole batch, neither checker has an automatic trigger anywhere
in this repo.** Both are manually-invoked skill helpers.

What actually remains, and it is less than "mitigation" implies:

- `check_no_project_tokens.py` is mandated by `skill-authoring.md` at skill-authoring time — the
  point where a leak is introduced. That is a **procedural** gate an agent can skip, not an
  automatic one. `consistency-checks/tests/test_guards_have_mutant_batches.py`'s module docstring
  records the general form of that failure for the sibling case: *"`mutate.py` is invoked by hand,
  so 'write a mutant' was advice, and advice is what gets skipped at the end of a long session."*
  Read across, that is the risk here.
- `consistency-checks/tests/test_token_list_is_curated_here.py` keeps running automatically, but it
  asserts only that the token *list* is present and non-empty — it never runs a scan.
- `check_fact_paths.py` has **no** surviving procedural or automatic trigger. This is the weaker of
  the two positions and the reason the question below is open rather than closed.

Why accept it here anyway: the alternative is keeping a repo-level pytest assertion in a scope the
successor deletes, which would have to be written and then unwritten within the same batch, and the
promotion is what makes the checkers reachable in *consuming* repos at all — where their coverage
today is zero. The trade is source-repo automation for downstream reachability. It is a real trade,
not a free one, and it needs a follow-up rather than a shrug — recorded as an open question below.

## Migration Plan

No runtime migration; this is source-tree surgery in one commit-series on one branch.

1. Promote `check_fact_paths.py` (the simpler of the two: one repo-level assertion). Re-point its
   tests, add its CLI tests and mutant batch. Run the `conformance-checks` scope.
2. Promote `check_no_project_tokens.py` (four repo-level assertions, plus the D3 fallback-depth
   fix). Re-point its tests **and `test_token_list_is_curated_here.py` (D7)**, add its CLI tests and
   mutant batch. Run the `conformance-checks` and `consistency-checks` scopes.
3. Rename both `aggregate.py` pairs; update the retro SKILL.md invocations and all four
   `consistency-checks` / `run_tests.py` consumers. Run `codify-retro`, `spec-to-pr-retro`, and
   `consistency-checks`.
4. Rewrite both 2b blocks. Prose only — no scope to run; the verbatim-preservation diff is the gate.
5. Doc line fixes (D6).
6. `run_tests.py` once, before opening the PR.

**Rollback:** every step is a self-contained revert. The riskiest two (1 and 2) leave the original
pytest files in place as the tests, so a revert restores the guard's behaviour by restoring one
import line and one file.

**Ordering constraint for the batch:** this change must land before
`extract-dev-tree-from-plugin` — the batch's only other change — which assumes both guards are
already promoted out of `conformance-checks/` and both duplicated basenames are already gone.

## Open Questions

- **What restores an automatic trigger for the two promoted checkers?** Open, and deliberately not
  answered here. After this change and its successor, neither `check_no_project_tokens.py` nor
  `check_fact_paths.py` runs automatically anywhere in this repo (see the trade-off above; the
  successor's shipped-tree scan is a filename-shape allowlist and does not invoke them).
  `check_fact_paths.py` is the weaker case — it has no procedural trigger either. Candidate answers,
  none costed here: a thin test in the successor's consolidated `plugin-tests/` scope that
  subprocess-invokes each checker against the real repo and asserts exit 0 with a non-zero scanned
  count; or wiring both into the `release` skill's precondition block beside the shipped-tree scan.
  **This is a follow-up owed by the batch, not a defect in this change** — the coverage it removes
  from this repo is what makes the checkers reachable downstream at all. Carry it to the successor's
  PR body (task 6.5) so it is not lost when this change closes.
- Does `check_script_drift.py` fail loudly or pass vacuously when a path in its list does not
  resolve? Resolved by running it during step 3, not by reading it. If it passes vacuously, that is
  a defect worth a note to `extract-dev-tree-from-plugin` — a drift detector that cannot detect its
  own subject disappearing is the silent-divergence failure it was built to prevent.
- Should the two promoted checkers share a common exit-code/reporting helper? Deliberately **not**
  in this change: a shared helper is a new module in the shipped tree, and the two checkers differ
  in what they report (paths vs. token+excerpt+line). Revisit only if `extract-dev-tree-from-plugin` makes a third
  checker appear.
