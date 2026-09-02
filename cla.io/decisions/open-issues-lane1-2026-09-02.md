# Decision: three ready-to-edit open issues, one PR each

Built 2026-09-02 from `gh issue list --state open` (9 issues) on `main` at `b1bcd93`, after the
`fix-brief-binding-defect` line closed (PRs #154/#155/#156) and `cla--v1.0.0` was cut.

Of the nine open issues, **three are knowable from the issue text alone** — the change is decided,
only the edit remains. Those three are this document. The other six are listed under
"Out of scope" with the reason each one is not here; three of those want `/cla:shape-decision`
first, and three leave the `lite-pr` path entirely.

The repo has no priority labels — the label set is GitHub's stock nine. "Ready" here means
*decision-complete*, not *most important*.

**Measured-by** (all run 2026-09-02 from the repo root, on `b1bcd93`):

```
gh issue list --state open --limit 100                                    → 9
gh label list                                                             → 9 stock labels, no priority label

grep -n '^#' .claude/plugins/cla/skills/_shared/references/test-quality.md
      → :160 "Prove a gate by planting what it is supposed to catch", :179 "How planting goes wrong",
        :246 "N rules × M constructs", :295 "Why these and not a longer list"
grep -rn 'confirm it FAILS' .claude/plugins/cla/skills/spec-to-pr/
      → references/revise.md:186 only — NOT SKILL.md
grep -n 'mutat' .claude/plugins/cla/skills/spec-to-pr/SKILL.md
      → :269, :271 — the ticked-task/measurement rule, not a mutation gate
grep -n 'references resolve' plugin-tests/tests/conformance/test_skill_lint.py
      → :1 — the SKILL.md frontmatter/reference-graph guard is in conformance, not consistency
grep -n 'revise.md' plugin-tests/tests/consistency/test_measurement_names_its_command.py
      → :169, inside _FAMILY — so A's edited revise.md is read by name in consistency as well

grep -n '^| ' .claude/plugins/cla/README.md                                → phase table at :47-71, 3 columns
ls .claude/plugins/cla/skills/*/SKILL.md | wc -l                          → 20
grep -l '^disable-model-invocation: true' .claude/plugins/cla/skills/*/SKILL.md
      → 2 files: multi-lite, multi-pr
grep -rn '^disable-model-invocation' .claude/plugins/cla/skills/
      → the same 2 lines and no others, so no third skill sets the key to any value
grep -n 'SCANNED_ROOTS =' plugin-tests/tests/conformance/test_no_hardcoded_plugin_paths.py
      → :38 — ("skills", "agents", "output-styles", "hooks", "lib"); the plugin ROOT is not a root
grep -n '"README.md"' plugin-tests/tests/conformance/test_shipped_files_are_scanned.py
      → :85, inside EXEMPT — the map of shipped files NO scanner opens
grep -rn 'README' plugin-tests/tests/conformance/ | grep -v test_shipped_files_are_scanned
      → no hits: no conformance test other than the exemption map itself opens the plugin README
grep -n '\.claude/plugins/cla' .claude/plugins/cla/README.md
      → :183 only — the Layout block, which is why widening the path scanner to the root would fail

grep -on '0[a-z][).]' .claude/plugins/cla/skills/review-change/references/checklist.md | tail
      → checklist defines 0a-0l; :56 is 0l, the highest
grep -n '0m' .claude/plugins/cla/skills/multi-spec/references/review-gate.md    → :22, :42
grep -rn 'enumerates-checks' .claude/plugins/cla/                              → 5 marked lines (2 review-gate, 3 checklist)
grep -n '_ENUMERATING_FILES\|_ENUMERATION_MARKER' plugin-tests/tests/consistency/test_check_labels_agree.py
      → :78 hand list of 4 files, :241 the marker constant — the guard knows the marker, the file list does not use it
grep -c 'enumerates-checks' plugin-tests/mutants/consistency/test_check_labels_agree.py  → 2
```

## Sequencing

**No dependency edges.** The three candidates touch disjoint files, so nothing must merge before
anything else. `multi-lite` should open three PRs and leave all three open for review.

| item | issue | files it edits |
|---|---|---|
| A | #193 | `.claude/plugins/cla/skills/_shared/references/test-quality.md`, `.claude/plugins/cla/skills/spec-to-pr/references/revise.md` |
| B | #180 | `.claude/plugins/cla/README.md` |
| C | #177 | `plugin-tests/tests/consistency/test_check_labels_agree.py`, `plugin-tests/mutants/consistency/test_check_labels_agree.py`, `.claude/plugins/cla/skills/multi-spec/references/review-gate.md` |

Run order A → B → C. C is last because it is the only one that touches a guard with a live mutant
batch, and its run needs `mutate.py` serialized against its own review agents (see C's constraint).

---

## A — #193: a killed mutant is not automatically a pass

**Decided.** The replacement paragraph is drafted verbatim in the issue and is adopted as written.

**What to do.** Add the paragraph to `_shared/references/test-quality.md`, near the planting rules
at `:160`–`:245`, and mirror the point at `spec-to-pr/references/revise.md:186`.

**Fact correction to carry into the run.** The issue says the mirror belongs in
`spec-to-pr/SKILL.md`'s Revise mutation-gate bullet. It does not — `grep -rn 'confirm it FAILS'`
returns `references/revise.md:186` and nothing in `SKILL.md`. `SKILL.md`'s only mutation mentions
(`:269`, `:271`) are the ticked-task measurement rule, a different subject. **Edit `revise.md`, not
`SKILL.md`.** The defect the issue reports survives this correction; only the location was wrong.

**The substance.** Both sites frame the gate as *break the code, confirm a test fails, restore*, and
treat a killed mutant as evidence the test is real. Necessary, not sufficient: a test written from a
wrong mental model kills mutants exactly as reliably as a correct one, and the green result reads as
confirmation. The consumer-repo case is in the issue — a conditional column offset whose killing
assertion *was* the defect.

**Out of scope.** Do not restate the SURVIVED-mutant rule; CLAUDE.md and `test-quality.md` already
cover that direction, and this is the opposite one.

**Acceptance.** `pytest plugin-tests/tests/conformance` green — the `SKILL.md` frontmatter and
reference-graph guard is `conformance/test_skill_lint.py`, so a `references/` link this edit adds
or renames that resolves to nothing fails there. Run `plugin-tests/tests/consistency` as well, for
a different reason: `consistency/test_measurement_names_its_command.py` lists
`spec-to-pr/references/revise.md` in its `_FAMILY` literal, so one of this candidate's two edited
files is read there by name. No new claim in the added prose asserts a count or a measurement.

---

## B — #180: label each skill's invocation model in the phase table

**Decided.** Adopt the label as documentation only. **Reject** the rule that arrived with it —
"user-invoked skills never call each other" — and record the rejection in the same edit so it does
not arrive a fourth time. CLA's orchestrators violate it deliberately: `spec-to-pr` chains
`review-change`, `multi-pr` drives `change-loop`, and that composition is the design.

**What to do.** Add a column to the phase table at `README.md:47`–`71`.

**The data is derivable, not a judgement call.** A skill is user-invoked-only exactly when its
`SKILL.md` frontmatter sets `disable-model-invocation: true`. Measured today: of 20 skills carrying
a `SKILL.md`, **two** set it — `multi-lite` and `multi-pr`. Both are unattended orchestrators that
open and merge PRs, which is the stated reason in each file's frontmatter comment. Every other
shipped skill is model-invocable.

**Out of scope.** Do not change any skill's frontmatter — this item documents the current state, it
does not re-decide it. Do not add the column to CLAUDE.md's own tables.

**Acceptance.** Every row in the table carries the new column. The two `true` skills are the only
two marked user-invoked.

**No conformance scanner reads the file this candidate edits, so a green `conformance` run is not
evidence about the column.** The plugin `README.md` sits at the plugin root, outside all five
`SCANNED_ROOTS` of `test_no_hardcoded_plugin_paths.py` (`skills`, `agents`, `output-styles`,
`hooks`, `lib`), and `test_shipped_files_are_scanned.py` lists `README.md` in `EXEMPT` — the map of
shipped files NO scanner opens — for two stated reasons: its install commands legitimately name
this repository, and its Layout block spells the literal `.claude/plugins/cla` at `README.md:183`,
which would fail the hardcoded-path rule outright. That is the same fact the `#190` entry below
records, reached from the other side.

**So the run must bring the guard with it.** A derived value copied into prose is what
`consistency/test_doc_facts.py` already exists to bind — it is the guard over the numbers
`CLAUDE.md`, `DEVELOPER-GUIDE.md` and the plugin `README.md` restate. Acceptance is that the column
is tied back there, comparing the marked set against the frontmatter set as a SET rather than a
count: a count agrees whenever the right number of rows are marked, including when the marks sit on
the wrong skills.

---

## C — #177: end the `0[a-z]` collision class, and let the guard discover marked lines

Two residues around one guard. One issue, one PR, because they are the same guard and one commit.

### C1 — move the batch-only check out of the `0[a-z]` namespace

**Decided.** Adopt the prefix the issue proposes. `review-gate.md`'s batch-only check moves from
`0m` to a prefix outside the namespace the guard scans (`B1` is the issue's candidate and is
adopted unless the run finds it already taken).

**Why now.** Measured today: `checklist.md` defines `0a`–`0l`, with `0l` live at `:56`. **`0m` is
the next label the checklist reaches**, and it is already taken by `review-gate.md:22`. The
`0j` → `0m` relabel deferred this collision by exactly three labels; a prefix outside `0[a-z]`
closes the class permanently.

**Trap, measured.** `plugin-tests/mutants/consistency/test_check_labels_agree.py` quotes
`review-gate.md`'s prose literally at two lines (`grep -c 'enumerates-checks'` → 2, one of them the
`0m` line's trailing text). **Renaming the label breaks that batch.** Update the batch in the same
commit; do not discover it after the fact.

### C2 — the guard discovers enumerating files instead of being handed a list

**Decided.** Have the guard find marked lines rather than read a hand-maintained file list.

**The mechanism already half-exists.** `_ENUMERATION_MARKER` is defined at
`test_check_labels_agree.py:241`, and `<!-- enumerates-checks -->` marks 5 lines across 2 files
today. But `_ENUMERATING_FILES` at `:78` is a hand list of 4 paths, and nothing detects a fifth
enumerating file appearing. Close it by scanning the plugin tree for the marker instead.

**Keep the deliberate exemption.** `agents/fact-gatherer.md` names a range in its frontmatter and is
unwatched on purpose. Discovery must not silently start policing it — carry the exemption forward
explicitly, with its reason, the way `_EXEMPT` does elsewhere.

**Constraint on the run — read before starting C.** `consistency` is a fully adopted mutant area, so
this guard's batch must stay green, which means running
`python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_check_labels_agree.py`.
CLAUDE.md forbids running `mutate.py` while a review agent reads the same tree — a batch rewrites
real files in place, and an agent reading mid-run sees a mutated file with a clean `git status`.
**Run the batch before dispatching this candidate's review agents, or after they return. Never
overlapping.**

**Out of scope.** Do not write batches for the seven grandfathered guards — that is #176, and it is
not in this document.

**Acceptance.** `pytest plugin-tests/tests/consistency` green. The mutant batch runs with zero
survivors, serialized as above. `grep -rn '0m' .claude/plugins/cla/` returns no batch-only check.
A sixth marked line added anywhere under the plugin is caught by the guard without editing a list.

---

## Out of scope — the other six open issues, and why

**Want `/cla:shape-decision` before any implementation:**

- **#190** — the issue *is* the decision: which of four unscanned shipped file groups to start
  scanning. Real cost side, so it is not a chore: `check_no_project_tokens.py` ships, and widening
  it changes behaviour in every consuming repo on a guard whose failure mode is a hard exit.
  The issue's own measured trap: the plugin `README.md` contains `.claude/plugins/cla` at `:183`, so
  widening the hardcoded-path scanner to the plugin root fails immediately unless README is exempted
  there first.
- **#175** — three open questions unanswered: where to enforce (authoring, review, both), what scope
  (all `tasks.md`, or only batch chains), and how much of the three-part discipline.
- **#176** — seven grandfathered guards. The issue states which one is next is "a judgement call
  rather than a documented one." Also unsuited to an unattended chain, for C's `mutate.py` reason
  multiplied by seven.

**Leave the `lite-pr` path entirely:**

- **#174** — blocked on run data `logic-artisan` will never produce. It holds no product code, so it
  accumulates no `multi-*`/`project-review` runs. The measurement has to be gathered in a consuming
  repo first.
- **#179** — check the live vendored `openspec-propose` SKILL.md, then either file upstream on
  someone else's repo or close. No PR here either way, and filing externally needs authorization.
- **#173** — a whole new skill plus two hooks. The issue names its own route: `/cla:spec-to-pr`.

## Noise found while measuring, not a candidate

`.claude/plugins/cla/skills/update-cla/` still exists on disk as three empty directories
(`.pytest_cache/`, `scripts/`, `tests/`) left over from the deleted skill. `git ls-files` returns
nothing for that path — it is untracked, so it needs no PR. Delete it locally; do not route it
through this batch.
