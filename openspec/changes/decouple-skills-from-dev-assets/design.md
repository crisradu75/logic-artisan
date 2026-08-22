## Context

`.claude/plugins/cla/` is published verbatim as one `git-subdir` marketplace snapshot. The docs for
that source type list exactly `url`, `path`, `ref?`, `sha?` — **no exclusion field** — so the only
lever on what a consumer receives is what lives under `path`. Change (b) uses that lever by moving
the dev tree out. This change is the prerequisite: it severs the three ties that would otherwise
break when the dev tree leaves.

Three ties, and they are not the same kind of problem:

1. **Two shipped skills mandate a dev-only runner.** `lite-pr/SKILL.md:129` and
   `spec-to-pr/references/revise.md:94` both instruct `python3 ${CLAUDE_PLUGIN_ROOT}/mutate.py`.
   After (b) that path does not exist in a consuming repo, so the mandate becomes an instruction to
   run a missing file.
2. **Two guards that read the *consuming* repo's data are trapped in a pytest scope.** Commit
   `a9ea9cf` ("Fix both conformance guards being silently inert in every consuming repo") records
   that these two were deliberately engineered to run from an installed copy against the consuming
   repo — and once fixed "immediately found a stale path there that had been invisible". A consumer
   has no pytest gate over the plugin cache, so today the only way to run them is by hand as
   `python3 -m pytest <path-inside-the-cache>`. They already behave as skill helpers; they are just
   filed as tests.
3. **Two module-name collisions pin the 12-scope pytest split.** Measured, the entire justification
   for 12 isolated scopes is `scripts/aggregate.py` and `tests/test_aggregate.py`, each existing
   twice (codify-retro and spec-to-pr-retro). One process cannot import both.

The decomposition rule from the decision doc governs the shape of this change: **every content
rewrite lands before any relocation.** Git renders a rewritten-and-moved file as delete+add, so
bundling these rewrites with (b)'s ~70 renames would make the highest-risk edits the least
reviewable ones in the diff.

## Goals / Non-Goals

**Goals:**

- Both downstream-live guards become programs a consumer can run: `python3 <script>`, exit 0 clean,
  non-zero with the offending paths named. No pytest needed downstream.
- Every assertion the two original pytest modules made against the real repo survives the rewrite,
  demonstrably — not by the author's recollection.
- The mutation gate survives as an obligation while its tool reference goes, with every named
  precedent in both blocks preserved verbatim.
- The two `aggregate.py` collisions are gone, and every consumer of the old names — including the
  three in `consistency-checks/` that the decision doc does not mention — is updated in the same
  commit.
- The tree is left in a state where change (b) is a pure `git mv` exercise.

**Non-Goals:**

- **No file moves and no deletions of the dev tree.** `conformance-checks/` still exists as a scope
  when this change lands; the three plugin-data guards stay in it; `run_tests.py` and `mutate.py`
  both still exist. All of that is change (b).
- **No release-time tree scan**, no `release`-skill relocation — change (c).
- **No broad doc reconciliation.** `CLAUDE.md`'s scope count, layout tree, `DEVELOPER-GUIDE.md`, the
  plugin `README.md`, root `.gitattributes` and `TODO.md` are change (c)'s. This change fixes only
  doc lines it *itself* makes factually false.
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

Underscores, not hyphens: these are importable Python module names, and the retro tests invoke them
both as subprocesses and (for the collision comment) by module identity.

### Where the old tests point after the promotion

The pytest files stay in `conformance-checks/tests/` for this change and import the promoted module
**by file path via `importlib.util.spec_from_file_location`**, not by adding a `pythonpath` entry to
`conformance-checks/pyproject.toml`. Two reasons: that scope deliberately has no `pythonpath` today
(its tests import nothing), and a path-based load survives change (b)'s relocation with a one-line
edit instead of a scope-config change.

## Decisions

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
repos" — is **left alone on purpose** and belongs to change (c), `guard-shipped-asset-boundary`.
Line 96 is a borderline call worth naming: after this change no two scopes share a module name, so
its stated justification is weakened. But the 12-scope split it justifies still exists until (b)
collapses it, so rewriting it here would describe a tree that does not yet exist. Left to (c).

Generic mentions in `_shared/references/retro-skeleton.md` ("the calling skill's `aggregate.py`")
and `run-log-schema.md` are **not** path references — they name a role, and each retro skill still
has exactly one aggregator. A task checks them rather than assuming; the expected outcome is that
the role-shaped ones stand and only path-shaped ones change.

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

**[Trade-off: two guards leave the test gate]** → Once they are programs, nothing in `run_tests.py`
fails when the *real repo* has a stale path or a leaked token; only their unit tests run. In this
source repo that is a genuine reduction in automatic coverage until change (c)'s release-time tree
scan lands, and the decision doc's own "Open, and not decided here" section accepts the equivalent
gap between (b) and (c). Partially mitigated by `skill-authoring.md` mandating the token checker at
skill-authoring time — the point where the leak is actually introduced.

## Migration Plan

No runtime migration; this is source-tree surgery in one commit-series on one branch.

1. Promote `check_fact_paths.py` (the simpler of the two: one repo-level assertion). Re-point its
   tests. Run the `conformance-checks` scope.
2. Promote `check_no_project_tokens.py` (four repo-level assertions, plus the D3 fallback-depth
   fix). Re-point its tests. Run the scope.
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
`extract-dev-tree-from-plugin`, which assumes both guards are already out of `conformance-checks/`
and both module collisions are already gone.

## Open Questions

- Does `check_script_drift.py` fail loudly or pass vacuously when a path in its list does not
  resolve? Resolved by running it during step 3, not by reading it. If it passes vacuously, that is
  a defect worth a note to change (c) — a drift detector that cannot detect its own subject
  disappearing is the silent-divergence failure it was built to prevent.
- Should the two promoted checkers share a common exit-code/reporting helper? Deliberately **not**
  in this change: a shared helper is a new module in the shipped tree, and the two checkers differ
  in what they report (paths vs. token+excerpt+line). Revisit only if change (b) makes a third
  checker appear.
