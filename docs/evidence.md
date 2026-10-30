# Evidence behind CLAUDE.md's rules

Part of the [CLA developer guide](../DEVELOPER-GUIDE.md), section 12.

`CLAUDE.md` states each rule once, in its compressed form, and points here from its first
paragraph for the measurement, incident or decision that produced it. Kept verbatim so the evidence
survives; each heading names the rule it backs. Where `CLAUDE.md` compressed a rule when it became
rules-only (change `claude-md-rules-only`), the full earlier wording is kept here too, so nothing the
compression left out is lost.

### The parallel gate: measurements and the cache incident

**Measured on this repo 2026-09-05:** serial 296.6s and `-n auto --dist loadfile` 149.6s
(2.0x). The pass count moved several times inside the branch that measured it and is deliberately not repeated here — run the command; `--collect-only -q` gives the total without executing anything. Plain `-n auto` ran 84.9s and 100.9s on
two consecutive invocations of the same tree — and **the first of those failed 3 tests
the other two forms passed**, all in `tests/hooks/test_hooks_wiring.py`
(`test_wiring_refuses_when_the_probe_is_unusable`, the `truncated` cases). The second
invocation was green. So the plain `-n auto` trap CLAUDE.md describes is not a hypothetical any more; it is the most
recent measurement, and the failure did not reproduce on demand, which is the whole
problem with it.

The mechanism was never proven, but the shared state it named was real and is now gone.
Those tests built their environment with `_inherited_env`, which copies the real `HOME`,
so the probe resolved its cache to the **developer's own** `~/.cache/cla/pyexe` and wrote
it — one shared mutable file, several xdist workers, and `--dist loadfile` keeps that
file's tests on one worker, which fits only plain `-n auto` failing. An autouse fixture in
`plugin-tests/tests/hooks/conftest.py` now relocates it per test via `CLA_PROBE_CACHE`.

**State this carefully.** The failure never reproduced on demand, so no run count proves
it fixed, and none is offered as if it did. What is measured is narrower and is the
reason the change is worth having anyway: deleting `~/.cache/cla/pyexe` and running the
full suite used to recreate it and now does not. A test suite writing a developer's home
directory was a defect on its own terms, whatever it did to the scheduler.

**Numbers here go stale, and this paragraph has been stale before.** Re-measure rather
than quoting it; the counts above move with every test added.

**The rules' full wording, as `CLAUDE.md` carried it before the rules-only compression.**
`loadfile` pins every test in a file to one worker. Without it a module's tests are split across
workers, and `tests/skills/annotate/test_page_in_a_browser.py` has module-scoped fixtures that own
a loopback server port and a Chromium process — two workers building those race for the port.
That suite skips wherever Playwright is absent, which is exactly why a green plain `-n auto` here
is not evidence: it means those tests did not run.

A parallel run is trusted only when its pass AND skip counts match a serial run of the same tree.
Skip counts matter here specifically: `tests/consistency/` and `tests/launcher/` skip their whole
scope conditionally, and the annotate browser suite skips without Playwright — so a dropped scope
shows up as a skip-count change and nowhere else. The check is necessary, not sufficient: it
catches gross divergence, not a test passing for the wrong reason.

### Why `mutate.py` stays serial

It shells out as `pytest -q -x <targets>` and reads the exit code to decide killed vs survived — a
judgement its own docstring says every check exists to protect. This is why `-n auto` is NOT in an
`addopts` key: `addopts` applies to every invocation, so putting it there would silently change how
the mutation runner executes.

### Why `--dist loadfile` is worth its premium

The peer repo `claude-plugins` hit the same class of
failure from a different cause and recorded the rule as "the full-suite pass is luck
about which worker gets which file, not evidence of safety". The premium over plain
`-n auto` was 18s when first measured and about 50-65s on 2026-09-05; either way it is
the whole price of not finding out the hard way, and the run above is what finding out
looks like.

### Why the twelve test scopes became one

The twelve-scope split existed for exactly one reason — pytest's default import mode cannot hold
two test modules with the same basename — and the collision set is now empty. Measured with
`git ls-files '.claude/plugins/cla/**/tests/*.py' | xargs -n1 basename | sort | uniq -d`, the only
duplicate is `conftest.py`, which pytest special-cases per directory. (Note for anyone re-deriving
this: the split's usual justification named a second collision on `scripts/log_run.py`, which
`git ls-files | grep log_run` shows never existed — one module, one test. The measurement, not the
folklore.)

