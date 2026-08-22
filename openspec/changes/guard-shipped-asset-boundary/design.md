## Context

Changes (a) and (b) made the plugin tree lean. Neither made it *stay* lean, and neither reconciled
the documentation that describes it. This change does both, and it is the last of the three.

Q5 fixed **where** the check runs — *"a tree scan as a `release` precondition, not a guard in the
test suite"*, because that "fires where the consequence actually lands, at the one deliberate gate
the repo already has", with the accepted tradeoff that "drift introduced in week one is not detected
until the next release". Q5b fixed **where the scan lives** — with the relocated repo-local `release`
skill, because "leaving it shipped would put the check against shipping unusable assets inside an
unusable asset."

Neither fixed **what shape the scan takes**, nor **whether it is a script at all**. Both are settled
below, on measurement rather than preference.

The second half of this change is documentation, and it is the larger half. That makes it the exact
shape root `CLAUDE.md` check 3 governs: *"Asserting a diagnosis, a measurement, or a count? … For a
measurement — 'measured', 'verified', 'zero violations', any number — name the command that produced
it, in the same commit. If you cannot name one, you did not measure it."* Every number in this
design was produced by a command, and each command is named beside it.

## Goals / Non-Goals

**Goals:**

- A future edit that puts a test, a pytest config, a mutation corpus, or any other undeclared shape
  back into `.claude/plugins/cla/` cannot reach a published tag without someone deliberately
  widening the allowlist and saying why.
- The scan names every offending file, refuses rather than warns, and cannot pass by inspecting
  nothing.
- Every repo document describes the tree that exists after (b), and every count in those documents
  was produced by a command run in this change's own commit.
- The two false claims about what reaches a consuming repo are gone from the tree, not softened.
- The findings (a) and (b) explicitly deferred here are resolved or recorded, not lost.

**Non-Goals:**

- **Cutting the `0.11.0` release.** The decision doc anticipates that version; this change adds the
  precondition and does not exercise it. A tag is cut deliberately, from reviewed and merged work.
- Moving, deleting, or adding any shipped asset. The tree (b) produced is the tree this change
  documents and guards.
- Re-litigating Q5's release-time-only enforcement. The week-one gap is the shape of the chosen
  option, and this design states it rather than quietly closing it with a second guard in the suite.
- Fixing the `consistency-checks` split, the 12 grandfathered mutant batches, or any other item
  `TODO.md` carries. This change **re-describes** those entries against the new layout; it does not
  discharge them.

## Pinned implementation parameters

Every value below was produced by a command, named beside it. Nothing here is "set during
implementation."

### The allowlist — the full pattern set

Matched against `git ls-files .claude/plugins/cla`, paths taken **relative to the plugin root**.
Eleven patterns, each with the reason it exists:

| # | Pattern | Why this shape ships |
|---|---|---|
| 1 | `README.md` | The plugin's own front door; its install commands legitimately name this repo. |
| 2 | `.gitattributes` | Carries the `eol=lf` pin for `hooks/*.sh` **inside** the published tree, where a `git-subdir` install can see it. |
| 3 | `.claude-plugin/plugin.json` | The manifest. Exactly one file; the marketplace reads it. |
| 4 | `agents/*.md` | Mechanical helper agents other skills delegate to. |
| 5 | `output-styles/*.md` | The writing convention, `force-for-plugin: true`. |
| 6 | `lib/*.py` | The shared writer every retro-logging skill invokes as a program (`log_run.py`). |
| 7 | `hooks/**` | Any file, any depth. Deliberately shape-agnostic — see the exception below. |
| 8 | `skills/_shared/README.md` | The one `README.md` under `skills/` that is not a skill's; `_shared/` is not a skill. |
| 9 | `skills/*/SKILL.md` | The skill itself. |
| 10 | `skills/*/references/*.{md,json}` | Supporting docs, plus the two permission-set JSON files. |
| 11 | `skills/*/scripts/*.{py,mjs}` | Deterministic helpers a skill calls. |

**Pattern 7 is the one deliberate hole, and it is named rather than hidden.** `hooks/` holds four
genuinely different shapes — twelve `.py` leaf hooks and a dispatcher lib, `hooks.json` (the
wiring), `probe-python.sh` (sourced by every wiring line), and `hooks/git/pre-push` (**no extension
at all**, a `#!/bin/sh` script every clone copies into `.git/hooks/`). Enumerating those shapes
would encode four rules to cover 15 files and would reject the next legitimate hook shape. The cost
is stated plainly: a stray file dropped under `hooks/` is the one thing this scan will not catch.

