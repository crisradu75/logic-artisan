"""Mutation batch for test_no_hardcoded_plugin_paths.py.

The guard claims that no file in synced core can carry the literal install path
`.claude/plugins/cla` without a test going red — a defect invisible in this repo,
because here that path resolves, and fatal in every repo that installs the plugin
from a marketplace.

**Eleven mutants, and the split between them is the point.** TWO mutate the INPUT
(mutants 1–2) and nine mutate the guard (3–11).

The old mutant 10 (a recorded printer line going stale) is gone with the test it
proved, `test_the_recorded_counts_are_the_real_ones`: the pinned scan floor and
the quoted printer lines were replaced by a comparison of the scan with
`git ls-files`, because every PR that added a shipped file had to edit them and
parallel PRs conflicted there. Mutants 10–11 now prove that comparison.

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
was ever large enough for the old count floor to notice, and that is mutant 5.

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

# SOME MUTANTS ARE SCOPED FINER STILL, to a single test each, so a kill says
# WHICH assertion did the work. Several tests in the guard react to the same
# narrowed scan (a dropped root fails both the root check and the tracked-file
# comparison), and a kill against the whole file would not say which one proved
# the mutant. `mutate.py` takes a `::`-qualified node id, so each such mutant
# names the test it is meant to prove.
_SCAN_VACUITY = [f"{GUARD}::test_the_scan_is_not_vacuous"]
_ROOTS_REACHED = [f"{GUARD}::test_every_required_root_is_actually_reached"]

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
        # A declared suffix dropped from the scan. This was the near-miss the
        # guard's comment works through while `.mjs` existed: ONE file, so
        # dropping it landed on the old count floor rather than under it and
        # only the REQUIRED_SUFFIXES comparison could catch it. Today the kill
        # comes from REQUIRED_SUFFIXES AND the tracked-file comparison (three
        # tracked `.json` files go unscanned), and attributes to neither alone;
        # mutant 10 isolates the comparison. The guard records the command that
        # shows the suffix assertion firing by itself (its `missing` column).
        #
        # SCOPED TO `test_the_scan_is_not_vacuous`.
        "a declared suffix is dropped from the scan",
        GUARD,
        'SCANNED_SUFFIXES = (".md", ".py", ".json")',
        'SCANNED_SUFFIXES = (".md", ".py")',
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
        'REQUIRED_SUFFIXES = frozenset({".md", ".py", ".json"})',
        'REQUIRED_SUFFIXES = frozenset({".md", ".py"})',
        TARGETS,
    ),
    (
        # The root list narrowed. `hooks/` was 13 of 102 files, so this one WAS
        # visible to the old count floor (89 < 101) — unlike `lib` and
        # `output-styles`, which were not, and which mutants 1-2 cover a
        # different way.
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
        # 69 files carry a reference today, far below the floor of 172, so it
        # dies loudly.
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
    # record as unkillable. `REQUIRED_ROOTS` is what kills them; the old count
    # floor was not, and both showed it. Measured against the floor of `>= 101` (since
    # slim-spec-to-pr, `>= 100` against a real 101: each drop leaves 100, still
    # exactly on the floor):
    #
    #     drop `output-styles`  101 files  clears the floor exactly
    #     drop `lib`            101 files  clears the floor exactly
    #
    # Against the earlier floor of `>= 102`, dropping `lib` (two files then)
    # failed it by one. This comment called that asymmetry an accident of the
    # file counts and predicted one lowering would put `lib` where
    # `output-styles` was; deleting `lib/ledger_summary.py` did exactly that,
    # and `REQUIRED_ROOTS` keeps failing either way.
    #
    # BOTH ARE SCOPED TO `test_every_required_root_is_actually_reached`, so each
    # kill attributes to `REQUIRED_ROOTS` and to nothing else. This paragraph
    # used to end "mutant 7 is killed by REQUIRED_ROOTS alone, and mutant 8
    # currently dies twice over". Against the whole file each now dies twice,
    # by the root check and by the tracked-file comparison that replaced the
    # floor; the scoping keeps the kill on `REQUIRED_ROOTS`.
    (
        "the one-file root is dropped from the scan, which no count can see",
        GUARD,
        'SCANNED_ROOTS = ("skills", "agents", "output-styles", "hooks", "lib")',
        'SCANNED_ROOTS = ("skills", "agents", "hooks", "lib")',
        _ROOTS_REACHED,
    ),
    (
        "the `lib` root is dropped from the scan, taking lib/log_run.py out of it",
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
        # THE TRACKED-FILE COMPARISON, ALONE. A pruning rule that skips every
        # `references/` folder narrows the scan by dozens of files while every
        # root and every suffix is still reached (`SKILL.md` keeps `.md` alive
        # in `skills/`), so REQUIRED_ROOTS and REQUIRED_SUFFIXES both pass. The
        # old count floor would have caught it; with the floor gone, the only
        # thing that can is the comparison with `git ls-files`.
        "the scanner stops opening references/ folders",
        GUARD,
        'if "__pycache__" in parts or ".pytest_cache" in parts:',
        'if "__pycache__" in parts or "references" in parts:',
        _SCAN_VACUITY,
    ),
    (
        # THE ENUMERATION'S OWN FLOOR. Filtering the `git ls-files` listing on a
        # set that holds no root name leaves the expected set empty, and an
        # empty set is contained in any scan: the comparison passes over
        # nothing. `_MIN_TRACKED_FILES` is what refuses that.
        "the independent enumeration matches nothing, so the comparison is vacuous",
        GUARD,
        "            Path(rel).parts[0] in REQUIRED_ROOTS",
        "            Path(rel).parts[0] in REQUIRED_SUFFIXES",
        _SCAN_VACUITY,
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
#   * the scan floor is gone: `test_the_scan_is_not_vacuous` compares the scan
#     with `git ls-files`, so no number moves when the plugin gains or loses a
#     file. `git log -p` on the guard has every step of the floor it replaced.
#   * `>= 172` is the placeholder floor; its gap to the real count is the rule,
#     not drift. The real count comes from the guard's printer, not from here.
#   * no suffix's loss is left to one assertion: dropping any declared suffix
#     fails `REQUIRED_SUFFIXES` and the tracked-file comparison together, so
#     mutant 3 attributes to neither alone.
#
# This block's numbers are hand-written and not covered by any test — a batch is
# not a test — so they remain the kind of thing that decays. Re-derive them
# rather than trusting them; the commands are in the guard.