### Why the Playwright suite earns its exception

Keep it to what a string cannot answer — geometry, stacking, what a breakpoint does to the flow,
whether a round-trip leaves the page in the state it claims. Anything checkable by reading the
generated source belongs in `test_render_doc.py`, which is cheaper and always runs.

**Why it earns the exception.** Every other check on the annotation page is a string grep
against generated HTML and JS, which is all a stdlib suite can do. During the
review of the margin change, a reviewer simulated 21 plausible regressions
against the rendered page and **19 survived all 46 tests then covering it** — and
two defects that shipped in that change were found only by driving a browser: an
open drawer laid on top of the margin at 1440px, and a note drawn at
`top:-135.78px` beside nothing for a block on a hidden tab. Neither has a string
to grep for. Its mutant batch re-breaks six such regressions and all six die
(`plugin-tests/mutants/annotate/test_page_in_a_browser.py`).

### The five checks: the shape every escape had

The plugin's behaviour lives mostly in markdown, so a prose edit ships like code but nothing
compiles it. Every defect that reached review in this repo had one shape: the artifact was checked,
the system it lands in was not.

### Check 1: what an inserted step inherits

**The rule's wording before the plain-language rewrite.** A phase added between two others
inherits whatever the next one asserts on entry — a clean-tree check, a state file, a branch
assumption.

### Check 2: why a rewrite is diffed

A rewrite silently loses rules an edit would have preserved; "it reads better" is not evidence that
nothing went missing.

### Check 3: the escapes that produced it

**The rule's full wording before the rules-only compression.** Two halves, and the second is the
one that keeps escaping. For a **diagnosis**, search the same source for counterexamples before
shipping it, not just for supporting cases — a table of three examples proves nothing if three
counterexamples sit in the same file. For a **measurement** — "measured", "verified", "zero
violations", any number — name the command that produced it, in the same commit. If you cannot name
one, you did not measure it: delete the claim or go run it. Reasoning that feels like measurement is
the most expensive thing in this repo, because it ships with a measurement's authority. **And a
measurement is evidence about the tree and conditions it ran on, nothing else.** A pair asserting
sameness — "unchanged", "same counts", "no regression" — must come from one tree, and say so;
measured on two it asserts a third claim, that conditions matched, with no command behind it. A
before/after delta is the exception, not a violation: "faster", "up exactly N" are two trees by
construction, so name both. Re-asserting an earlier number as current is the same defect with one
run missing, and a number true under one platform, shell or edition is not true generally until
someone runs the others.

Measured 2026-09-12, three times in one session: a firing count restated as 84 that re-ran at 86 (test runs had moved it); a gap table that went stale inside the change that invalidated it, claiming 33% headroom where 2.4% remained; and a `Remove-Item` failure measured on Windows PowerShell 5.1 and reported as universal, where the tool actually runs pwsh 7.6.6 and the command works. Recorded in `cla.io/lessons-learned/lessons-learned.md` (2026-08-14): review caught six such claims in one session, and in one of them the comment's own text contained the token it declared absent. Two more were invented blockers — "widening the scan roots fails on the test fixtures" survived until someone widened the scan roots and got zero violations. A seventh was caught by the merge check on the PR that added this very rule: a commit count nobody had run, in three files including the hook written to measure it.

### Check 4: the fix's second branch

A fix is a change like any other and earns the same evidence the original code needed; "the
reviewer's finding is now handled" is not that evidence. A fix also has a second branch nobody
looks at: correcting one return path of a function commonly breaks another, which is how
`lint_profile` traded a silent no-op on the default path for the identical no-op on the overlay
path.

### Mutation testing is opt-in: the PR behind the rule

Decided by the owner on 2026-10-14. A mutation batch (`mutate.py` planting bugs and confirming a
test catches each) is no longer a required step anywhere. It runs only when the owner asks for it,
or when a guard hook under `.claude/plugins/cla/hooks/` is rewritten. The floor that stays
everywhere is breaking each review fix by hand once and confirming a test fails, then restoring it.
The rules about reading the killing test and running `mutate.py` serially, never beside a reading
agent, still apply whenever a batch is run. This supersedes the story below.

