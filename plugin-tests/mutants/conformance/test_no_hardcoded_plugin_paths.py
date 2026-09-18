"""Mutation batch for test_no_hardcoded_plugin_paths.py.

The guard claims that no file in synced core can carry the literal install path
`.claude/plugins/cla` without a test going red — a defect invisible in this repo,
because here that path resolves, and fatal in every repo that installs the plugin
from a marketplace.

**Nine mutants, and the split between them is the point.** Two mutate the INPUT
(mutants 1–2) and seven mutate the guard (3–9).

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
        # file, so dropping it lands on the floor rather than under it (103 - 1
        # = 102, floor >= 98) and the count cannot see it. Only the
        # REQUIRED_SUFFIXES comparison catches this, which is the whole reason
        # that second list exists as an independent source rather than being
        # derived from SCANNED_SUFFIXES.
        "a declared suffix is dropped from the scan without moving the file count below its floor",
        GUARD,
        'SCANNED_SUFFIXES = (".md", ".py", ".mjs", ".json")',
        'SCANNED_SUFFIXES = (".md", ".py", ".json")',
        TARGETS,
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
        # visible to the floor (89 < 98) — unlike `lib` and `output-styles`,
        # which are not, and which mutants 1-2 cover a different way. The
        # docstring says why that asymmetry is left standing rather than hidden.
        "a scan root is dropped, taking every hook file out of the scan",
        GUARD,
        'SCANNED_ROOTS = ("skills", "agents", "output-styles", "hooks", "lib")',
        'SCANNED_ROOTS = ("skills", "agents", "output-styles", "lib")',
        TARGETS,
    ),
    (
        # RE-BREAKS A DEFECT THAT SHIPPED. `test_the_replacement_is_actually_in_
        # use` counted FILES carrying at least one reference, not references, and
        # its own docstring records the measurement: 50 files carry 234
        # occurrences, so a change deleting most of them while leaving one per
        # file held the old assertion green. This restores the file-count form;
        # 50 is far below the floor of 210, so it dies loudly.
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
    # not, and mutant 7 is the one that proves it. Measured against the re-pinned
    # floor of `>= 102`:
    #
    #     drop `output-styles`  102 files  clears the floor exactly
    #     drop `lib`            101 files  fails the floor by one
    #
    # So mutant 7 is killed by `REQUIRED_ROOTS` alone, and mutant 8 currently
    # dies twice over. That asymmetry is an accident of today's file counts and
    # the argument for the separate list: the floor's stated rule is to be
    # lowered on every deliberate deletion, and one lowering puts mutant 8 back
    # where mutant 7 is, while `REQUIRED_ROOTS` keeps failing either way.
    (
        "the one-file root is dropped from the scan, which no count can see",
        GUARD,
        'SCANNED_ROOTS = ("skills", "agents", "output-styles", "hooks", "lib")',
        'SCANNED_ROOTS = ("skills", "agents", "hooks", "lib")',
        TARGETS,
    ),
    (
        "the two-file root is dropped from the scan, taking lib/log_run.py and "
        "lib/ledger_summary.py out of it",
        GUARD,
        'SCANNED_ROOTS = ("skills", "agents", "output-styles", "hooks", "lib")',
        'SCANNED_ROOTS = ("skills", "agents", "output-styles", "hooks")',
        TARGETS,
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
# TWO STALE MEASUREMENTS IN THE GUARD, found while writing this batch and left
# alone because correcting a guard is a different change from proving one. They
# are NOT the same defect as each other, and an earlier version of this note
# conflated them:
#
#   * `test_the_scan_is_not_vacuous`'s floor is genuine drift. It asserts
#     `>= 98` under a comment citing a real count of 99, and the real count is
#     now 103. That file's own rule is that the floor sits NEAR its population —
#     its comment calls a four-file margin "precisely the decorative floor the
#     rule above forbids" — and the margin is five.
#   * `test_the_replacement_is_actually_in_use`'s floor is NOT drift. `>= 210`
#     against a real 234 is deliberate, and the same file says so at length: a
#     one-below margin would be noise for a count that moves whenever prose is
#     edited, so it is "a different rule from the scan floor's, deliberately".
#     What is stale there is only the RECORDED count in the comment — 217, now
#     234 — which is a stale measurement, not a decorative floor.
#
# AND ONE PARENTHETICAL IS NOW FALSE, downstream of the first. The guard says
# "Today the floor happens to catch a `.json` drop (99 - 3 = 96 < 98)". Re-run
# with the guard's own recorded experiment, it does not:
#
#     drop  files  >=98?  missing-required
#    .json    100   True  ['.json']
#     .mjs    102   True  ['.mjs']
#      .py     73  False  ['.py']
#      .md     34  False  ['.md']
#     None    103   True  []
#
# `REQUIRED_SUFFIXES` still catches a `.json` drop, so nothing escapes — which
# is precisely the argument that list was added to make, now demonstrated by the
# floor failing to do the job the parenthetical credits it with.