**Verification of the whole pattern set, with the command.** Against the post-(b) tree,
reconstructed from today's tree by removing the dev-only set and adding change (a)'s two promoted
scripts:

```bash
git ls-files .claude/plugins/cla \
  | grep -vE '(^|/)tests/|(^|/)mutants/|pyproject\.toml$|run_tests\.py$|mutate\.py$|/(conformance|consistency|launcher)-checks/|skills/release/|SOURCE-REPO-ONLY\.md$|mechanical-checks\.test\.mjs$' \
  | sed 's|^\.claude/plugins/cla/||' > ship.txt
printf 'skills/sync-context/scripts/check_fact_paths.py\nskills/_shared/scripts/check_no_project_tokens.py\n' >> ship.txt
grep -vE '^(README\.md|\.gitattributes|\.claude-plugin/plugin\.json|agents/[^/]+\.md|output-styles/[^/]+\.md|lib/[^/]+\.py|hooks/.+|skills/_shared/README\.md|skills/[^/]+/SKILL\.md|skills/[^/]+/references/[^/]+\.(md|json)|skills/[^/]+/scripts/[^/]+\.(py|mjs))$' ship.txt
```

Result: **101 files in, 0 unmatched.** The allowlist covers the post-(b) tree exactly.

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

Patterns 6, 8 and the `{md,json}` alternation in 10 exist for exactly these. Recording the
correction rather than silently substituting it, because the difference between the candidate list
and the pinned one is four files a first run would have rejected.

### Why an allowlist, measured — the denylist's actual miss rate

The denylist candidate was: fail if the tree contains any `tests/` dir, `pyproject.toml`,
`mutants/`, `*.test.mjs`, or `conftest.py`. Run against today's tree (the state a scan would have
had to catch):

```bash
git ls-files .claude/plugins/cla | wc -l                                    # 171 tracked
git ls-files .claude/plugins/cla | grep -E '<dev-only union>' | wc -l       # 72 dev-only
git ls-files .claude/plugins/cla | grep -cE '(^|/)tests/|(^|/)mutants/|pyproject\.toml$|\.test\.mjs$|conftest\.py$'   # 65
```

**65 of 72 caught. Seven missed**, and here is the whole list:

```
consistency-checks/SOURCE-REPO-ONLY.md
consistency-checks/scripts/check_script_drift.py
launcher-checks/SOURCE-REPO-ONLY.md
mutate.py
run_tests.py
skills/release/SKILL.md
skills/release/SOURCE-REPO-ONLY.md
```

Those seven are not an incidental remainder. They are `run_tests.py` and `mutate.py` (Q2's entire
subject), all three `SOURCE-REPO-ONLY.md` (Q4's), and `release` (Q5b's). **A denylist would have
reported clean on precisely the drift the decision doc was written to prevent** — the three
questions it answers are the three it cannot see. This is the same failure this repo has shipped
twice already: a guard that reported clean because the defect sat somewhere it did not scan.

### The false-positive cost, stated honestly

An allowlist rejects every legitimate new shape until someone widens it. Concretely: the first time
a skill needs a `.yaml` reference, a `.txt` fixture a consumer reads, or a `templates/` directory,
the release refuses and the operator must add a pattern before shipping. That is friction at the
worst moment — someone is trying to cut a release. It is accepted for one reason: the failure is
**loud and at the file level** (the scan names the file), whereas a denylist's failure is silent and
global. A refusal that names `skills/foo/templates/bar.hbs` is a thirty-second decision; a clean
report over an unscanned shape is invisible for a release cycle.

### The allowlist grows only with a stated reason — the mechanism, not the hope

Modelled on `test_guards_have_mutant_batches.py`'s `_EXEMPT` block, which already runs this exact
discipline in this repo (lines 28–30):

> `# Guard files exempt from needing a batch, each for a stated reason. Keep this`
> `# list short and justified — it is the pressure valve that could quietly empty`
> `# this test if it grew without argument.`

and enforces it with a companion cap test, `test_the_grandfather_list_only_shrinks`, asserting
`grandfathered <= 12` with the message *"the list was 12 when the convention landed and is only
allowed to shrink. A NEW guard needs a mutant batch, not an exemption."*