The evidence is PR #365 ("feat: spec-proof-checker", merged as `f929ac2`). The facts about that PR
below are from its body (`gh pr view 365`). Its body reports an earlier version of the batch run with 40 of 40
killed. The batch was then extended to 67 mutants, and that run was stopped by the owner before it
finished, on the decision that mutation testing is opt-in. The extended batch was never run to
completion against the final code (`plugin-tests/mutants/_shared/test_check_spec_proof.py`). The
review found its defects without it: round 1 found 5 and the single review over the whole diff
found 7 Important, and each fix was broken by hand once with a test failing. The evidence for
PR #320 in the superseded section below (from its own `gh pr view 320` figures) shows the same
shape: 2 test gaps against 16 review findings. The owner's stated reason (2026-10-14, not from
either PR body) was that each batch run is serial and blocks the agent for a long time, and that
the cost is "prohibitively expensive as a validation process with no clear benefit".

### Superseded: mutation runs only for guards and checkers: the PR behind the rule

*Superseded by "Mutation testing is opt-in" above; kept for its evidence.* Check 4 used to require a mutation batch for every review fix. It now requires one only in a guard
hook or a checker, once per PR, after the last fix. Every other fix needs one test that fails
without it, shown by breaking the fix by hand.

**The rule's wording before this change.** Check 4: "Break the fix and confirm a test fails:
`python3 plugin-tests/mutate.py <batch.py>`". The table row for a review fix: "that area, plus a
mutation batch over what the fix touches". The clean-run bullet: "Plant bugs in everything the fix
touches, not only the line it meant to fix."

The evidence is PR #320 ("annotate: make the change page readable for a human reviewer", merged
2026-10-09, merge commit `ca3b13a`). Every number below is from its body (`gh pr view 320`) or from
`git show 18bb37c`. Most of its code is the annotate change page, which renders documents. That
code is not a guard or a checker.

- **Review found the defects.** The first review round had 2 critical and 11 important findings.
  The second had 3 important findings. The fixes follow OpenSpec 1.14.1's own `dist/` code. The PR
  body credits no defect to a mutation run.
- **Mutation runs found 2 test gaps.** Each was a mutant that survived and got a new test: the
  "listed under New Capabilities" rule at the first push, and an "unknown" capability shown as
  "modified" in the first fix round.
- **One killed mutant protected a wrong behaviour.** The batch at the first push held "a MODIFIED
  header matches the main spec only with identical spacing", which replaced
  `" ".join(name.split())` with `return name`. A test killed it, and that run reported 26 of 26
  killed. The simpler form was the right one: OpenSpec's `normalizeRequirementName` counts inner
  spacing. Review found it as critical 1. This is the false reassurance "A killed mutant" below
  describes. `git show 18bb37c -- plugin-tests/mutants/annotate/test_openspec_change.py` shows the
  mutant replaced.
- **The batches were re-run in each round.** They ran serially, as `mutate.py` must. The runs
  covered 78 mutants at the first push, 111 after the first fix round and 135 after the second.

So outside the guards and checkers, each round paid for serial batch runs. Against 16 review
findings, the runs found 2 test gaps, and they reported one wrong test as a pass. A guard is
different: a broken one fails silently, and a planted bug is the cheap way to see it fail.

