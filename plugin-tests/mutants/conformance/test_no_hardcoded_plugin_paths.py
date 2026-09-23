"""Mutation batch for test_no_hardcoded_plugin_paths.py.

The guard claims that no file in synced core can carry the literal install path
`.claude/plugins/cla` without a test going red — a defect invisible in this repo,
because here that path resolves, and fatal in every repo that installs the plugin
from a marketplace.

**Ten mutants, and the split between them is the point.** THREE mutate the INPUT
(mutants 1–2 and 10) and seven mutate the guard (3–9).

Mutant 10 is the input-side one for a different guard in the same file:
`test_the_recorded_counts_are_the_real_ones` reads this file's own comments, so
the recorded measurements ARE its input.

**Why two of them mutate the input rather than the guard.** The obvious mutant —
break `BAD` so it matches nothing — cannot be killed. In a correct tree there are
no offenders, so a `BAD` that matches nothing and a `BAD` that is right produce
the identical empty list; the two expressions agree on every input the real files
supply. That is `CLAUDE.md`'s named unkillable class, and its rule applies:
**where two candidate rules agree on all correct inputs, mutate the input.**
Mutants 1–2 do that, and they buy more than `BAD`'s correctness — each plants the
literal in a scan root that no assertion in the guard pins, so a kill proves that
root is genuinely reached.

Mutant 1 is the historical defect verbatim: `lib/log_run.py:7` documents its own
invocation, and reverting its `${CLAUDE_PLUGIN_ROOT}` to the hardcoded path is one
of the 92 occurrences across 31 files the guard's docstring says were found
immediately before the first consuming-repo test.

**THE ROOT-LIST WEAKNESS THIS BATCH USED TO REPORT IS NOW CLOSED (issue #246).**
`SCANNED_ROOTS` had five entries and only `agents/` was pinned by an assertion.
Dropping `lib` or `output-styles` left 101 or 102 files against a floor of
`>= 98`, every required suffix still reached, and the run green — so both sat in
the DELIBERATELY-NOT-A-MUTANT block below as known survivors. `REQUIRED_ROOTS`
and `test_every_required_root_is_actually_reached` are the fix, and mutants 7–8
are the two former survivors promoted to real mutants. Only `hooks` (14 files)
was ever large enough for the floor to notice, and that is mutant 5.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/conformance/test_no_hardcoded_plugin_paths.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"

GUARD = DEV / "tests" / "conformance" / "test_no_hardcoded_plugin_paths.py"
LOG_RUN = PLUGIN / "lib" / "log_run.py"
OUTPUT_STYLE = PLUGIN / "output-styles" / "CLA.md"

# Scoped to the ONE guard file: a target red for any other reason reports every
# mutant "killed" and proves nothing.
TARGETS = [GUARD]

# THREE MUTANTS ARE SCOPED FINER STILL, to a single test each, and the reason is
# the same argument one level down.
#
# `test_the_recorded_counts_are_the_real_ones` reads the printer's quoted output,
# so it fails on ANY mutant that moves a counted number — which is most of the
# interesting ones here. Measured, applying each mutant to a scratch copy and
# recording which tests go red:
#
#     mutant 3 (.mjs dropped)          scan_is_not_vacuous + recorded_counts
#     mutant 7 (output-styles dropped) required_root_is_reached + recorded_counts
#     mutant 8 (lib dropped)           required_root_is_reached + recorded_counts
#                                      + scan_is_not_vacuous
#
# A kill against the whole file therefore stopped saying WHICH assertion did the
# work — and for mutants 3 and 7 that assertion was the entire evidence that
# `REQUIRED_SUFFIXES` and `REQUIRED_ROOTS` have teeth. This is exactly the
# non-attributing kill the guard's own comment refuses to accept from the
# neighbouring batch, reintroduced here by a test added in the same PR.
#
# `mutate.py` takes a `::`-qualified node id, so the fix is to name the test each
# mutant is meant to prove. The kill then attributes again, and the comments
# below are true as written rather than true-as-of-when-they-were-written.
_SCAN_VACUITY = [f"{GUARD}::test_the_scan_is_not_vacuous"]
_ROOTS_REACHED = [f"{GUARD}::test_every_required_root_is_actually_reached"]

# Derived, not spelled. Only the recorded-count mutant spans lines, and it must:
# the printer's output is quoted TWICE in the guard, so the line alone is an
# ambiguous anchor and `mutate.py` refuses it. The surrounding prose is what
# makes it unique — and a bare `\n` there would match nothing on this CRLF
# checkout, aborting the whole batch in preflight.
_NL = "\r\n" if b"\r\n" in GUARD.read_bytes() else "\n"

MUTANTS = [
    (
        # THE HISTORICAL DEFECT, VERBATIM. `lib/log_run.py` documents how to
        # invoke itself; written with the literal path that command works only
        # in this repo and fails with "No such file or directory" wherever the
        # plugin is installed from the marketplace. Also proves `lib/` — one of
        # the two scan roots no assertion pins — is actually reached.
        "a lib/ script documents its own invocation with the hardcoded install path",
        LOG_RUN,
        "    python ${CLAUDE_PLUGIN_ROOT}/lib/log_run.py spec-to-pr-runs.jsonl < record.json",
        "    python .claude/plugins/cla/lib/log_run.py spec-to-pr-runs.jsonl < record.json",
        TARGETS,
    ),
    (
        # The other unpinned root. `output-styles/` holds exactly one file and
        # carries no `${CLAUDE_PLUGIN_ROOT}` reference to revert, so this plants
        # the literal instead — a synthetic probe, unlike mutant 1, and labelled
        # as one. What it establishes is the same: the scanner opens this root.
        "the output-style names the install path in its own heading",
        OUTPUT_STYLE,
        "# CLA output style",
        "# CLA output style (see .claude/plugins/cla/output-styles/CLA.md)",
        TARGETS,
    ),
    (
        # The near-miss the guard's own comment works through: `.mjs` is ONE
        # file, so dropping it lands on the floor rather than under it (102 - 1
        # = 101, floor >= 101) and the count cannot see it. Within
        # `test_the_scan_is_not_vacuous` the REQUIRED_SUFFIXES comparison is
        # therefore the ONLY assertion that can catch it, which is the whole
        # reason that second list exists as an independent source rather than
        # being derived from SCANNED_SUFFIXES.
        #
        # SCOPED TO THAT ONE TEST. Against the whole file this mutant also
        # fails `test_the_recorded_counts_are_the_real_ones` (scanned 101
        # against a recorded 102), and a kill that could have come from either
        # proves neither. The claim above is only true of a run scoped this
        # way, and it used to be written as though it were true of the batch.
        "a declared suffix is dropped from the scan without moving the file count below its floor",
        GUARD,
        'SCANNED_SUFFIXES = (".md", ".py", ".mjs", ".json")',
        'SCANNED_SUFFIXES = (".md", ".py", ".json")',
        _SCAN_VACUITY,
    ),
    (
        # The opposite direction, and the one the `missing` assertion cannot
        # see. Widening SCANNED_SUFFIXES without declaring the new suffix
        # REQUIRED reaches it, so nothing is missing and the run is green —
        # while the new suffix carries exactly the protection `.json` had before
        # REQUIRED_SUFFIXES existed, which is none. Spelled here as a narrowing
        # of REQUIRED rather than a widening of SCANNED because the two are the
        # same edit from either end and this one needs no file to exist.
        "a scanned suffix stops being declared required, so its removal would go unnoticed",
        GUARD,
        'REQUIRED_SUFFIXES = frozenset({".md", ".py", ".mjs", ".json"})',
        'REQUIRED_SUFFIXES = frozenset({".md", ".py", ".json"})',
        TARGETS,
    ),
    (
        # The root list narrowed. `hooks/` is 14 of 103 files, so this one IS
        # visible to the floor (89 < 102) — unlike `lib` and `output-styles`,
        # which are not, and which mutants 1-2 cover a different way.
        #
        # THE ASYMMETRY IS NO LONGER LEFT STANDING. This comment used to end
        # `the docstring says why that asymmetry is left standing rather than
        # hidden`, which stopped being true when `REQUIRED_ROOTS` closed it on
        # the axis the count cannot see. `lib` and `output-styles` are mutants
        # 7 and 8 now, and both die.
        "a scan root is dropped, taking every hook file out of the scan",
        GUARD,
        'SCANNED_ROOTS = ("skills", "agents", "output-styles", "hooks", "lib")',
        'SCANNED_ROOTS = ("skills", "agents", "output-styles", "lib")',
        TARGETS,
    ),
    (
        # RE-BREAKS A DEFECT THAT SHIPPED. `test_the_replacement_is_actually_in_
        # use` counted FILES carrying at least one reference, not references, and
        # its own docstring records the measurement: 51 files carry 235
        # occurrences, so a change deleting most of them while leaving one per
        # file held the old assertion green. This restores the file-count form;
        # 51 is far below the floor of 210, so it dies loudly.
        #
        # (This pair read 50/234 until a cross-branch comparison caught it —
        # the same drift the rest of this block is about, in the sentence that
        # quotes the guard's own record.)
        #
        # ANCHOR IS ONE LINE. `mutate.py` matches raw bytes and forbids `\n` in
        # an anchor — on a CRLF checkout a multi-line anchor matches nothing,
        # preflight refuses, and one bad anchor aborts the whole run. The
        # surrounding `sum(...)` and `for p in _scanned_files()` lines are
        # untouched; only the per-file expression changes.
        "the placeholder floor reverts to counting files rather than references",
        GUARD,
        '        p.read_text(encoding="utf-8", errors="replace").count("${CLAUDE_PLUGIN_ROOT}")',
        '        (1 if "${CLAUDE_PLUGIN_ROOT}" in p.read_text(encoding="utf-8", errors="replace") else 0)',
        TARGETS,
    ),

    # ---- 7-8: the two former survivors, promoted (issue #246) ----
    #
    # These are the exact edits the block at the bottom of this file used to
    # record as unkillable. `REQUIRED_ROOTS` is what kills them; the floor is
    # not, and mutant 7 is the one that shows it. Measured against the re-pinned
    # floor of `>= 101`:
    #
    #     drop `output-styles`  101 files  clears the floor exactly
    #     drop `lib`            100 files  fails the floor by one
    #
    # That asymmetry is an accident of today's file counts and is the argument
    # for the separate list: the floor's stated rule is to be lowered on every
    # deliberate deletion, and one lowering puts `lib` where `output-styles`
    # already is, while `REQUIRED_ROOTS` keeps failing either way.
    #
    # BOTH ARE SCOPED TO `test_every_required_root_is_actually_reached`, so each
    # kill attributes to `REQUIRED_ROOTS` and to nothing else. This paragraph
    # used to end "mutant 7 is killed by REQUIRED_ROOTS alone, and mutant 8
    # currently dies twice over" — measured against the whole file that is now
    # false in both halves: 7 dies twice (the root check and the recorded
    # counts) and 8 dies three times (those two plus the floor). The asymmetry
    # above is still real and still the argument; it is just no longer
    # something the batch DEMONSTRATES, so it is stated as a measurement rather
    # than implied by a kill.
    (
        "the one-file root is dropped from the scan, which no count can see",
        GUARD,
        'SCANNED_ROOTS = ("skills", "agents", "output-styles", "hooks", "lib")',
        'SCANNED_ROOTS = ("skills", "agents", "hooks", "lib")',
        _ROOTS_REACHED,
    ),
    (
        "the two-file root is dropped from the scan, taking lib/log_run.py and "
        "lib/ledger_summary.py out of it",
        GUARD,
        'SCANNED_ROOTS = ("skills", "agents", "output-styles", "hooks", "lib")',
        'SCANNED_ROOTS = ("skills", "agents", "output-styles", "hooks")',
        _ROOTS_REACHED,
    ),
    (
        # And the direction `REQUIRED_ROOTS` shares with `REQUIRED_SUFFIXES`: a
        # root ADDED to the scan without being declared required carries no
        # protection against being removed again. Spelled as a narrowing of
        # REQUIRED rather than a widening of SCANNED, for the reason mutant 4
        # gives — the two are the same edit from either end, and this one needs
        # no directory to exist.
        "a scanned root stops being declared required, so its removal would go unnoticed",
        GUARD,
        'REQUIRED_ROOTS = frozenset({"skills", "agents", "output-styles", "hooks", "lib"})',
        'REQUIRED_ROOTS = frozenset({"skills", "agents", "hooks", "lib"})',
        TARGETS,
    ),
    (
        # MUTATE THE INPUT, NOT THE GUARD. `test_the_recorded_counts_are_the_real_
        # ones` reads this file's own comments, so the PROSE is its input. A
        # recorded count that no longer matches the tree is exactly the decay it
        # exists to catch, and this repo has shipped that decay twice —
        # 95/96/99, then 98/99/103 — both times found by someone running the
        # printer for an unrelated reason rather than by a check.
        #
        # Reverting one quoted line to the pre-#246 figures is the historical
        # defect verbatim, the same way mutant 1 is for the hardcoded path. It is
        # the only mutant here that proves the RECORD is pinned rather than the
        # bound: every other one moves code, and the floors are deliberately
        # hand-pinned because a floor that re-derives itself asserts nothing.
        "a recorded measurement in the guard's own comments goes stale again",
        GUARD,
        "    #     scanned 102  .json 3  .md 69  .mjs 1  .py 29  placeholder-refs 233 in 53 files"
        + _NL
        + "    #" + _NL
        + "    # The real count is 102. Pinned near it, not",
        "    #     scanned 99  .json 3  .md 67  .mjs 1  .py 28  placeholder-refs 217 in 48 files"
        + _NL
        + "    #" + _NL
        + "    # The real count is 99. Pinned near it, not",
        TARGETS,
    ),
]

# DELIBERATELY NOT A MUTANT: breaking `BAD` so it matches nothing.
#
# It SURVIVES, and it cannot do otherwise. A correct tree has zero offenders, so
# a `BAD` that never matches and a `BAD` that is exactly right both produce an
# empty list — the two expressions agree on every input the live tree supplies.
# Mutants 1-2 are the input-side answer prescribed for that class: plant the
# literal and confirm the guard fires.
#
# NO LONGER A SURVIVOR: dropping `lib` or `output-styles` from SCANNED_ROOTS.
#
# Both DID survive, and the reason was arithmetic rather than anything about the
# guard's intent: `lib` is 2 files and `output-styles` is 1, against a floor that
# was `>= 98` with a real count of 103, and neither root holds the last file of
# any REQUIRED suffix. `REQUIRED_ROOTS` closes it on the axis the floor cannot,
# and the two edits are now mutants 7 and 8 rather than a paragraph.
#
# THE THREE FINDINGS THIS BLOCK USED TO REPORT ARE ALL FIXED, and the block is
# rewritten rather than deleted because what it got wrong is worth keeping.
#
# It reported two stale measurements and one false parenthetical in the guard,
# "left alone because correcting a guard is a different change from proving
# one". All three were corrected in the commit that re-pinned the floors. THE
# BLOCK ITSELF WAS NOT UPDATED WITH THEM, so a note whose whole subject is
# stale records sat here carrying stale records of its own — for three commits,
# until a comparison against another branch noticed.
#
# Where each one landed, re-derived rather than remembered:
#
#   * the scan floor's drift is fixed: `>= 102` against a real 103, a margin of
#     one, which is what that file's own rule asks for.
#   * `>= 210` was examined and deliberately NOT moved — its gap is the rule,
#     not drift. Only its recorded count was stale (217 against a real 235) and
#     that is now corrected.
#   * the `.json` parenthetical is true again, because the floor moved under
#     it. Re-run with the guard's own recorded experiment against `>= 102`:
#
#     drop  files  >=102?  missing-required
#    .json    100   False  ['.json']
#     .mjs    102    True  ['.mjs']
#      .py     73   False  ['.py']
#      .md     34   False  ['.md']
#     None    103    True  []
#
# The `.mjs` row is still the load-bearing one: it clears the floor exactly, so
# `REQUIRED_SUFFIXES` is the only thing that catches it. That is the argument
# the second list was added to make, and it does not depend on where the floor
# happens to sit.
#
# Since then the floor moved to `>= 101` against a real 102, when the
# commit-provenance hook was deleted from `hooks/`. The table above is shifted
# by one file throughout; its shape, and the `.mjs` row's role, are unchanged.
#
# THE RECORDS ABOVE ARE NOW CHECKED, not trusted. The guard carries
# `test_the_recorded_counts_are_the_real_ones`, which re-runs its printer and
# compares every quoted line against the tree. This block's numbers are still
# hand-written and still not covered by it — a batch is not a test — so they
# remain the kind of thing that decays. Re-derive them rather than trusting
# them; the commands are in the guard.