The allowlist carries the same two parts: the reason column in the table above is **required per
entry**, and a companion test caps the pattern count at **11**, its size when the convention landed.
The cap is not a prohibition on growth — it is a prohibition on growth that nobody argued for. A
twelfth pattern lands by editing the cap in the same commit that adds the pattern and its reason,
which is exactly the visibility the `_EXEMPT` model buys.

### Enumeration source: `git ls-files`, not a filesystem walk

The scan enumerates via `git ls-files .claude/plugins/cla`. This is not a convenience: `git-subdir`
publishes from the repository, so **tracked files are exactly the files that ship**. A filesystem
walk would additionally flag `__pycache__/` and `.pytest_cache/` (which the root `.gitignore`
already excludes from tracking and which therefore never ship), producing failures on a state that
has no consumer consequence.

### Non-vacuity and the exit contract

| Exit | Meaning | Output |
|---|---|---|
| `0` | Every enumerated file matched a pattern. | One line naming the count and the pattern count, e.g. `check_shipped_tree: 101 files, 11 patterns, 0 violations`. |
| `1` | One or more files matched no pattern. | Every offending repo-relative path, one per line, all of them in one run — never stopping at the first. |
| `2` | The scan could not do its job: `git ls-files` failed, or it enumerated **zero** files. | A diagnostic to stderr. |

Exit `2` on an empty enumeration is the load-bearing row. A scan run from the wrong directory, or
after a path typo, enumerates nothing and would otherwise report "0 violations" — the identical
shape `CLAUDE.md` records for the ledger-dir resolver, *"the retro reports zero runs, which reads as
a cold start."* The printed file count is what makes a shrunken scan visible even when it does not
hit zero.

### Post-change counts carried from change (b)

Carried, not re-derived — with one stated amendment. Each was pinned in
`extract-dev-tree-from-plugin`'s design.md.