The stories behind check 4 and the clean-run, survivor and concurrent-run rules are all about
guards or checkers. That is why the rule keeps mutation runs for them. (The "A killed mutant" case
came from a consuming repo; its rule applies whenever a batch runs.) `1cf09da` and `0027bc7` ("A
clean mutation run") changed two guard hooks since deleted, warn-lint-on-edit and
block-direct-push-to-main. `lint_profile` (check 4) was in warn-lint-on-edit. `check_labels_agree` ("A survivor") is a consistency guard test, and
`check_script_drift` ("Concurrent mutation runs") was a guard, since deleted.

### Check 5: the escape that produced it

Check 5 is check 4's second-branch problem one level up: there, the other branch is inside the
function; here, it is in a file you were not looking at. Running the one scope you work in green is
what makes the omission feel finished.

Measured 2026-08-23 — `scan()` in `check_fact_paths.py` gained a third return value, the three callers in `tests/conformance/` were updated, that scope passed, and a fourth caller in `tests/consistency/` went red only when the full suite ran. One `grep -rn "<name>(" ` would have found it before the first edit.

### A clean mutation run: the commits behind the rule

Measured on this repo: commits `1cf09da` and `0027bc7` each
recorded "three mutations checked, all caught" and each shipped a critical that a later
review found — the mutants covered the branch the author was reasoning about, not the
branch they got wrong.

### A killed mutant: the case behind the rule

The kill proves the suite reacts to that edit; it proves neither the code nor the test right. A
test written from a wrong mental model kills mutants exactly as reliably as a correct one, and the
green result reads as confirmation. Worst where the mutant is the *simpler* form of the code: if the
simpler form is correct, the test defending the original is defending the defect, and the gate pins
it while reporting green.

Reported from a
consuming repo (issue #193), where the assertion killing a column-offset mutant was
itself the defect: the mutant died, the gate reported green, and the wrong belief
reached a PR. A review agent reasoning from the type's stated invariant caught it
there; no gate did.

### A survivor: the batch behind the rule

Some mutants cannot be killed, because the edit is unobservable in a correct tree — a floor
constant that only binds when something is missing, or two expressions that agree on every input
the real files reach. **Where a guard's two candidate rules agree on all correct inputs, mutate the
input, not the guard** (CLAUDE.md now says it as "add a bad input file instead of breaking the
check"). Never leave one in a batch: a survivor nobody acts on trains the next reader to skip the
whole list.

Measured 2026-08-28 with
`python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_check_labels_agree.py`
over a then-nine-mutant batch: two survived and neither could have done otherwise. The
`defined - _delegated_labels() - covered` one was fixed by mutating the *prose* the guard
reads instead of the guard, which does discriminate and is killed; the `_MIN_MARKED_LINES`
floor constant was deleted from the batch with the reason recorded in it.

(The batch has since been reworked, so re-run it rather
than expecting nine.)

### Concurrent mutation runs: the flake behind the rule

Recorded after
a guard flaked 3-of-5 runs under a concurrent batch, and reproduced twice on 2026-08-28
during the review of the commit that added CLAUDE.md's rule — one agent read a mutated
`check_script_drift.py`, another aborted at preflight on a leftover `.mutate-backup`.

### Matching the checking to the change

The five checks are priced for a *fix* or a new component — the cases where being wrong is
expensive and invisible. An increment to something already built and already tested does not earn
them, and paying them anyway is not caution, it is waste with the shape of rigour.

### Repeated green runs: the session behind the rule

Recorded
2026-08-22, after adding a navigation rail to `annotate` cost five full scope runs, a whole
sweep of the entire suite, and an unrelated change to a server, for an edit whose real gate
was one 13-second run over that one area and looking at the page. (The runner those runs
used is gone; the lesson is about the count, not the command.)

### Unarchived merges: the measurement behind the rule

Measured 2026-08-28: three fully-implemented merged changes had accumulated unarchived (merged without Archive), and `openspec/specs/cla-plugin/spec.md` was missing 11 requirements — the shipped skills carried behaviour no live spec described.

### The scan roots: why five

It was eight until the dev tree moved out; the three `*-checks/` entries then named directories that no longer exist, and a stale root is worse than a missing one, because the guard refuses to run at all rather than quietly scanning less.

### The coverage lists: why they are not restated

They were spelled out in CLAUDE.md's architecture paragraph and went stale inside the very change that widened them — twice, once in the widening and once in the fix, each time three lines below a sentence saying not to restate them.

Both used to be written out as a list and a count, and both went stale while nothing noticed — the defect issue #178 named.

### No CI: the decision behind the rule

Not an incident — an owner decision. CI existed briefly: `.github/workflows/tests.yml` ran pytest on
ubuntu and windows × Python 3.11/3.13 plus the Node suite, added in #18. It was deleted in #24
(commit `b444dd2`, "This repo does not want CI"), which also wrote down the two consequences
CLAUDE.md still carries: code that differs by platform is exercised only on the machine you are on,
and nothing gates a merge, so the local run before opening a PR is the only gate.
`git log --oneline -- .github/workflows` shows both commits.

### Stdlib-only shipped scripts: why

No incident either; the reason is the rule's own. A repo installs the plugin as a copied folder and
never runs a `pip install` for it, so a third-party import in a shipped script fails on the first
machine that lacks the package. The rule is as old as this repo's first CLAUDE.md (`85af744`, #2:
"All scripts are stdlib-only Python"). The one exception, the Playwright browser suite, is test-only
and opt-in; its case is under "Why the Playwright suite earns its exception" above.

### Releasing: the history behind the rules

The never-move-a-tag rule, the no-local-marketplace rule, and why a release is a five-file edit
are each told in [the release and distribution history](history.md).
