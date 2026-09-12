"""Mutation batch for test_no_hardcoded_plugin_paths.py.

The guard claims that no file in synced core can carry the literal install path
`.claude/plugins/cla` without a test going red — a defect invisible in this repo,
because here that path resolves, and fatal in every repo that installs the plugin
from a marketplace.

**Ten mutants, and the split between them is the point.** Three mutate the INPUT
(mutants 1–2 and 9) and seven mutate the guard.

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

**A weakness this batch did NOT paper over, and which is now fixed.**
`SCANNED_ROOTS` had five entries with only `agents/` pinned by an assertion.
Dropping `lib` or `output-styles` left 101 or 102 files against a floor of `>= 98`,
every required suffix still reached, and the run green — measured, see the report
on issue #176. This batch stated that rather than hiding it, and issue #246 acted
on the statement: `REQUIRED_ROOTS` now names each root independently and the root
assertion runs before the floor, so a dropped root reports itself by name.
Mutants 6–8 are that fix, and the distinction the old note drew still holds —
mutants 1–2 prove those roots are scanned TODAY, which is a different claim from
"a narrowing of the root list would be caught", and both claims now have a mutant.

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

# Derived from the GUARD's own bytes rather than spelled. `mutate.py` matches raw
# bytes, so on this CRLF checkout a `\n` in an anchor matches nothing — preflight
# refuses it here, but the same mistake in an ad-hoc script is a silent no-op that
# reports SURVIVED without running the mutation. Spelling `\r\n` outright would
# work here and pin the batch to Windows.
#
# Only the recorded-count mutant spans lines, and it must: the printer's output is
# quoted TWICE in the guard (once beside each floor), so a single-line anchor on it
# is ambiguous and preflight rejects it. The following two lines disambiguate.
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
        # file, so dropping it lands on the floor rather than under it (103 - 1
        # = 102, floor >= 102) and the count cannot see it. Only the
        # REQUIRED_SUFFIXES comparison catches this, which is the whole reason
        # that second list exists as an independent source rather than being
        # derived from SCANNED_SUFFIXES. The margin moved with issue #246 and
        # the near-miss survived it — at 98 the drop cleared by four, at 102 it
        # clears by nothing at all, and either way the count says green.
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
        # The root list narrowed. Before issue #246 this one was caught only by
        # the file count (89 < 98) while `lib` and `output-styles` were caught by
        # nothing; `REQUIRED_ROOTS` now catches all three by name, and the root
        # assertion runs BEFORE the floor so the failure says which root went
        # missing rather than "scan set collapsed".
        "a scan root is dropped, taking every hook file out of the scan",
        GUARD,
        'SCANNED_ROOTS = ("skills", "agents", "output-styles", "hooks", "lib")',
        'SCANNED_ROOTS = ("skills", "agents", "output-styles", "lib")',
        TARGETS,
    ),
    (
        # ISSUE #246, CASE ONE. This SURVIVED before `REQUIRED_ROOTS` existed:
        # `lib/` is 2 files of 103, so the count lands at 101 — above the old
        # floor of 98 — and `lib` holds the last file of no required suffix.
        # `lib/` is where `log_run.py` and `ledger_summary.py` live, so a
        # hardcoded install path there went unreported.
        #
        # Distinct from mutant 1, which plants a path IN `lib/` to prove the root
        # is opened. This removes the root from the declaration instead. Content
        # and structure are two different ways to lose a root and want two checks.
        "the lib/ root is dropped from the scan without moving the count below its floor",
        GUARD,
        'SCANNED_ROOTS = ("skills", "agents", "output-styles", "hooks", "lib")',
        'SCANNED_ROOTS = ("skills", "agents", "output-styles", "hooks")',
        TARGETS,
    ),
    (
        # ISSUE #246, CASE TWO, and the sharpest of the three. `output-styles/`
        # is ONE file, so dropping it leaves 102 — which clears even the raised
        # floor of 102 exactly, the same near-miss shape as the `.mjs` suffix in
        # mutant 3. No count can ever see this root leave; only the named list
        # can. It ships to every consuming repo.
        "the output-styles/ root is dropped, and no file count can see it",
        GUARD,
        'SCANNED_ROOTS = ("skills", "agents", "output-styles", "hooks", "lib")',
        'SCANNED_ROOTS = ("skills", "agents", "hooks", "lib")',
        TARGETS,
    ),
    (
        # The opposite direction for roots, mirroring mutant 4 for suffixes. A
        # root added to SCANNED_ROOTS but not declared REQUIRED is reached, so
        # `unreached` is empty and the run is green — while the new root carries
        # none of the protection. Spelled as a narrowing of REQUIRED because the
        # two are the same edit from either end and this one needs no directory
        # to exist.
        "a scanned root stops being declared required, so its removal would go unnoticed",
        GUARD,
        'REQUIRED_ROOTS = frozenset({"skills", "agents", "output-styles", "hooks", "lib"})',
        'REQUIRED_ROOTS = frozenset({"skills", "agents", "hooks", "lib"})',
        TARGETS,
    ),
    (
        # MUTATE THE INPUT, NOT THE GUARD. `test_the_recorded_counts_are_the_real_
        # ones` reads this file's own comments, so the prose IS its input. A
        # recorded count that no longer matches the tree is exactly the decay it
        # exists to catch, and this repo has shipped that decay twice (95/96/99,
        # then 98/99/103) — both times found by someone running the printer for
        # an unrelated reason.
        #
        # Reverting one quoted line to the pre-#246 figures is the historical
        # defect verbatim, the same way mutant 1 is for the hardcoded path.
        "a recorded measurement in the guard's own comments goes stale again",
        GUARD,
        "    #     scanned 103  .json 3  .md 69  .mjs 1  .py 30  placeholder-refs 234 in 50 files"
        + _NL
        + "    #" + _NL
        + "    # The real count is 103.",
        "    #     scanned 99  .json 3  .md 67  .mjs 1  .py 28  placeholder-refs 217 in 48 files"
        + _NL
        + "    #" + _NL
        + "    # The real count is 99.",
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
]

# DELIBERATELY NOT A MUTANT: breaking `BAD` so it matches nothing.
#
# It SURVIVES, and it cannot do otherwise. A correct tree has zero offenders, so
# a `BAD` that never matches and a `BAD` that is exactly right both produce an
# empty list — the two expressions agree on every input the live tree supplies.
# Mutants 1-2 are the input-side answer prescribed for that class: plant the
# literal and confirm the guard fires.
#
# WAS "DELIBERATELY NOT A MUTANT", NOW MUTANTS 6 AND 7: dropping `lib` or
# `output-styles` from SCANNED_ROOTS.
#
# Both survived when this note was written, and the note said so rather than
# hiding the gap behind a mutant that would sit in the survivor column forever.
# Issue #246 acted on that report: `REQUIRED_ROOTS` now names every root
# independently, so both die. The note is kept in this form because the sequence
# is the point — a batch reporting an unkillable mutant as a finding is what
# turned the gap into a fix.
#
# THE THREE STALE MEASUREMENTS this batch reported are fixed by the same issue,
# and the distinction it drew between them survives into the guard:
#
#   * `test_the_scan_is_not_vacuous`'s floor WAS genuine drift — `>= 98` under a
#     comment citing 99 against a real 103. Now `>= 102` under a comment citing
#     103, back to the one-below margin that file's own rule prescribes.
#   * `test_the_replacement_is_actually_in_use`'s floor was NOT drift. `>= 210`
#     against a real 234 is deliberate and the guard argues for it at length, so
#     210 did not move. Only its RECORDED count was stale (217, now 234).
#   * The `.json` parenthetical was false and is now true again — at a floor of
#     102, dropping `.json` leaves 100 and trips it. Still arithmetic rather than
#     a guarantee, and the guard now says so, naming the window in which it was
#     false rather than just asserting the current figure.
#
# Mutant 8 is what stops all three going stale again: it reverts one recorded
# printer line to the pre-#246 figures, and
# `test_the_recorded_counts_are_the_real_ones` re-derives every field. The floors
# stay hand-pinned — a floor that re-derives itself asserts nothing — while the
# record beside them cannot drift unnoticed.
#
# DELIBERATELY NOT A MUTANT: reverting the scan floor from `>= 102` to `>= 98`.
#
# It survives, and it cannot do otherwise: the real count is 103, so both forms
# pass on a correct tree. The two expressions agree on every input the live tree
# supplies — the same class as `BAD` above. The input-side answer is mutant 8,
# which moves the RECORDED count instead and does discriminate.