| Quantity | Value | Status here |
|---|---|---|
| Tracked under `.claude/plugins/cla/` after (b) | **101** | **Independently confirmed** by the `git ls-files` reconstruction above (99 today + (a)'s 2 promoted scripts). |
| Tracked under `<repo>/plugin-tests/` after (b) | **54** | Carried unchanged. |
| Tracked under `<repo>/.claude/skills/release/` after (b) | **1** (`SKILL.md`) | **Amended to 2** by this change — see D2. |
| Files deleted outright by (b) | **17** | Carried unchanged. |
| Collected-test assertion for (b) | `collected_after == collected_before − 9` | Carried; this change adds tests and so raises the count. |
| Node tests | **70** | Carried unchanged; this change does not touch the Node suite. |
| `SOURCE_SCAN_ROOTS` after (b) | **5** (`skills`, `agents`, `hooks`, `output-styles`, `lib`) | Carried unchanged. |
| `plugin-tests/pyproject.toml` `pythonpath` entries | **9** | **Amended to 10** by this change — see D2. |
| Pytest scopes after (b) | **1** | Carried; this is the number every doc must be reconciled to. |

**One disagreement, stated rather than substituted.** (b) pins `.claude/skills/release/` at 1 file
and its `pythonpath` at 9 entries. Both were correct for (b). This change adds
`.claude/skills/release/scripts/check_shipped_tree.py`, making them **2** and **10**. Change (b)'s
task 6.4 audits the `pythonpath` entry-by-entry, so this change must not silently invalidate that
audit — task 3.4 re-runs it against 10.

## Decisions

### D1 — A structural allowlist, not a denylist

**Chosen: the 11-pattern structural allowlist above.**

The measurement is the argument, and it is in the pinned block: the denylist catches 65 of 72 and
misses the seven files that *are* the three questions the decision doc answers. The principle behind
the measurement is that a denylist can only catch shapes someone anticipated, and this repo has
twice shipped a guard that reported clean because the defect sat somewhere it did not scan —
`CLAUDE.md` records the case where "'widening the scan roots fails on the test fixtures' survived
until someone widened the scan roots and got zero violations", and (b)'s own D7.1 records
`SOURCE_SCAN_ROOTS` silently skipping a vanished root while still exiting 0.

There is a second, structural reason. The set of things that *should* ship is small, stable, and
enumerable — 11 shapes covering 101 files. The set of things that should not is unbounded and grows
every time someone invents a new kind of dev asset. Guarding the small closed set is cheaper to
maintain and is the only one of the two that can be complete.

*Alternative considered — a denylist:* rejected on the measurement. *Alternative considered — both:*
rejected as machinery. The allowlist is a strict superset of the denylist's coverage on the measured
tree; running the second adds a maintenance surface and no detection.

### D2 — The scan is a script, at `<repo>/.claude/skills/release/scripts/check_shipped_tree.py`

The bar this must clear is root `CLAUDE.md`'s: *"A script earns its place only by doing something a
direct command plus a sentence of prose cannot do reliably."* Seven scripts were deleted for failing
it, and user memory records the standing preference for prose over machinery. The brief correctly
notes that the "keep the plugin lean" concern does not apply — this asset lives outside the
published tree — so the decision rests entirely on the merits.

**The prose-and-command alternative, stated fairly.** It is a real option and nearly sufficient:

```bash
git ls-files .claude/plugins/cla | sed 's|^\.claude/plugins/cla/||' | grep -vE '<the 11-pattern alternation>'
```

plus a sentence: "if it prints anything, refuse; if it prints nothing *and* the file count is
non-zero, proceed." One command, two sentences, and the reason column can live in a markdown table
in `SKILL.md` — arguably a better home for prose than a Python comment. There is only one copy of
the pattern list either way, so there is no drift risk between a script and its documentation.

**Chosen: the script**, on three grounds the command cannot cover:

1. **The exit contract is inverted and three-valued.** `grep -v` exits 0 when it prints violations
   and 1 when clean — backwards for a precondition, in a list of five preconditions the operator
   reads by exit status. And it has no third value: "I could not look" (zero files enumerated) is
   indistinguishable from "I looked and found nothing". That third value is the whole non-vacuity
   guarantee, and no shell one-liner in a markdown block provides it without becoming a script in
   all but name.
2. **A regex transcribed by hand is where a silent widening enters.** The alternation is ~200
   characters. A typo that *narrows* it produces a false positive, which is caught instantly. A typo
   that *widens* it — a stray `.*`, a dropped anchor — produces a clean report over an unscanned
   shape, and nobody sees it for a release cycle. This is the silent-failure class this repo
   optimises against, and a human being present at release time does not catch it, because the
   output looks correct.
3. **A script is the only form this repo can test.** Change (b) puts the release skill's tests at
   `plugin-tests/tests/skills/release/`, and the repo's one shipping gate is `pytest`. A regex in a
   markdown code block has no test and cannot acquire one. A script gets seeded-input tests (a
   planted `tests/` dir fails; a planted `pyproject.toml` fails; an empty enumeration exits 2) and a
   mutant batch, which is what `CLAUDE.md` requires of a new script anyway.

**Home:** `<repo>/.claude/skills/release/scripts/`, beside the only skill that invokes it. Q5b's
"it takes the tree scan with it" is satisfied by any location outside the plugin, but co-location
means deleting the skill deletes its check, and there is exactly one caller.

*Alternative considered — `plugin-tests/scripts/`, beside `check_script_drift.py`:* that precedent
is real (a script, not a test, living in the dev tree because its subject is this repo's own
source), and it would need **no** `pyproject.toml` edit, since `pythonpath` entry 1 is already
`scripts`. Rejected because the scan has one caller and belongs with it. The cost is explicit: a
10th `pythonpath` entry, `../.claude/skills/release/scripts`, amending a number (b) pinned and
audited — which is why task 3.4 re-runs (b)'s audit rather than assuming it still holds.

**Size discipline, since the memory preferring prose is a real constraint and not a formality.** The
script is an enumeration, a pattern list, and a match loop. If the implementation exceeds roughly
120 lines excluding the pattern table and its reasons, that is a signal it has grown a second job,
and the second job should be questioned rather than accommodated.

### D3 — The two false claims are deleted, and the `.gitattributes` rules are re-verified

Both are corrections the decision doc names explicitly, and both need deleting rather than
rewording, because a reworded false claim is still a claim about a consuming repo that nobody has
checked.

**Root `.gitattributes`.** The file's comment block ends with a "TWO BELTS to this braces" list. The
second belt reads: `hooks/tests/test_hooks_wiring.py::test_the_probe_has_no_carriage_returns` "ships
with the plugin, so it also fires in a consuming repo." After (b), that file lives in
`plugin-tests/` and does not ship. It was also never true: nothing downstream ever invoked it — a
consuming repo has no pytest gate over the plugin cache, which is the same fact commit `a9ea9cf`
recorded about the two conformance guards.

The surrounding block is **load-bearing and stays**. It documents a measured, platform-divergent
CRLF hazard (Cygwin/Git Bash strip the CR, `dash` syntax-errors), and it records a *previous*
correction where an earlier version of the same comment asserted a failure mode that does not occur
and "got the mechanism backwards besides". Deleting more than the one false bullet would repeat that
error in the opposite direction. The first belt — `.claude/plugins/cla/.gitattributes` carrying the
same pin inside the published tree — is true, still true after (b), and stays.

**Every `eol=` rule is unchanged**, and every pinned path is re-checked to resolve, because one of
them (`.claude/plugins/cla/hooks/git/pre-push`) names a path inside the plugin and the sweep must
confirm (b) did not move it. It did not — `hooks/` stays shipped in full — but "it did not move" is
a fact to verify, not to assume, and task 4.2 verifies it for all four patterns.

**`CLAUDE.md`'s "portable core that reaches consuming repos".** After (a) and (b), `conformance-checks`
does not exist as a directory: two of its five guards are skill scripts in the plugin, three are
tests in `plugin-tests/`. The sentence has no true reading, so it goes rather than being narrowed.
What replaces it is the honest statement — the two promoted checkers reach consumers because they
are skill scripts inside the shipped tree, and the three plugin-data guards do not reach consumers
at all and are not meant to.

### D4 — Every count in a doc is produced by a command in this change's own commit

This change writes numbers into prose: how many pytest scopes, how many tests, how many files ship,
how many rows the script table has. `CLAUDE.md` records six such claims caught in one review session
— *"in one of them the comment's own text contained the token it declared absent"* — and a seventh
caught on the PR that added the rule, "a commit count nobody had run, in three files including the
hook written to measure it."

So the rule for this change is mechanical: **a number reaches a doc only as the recorded output of a
command run in the same commit.** tasks.md section 5 pairs every count with its command, and task
7.3 re-runs the whole set as a block before the PR, because a number measured at the start of the
change has expired by the end of it (user memory: "a measurement has an expiry"). Counts that must
be produced this way, at minimum:

- pytest scopes: **1** — `find . -name pyproject.toml -not -path './.git/*'`
- collected tests — `pytest --collect-only -q` from the repo root
- Node tests — `node --test plugin-tests/node/mechanical-checks.test.mjs`
- files under `.claude/plugins/cla/` — `git ls-files .claude/plugins/cla | wc -l`
- rows in the "Every script, and why it exists" table — one per script actually present, listed by
  `git ls-files '.claude/plugins/cla/**/scripts/*' .claude/plugins/cla/lib`
- hand-watched unscanned files (`CLAUDE.md` says four today) — the count changes because
  `run_tests.py` and `mutate.py` were two of them

### D5 — The two inherited findings are resolved here, and a third was found

**(a) task 3.10 — does `check_script_drift.py` pass vacuously on a missing path?** (a) records the
finding; (b) inherits the file. (c) resolves it, because (b)'s Open Questions assign it here unless
the move itself caused it. If the answer is "vacuous", the fix is the same shape as the exit-`2`
row above: a resolver that cannot find its subject must fail, not report clean.

**(b) open question — does `test_guards_have_mutant_batches.py` hardcode a pairing that deleting
`test_source_only_markers.py` invalidates?** **Answered by reading the file, in this design:** its
`_EXEMPT` dict (line 31) is a hardcoded literal, but `test_source_only_markers.py` is **not in it** —
it has a batch. The guard list itself is derived from the tree by `_guard_files()` (line 71), which
globs `_PLUGIN_ROOT / scope / "tests"`. So the deletion needs **no** `_EXEMPT` edit, and (b)'s open
question resolves to "no hardcoded pairing to fix."

**Reading it surfaced a second problem the open question did not ask about — and then a
counterexample that changes who owns it.** `_CHECK_SCOPES = ("conformance-checks",
"consistency-checks")` (line 26) and `_guard_files()` (line 71) glob those two directories **under
the plugin root**. After (b) neither exists there. `glob()` on a missing directory returns empty and
does not raise, so `_guard_files()` returns `[]` and the loop in
`test_every_guard_file_has_a_mutant_batch_beside_its_scope` never executes — that assertion alone
would pass while checking nothing, and all 14 `_EXEMPT` keys would name paths that no longer resolve.

**The counterexample, found by searching the same file for what refutes the diagnosis rather than
only for what supports it** (`CLAUDE.md` check 3): a sibling test in the same file,
`test_the_scan_is_not_vacuous` (line 143), asserts `len(files) >= 6` with the message *"guard
discovery collapsed to {len(files)} files"*, and separately asserts the batch list is non-empty. So
the file does **not** fail silently — it fails **loudly**, on a different assertion than the one that
matters. Which means change (b)'s own bare-`pytest` gate goes red, and (b) cannot ship without
fixing it. **This is therefore (b)'s fix, not (c)'s.**

What (c) owns is the verification, and it is not a formality, because the cheapest way to turn that
red assertion green is to delete it or lower the `6`. Task 6.2 confirms three things about the state
(b) left: `_CHECK_SCOPES` names directories that exist in the dev tree, all 14 `_EXEMPT` keys resolve
to real files, and the `>= 6` floor is still present and still a floor — re-pointed rather than
weakened. A non-vacuity assertion that was relaxed to make a move green is worse than one that was
never written, because it now certifies the thing it stopped checking.

### D6 — `TODO.md` entries are re-described, not discharged

Four `TODO.md` entries describe a tree that no longer exists. The temptation is to delete the ones
that "look done"; the rule here is that a re-layout does not discharge a debt.

- **"Source-repo-only scopes — chosen: a per-scope marker file"** — the mechanism is deleted by (b).
  This entry's *decision* is now moot and the entry is replaced by one sentence recording that
  source-repo-only became structural, so the marker mechanism has no subject.
- **"Split `consistency-checks` so consumers keep its portable half"** — **moot, and worth saying
  why**: consumers never received `consistency-checks` after (b), so there is no portable half to
  preserve for them. The entry goes, with the reason recorded.
- **"Write mutant batches for the 12 grandfathered guards"** — **live, unchanged in substance**, but
  every path in it moved. Re-point, keep the count, keep the `_EXEMPT` cap discipline.
- **"Remaining unscanned surface after the scan-root widening"** — the file counts and the
  four-file list are falsified by (b) (`run_tests.py` and `mutate.py` were two of the four and no
  longer ship). Re-measure with the command, do not adjust the numbers by arithmetic.

### D7 — The docs have a guard of their own, and it fails the doc fix

`test_doc_facts.py` is a drift guard over **all four** docs this change edits — its `_DOCS` map
(lines 39–42) names `CLAUDE.md`, the root `README.md`, `DEVELOPER-GUIDE.md`, and the plugin
`README.md` — and its own docstring lists what it pins: *"the skill count, the pytest-scope count,
the count of skills shipping tests, the leaf-hook count, and the release version."* It is one of only
three guards in the repo that ships a mutant batch, so it is a guard that has been shown to fail.
Every number in its list is a number this change rewrites.

It fails in **two different ways**, and only one of them is obvious:

1. **Derived counts self-correct and fail the doc.** `real_skill_count()` (line 52) counts the tree
   rather than trusting a literal, and excludes `_shared/` explicitly because "counting it here would
   make every doc that says …" wrong. Measured today: `ls -d .claude/plugins/cla/skills/*/ | wc -l`
   → **22**, minus `_shared/` → **21**; once `release` moves out it becomes **20**, and the root
   `README.md`'s "21 workflow skills" fails on its own. This is the guard working.
2. **Anchored assertions fail on the rewrite itself, not on the number.** Several checks locate their
   subject by literal phrase — `("CLAUDE.md", "pytest scope —")`, `("README.md", "every pytest
   scope")`, `("plugin README.md", "isolated\npytest scope")` (lines 163–166) — and the release check
   requires `CLAUDE.md` to still state `**Current release: `cla--v<version>`**`, failing with
   *"CLAUDE.md no longer states…"* otherwise. This change rewrites exactly those sentences. A rewrite
   that drops an anchor fails with "no longer states", which reads like a broken guard and invites
   the wrong fix: deleting the assertion.

**So the sequence is fixed, and it is the whole point.** Edit the doc, run the guard, read *which*
of the two failures it is. A derived-count failure means update the doc to the measured value. An
anchor failure means the rewrite dropped a claim the repo deliberately pins — restore a phrase the
anchor can find, or move the anchor *and say why in the same commit*. What must not happen is
editing the guard first, so the doc lands against an expectation already loosened to accept it. Task
5.6 states this order explicitly, because the failing run is the cheapest proof available that the
guard still covers the claim.

## Risks / Trade-offs

**[The allowlist is transcribed wrong and silently widens]** → The exact defect D2 chose a script to
prevent, and choosing a script does not by itself prevent it. Mitigation: seeded-input tests that
plant a violating file of each denylist shape (`tests/` dir, `pyproject.toml`, `mutants/`,
`*.test.mjs`, `conftest.py`) and assert exit 1 naming it, plus the empty-enumeration exit-2 test,
plus a mutant batch. A pattern list nobody has shown can reject anything is an allowlist that
matches everything.

**[The scan passes vacuously]** → Exit `2` on an empty enumeration plus the printed file count. The
scan is run from the release skill, whose working directory is the repo root, but a precondition
that depends on cwd and reports clean when wrong is the failure this repo names most often.

**[Week-one drift ships]** → Accepted, and it is Q5's chosen tradeoff verbatim: "drift introduced in
week one is not detected until the next release." Not silently closed with a second guard in the
suite, because that is the option Q5 rejected. Stated in the spec text so a reader meets the
tradeoff rather than discovering it.

**[A doc gets a number that was reasoned about]** → D4, and it is the most likely defect in this
change by volume. Every count in tasks.md section 5 names its command; task 7.3 re-runs them as a
block before the PR because a measurement taken at the start of a long prose change has expired by
the end.

**[A rewrite drops a rule while "reading better"]** → `CLAUDE.md`'s check 2. Several sections here
are substantially rewritten rather than line-edited — the 12-scope paragraph, the No-CI section, the
script table. Mitigation: task 7.2 diffs old against new per section and states what was dropped,
and the two *deliberate* deletions (D3) are named in advance so an accidental third is visible
against them.

**[The `.gitattributes` edit takes the rules with the comment]** → The block's own history is the
warning: a previous edit to this comment asserted a failure mode that does not occur on the platform
it named. Mitigation: task 4.2 diffs the file and asserts that the four `text eol=` lines are
byte-identical, and independently confirms each pinned path resolves.

**[The `pythonpath` amendment invalidates (b)'s audit]** → D2's accepted cost. Mitigation: task 3.4
re-runs (b)'s task 6.4 audit against all 10 entries rather than trusting the 9-entry result.

**[`TODO.md` debt is deleted rather than re-pointed]** → D6. Two entries genuinely become moot and
two do not, and they read similarly. Mitigation: task 6.4 requires a one-line stated reason per
entry — kept-and-re-pointed, or removed-because-its-subject-is-gone.

## Migration Plan

No runtime migration. Source-tree edits on one branch, after (b) has landed.

1. Confirm (b) landed: `.claude/skills/release/SKILL.md` exists, `plugin-tests/` exists,
   `.claude/plugins/cla/run_tests.py` does not.
2. Write the scan, its tests, and its mutant batch. Run the seeded-input tests before wiring it in.
3. Wire it into the release skill's step 1 as a fifth precondition.
4. Resolve the inherited findings (D5), including the `_CHECK_SCOPES` vacuity this design found.
5. Delete the two false claims (D3).
6. Reconcile the docs, measuring every count as it is written (D4).
7. Re-run the measurement block, then `pytest` from the repo root, once.

**Rollback:** every step is a self-contained revert; no tag is cut, so nothing has been published.

**Ordering:** strictly after `extract-dev-tree-from-plugin`, which is strictly after
`decouple-skills-from-dev-assets`.

## Open Questions

None blocking. Two recorded for the implementer to resolve with a command rather than a guess:

- **Does (a)'s task 3.10 report `check_script_drift.py` passing vacuously?** If (a) recorded the
  finding, task 6.3 fixes it here. If (a) recorded that it fails loudly, task 6.3 confirms that is
  still true from the file's new home and closes the thread. Either way the answer comes from
  running it.
- **Does the mutant-batch cap test need its bound changed?** `test_the_grandfather_list_only_shrinks`
  asserts `grandfathered <= 12`. This change re-keys `_EXEMPT` but should not change that count.
  If re-keying changes it, something was dropped — the count is the check, not the keys.
