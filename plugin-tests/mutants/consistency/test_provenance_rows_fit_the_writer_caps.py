"""Mutation batch for test_provenance_rows_fit_the_writer_caps.py.

The guard claims no row in the provenance ledger exceeds a cap the writer
enforces, that a wrong-shaped field is reported rather than raised on, and that
the dedupe's tail window holds one maximal row as stored on disk.

**NO MUTANT HERE TOUCHES THE LEDGER OR THE HOOK, and both exclusions were
learned rather than designed.** Two rounds of this batch got it wrong in the same
way, one level apart.

The first round mutated `cla.io/retro/commit-provenance.jsonl` to plant cap
violations — the textbook answer when a guard's two candidate rules agree on
every correct input. It is the wrong answer when the input is a LIVE file the
harness writes to: `log-commit-provenance.py` appends a row on every commit, and
`mutate.py` snapshots the file, runs each round, then restores the snapshot — so
a commit landing mid-run has its row erased, and the post-restore integrity check
compares against that same snapshot and reports success.

The second round moved those mutants to the HOOK's own constants
(`_MAX_LINE_BYTES` and the dedupe window literal) and repeated the mistake from
the other end. This repo loads the plugin from the working tree via
`--plugin-dir`, so that hook is the one running on every `git commit`: with the
cap raised, a commit during the round writes an over-cap row; with the window
shrunk below a real row, the hook fails its own dedupe read and records the
commit twice. `mutate.py` restores the hook — it cannot restore the row.

**The fix both times was a seam.** `_cap_violations` and `_rows` take their input
as an argument, `_dedupe_window_bytes` takes source text, and `_window_shortfall`
takes all three numbers. Every mutant below therefore breaks the GUARD and is
killed by a test feeding it synthetic values. The general rule, now paid for
twice: when mutating the input is unsafe, give the checker a seam and mutate
through it — and check what the "input" really is, because a constant inside a
live hook is one.

**Eight mutants.** Three break a cap comparison, one breaks the shape guard, two
break the window arithmetic, one breaks the extractor's liveness, one breaks the
non-vacuity partner. Each is scoped to ONE test, so a kill attributes to the
branch it aims at rather than to "something in this file".

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_provenance_rows_fit_the_writer_caps.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]

GUARD = DEV / "tests" / "consistency" / "test_provenance_rows_fit_the_writer_caps.py"

_CAPS = [f"{GUARD}::test_each_cap_is_actually_checked"]
_SHAPE = [f"{GUARD}::test_a_wrong_shaped_field_is_reported_rather_than_raised_on"]
_CRLF = [f"{GUARD}::test_the_window_check_accounts_for_a_crlf_checkout"]
_LIVE = [f"{GUARD}::test_the_window_is_read_out_of_the_hook_rather_than_assumed"]
_VACUITY = [f"{GUARD}::test_the_ledger_is_there_and_has_rows_to_check"]

MUTANTS = [
    (
        # THE VALUE-COUNT BRANCH STOPS DISCRIMINATING. `> maxt` to `> maxt * 2`
        # rather than to something obviously dead, because a doubled bound is
        # what a careless "the cap moved" edit looks like and still passes every
        # real row.
        "the value-count check accepts twice _MAX_TRAILERS",
        GUARD,
        "        if len(values) > maxt:",
        "        if len(values) > maxt * 2:",
        _CAPS,
    ),
    (
        # THE PER-VALUE BRANCH. This is the backfill's actual defect: the raw
        # extraction stored without `[v[:_MAX_TRAILER_CHARS] for v in ...]` left
        # 49 values past the cap, the longest 397 — comfortably inside a doubled
        # bound, so this mutant is the real escape rather than a synthetic one.
        "the per-value check accepts twice _MAX_TRAILER_CHARS",
        GUARD,
        "        long = [v for v in values if len(v) > maxc]",
        "        long = [v for v in values if len(v) > maxc * 2]",
        _CAPS,
    ),
    (
        # THE LINE-LENGTH BRANCH. Note what this one is and is not: exceeding
        # `_MAX_LINE_BYTES` means the row skipped the shedding loop, which is a
        # cap violation. It does NOT by itself break the dedupe — that needs a
        # row past the WINDOW, at the end of the file. The cap is what keeps the
        # window's assumption out of reach, and this branch defends it.
        "the line-length check accepts twice _MAX_LINE_BYTES",
        GUARD,
        "        if nbytes > maxb:",
        "        if nbytes > maxb * 2:",
        _CAPS,
    ),
    (
        # THE SHAPE GUARD REMOVED. Without it `len(values)` on a `null` or a
        # number is a bare `TypeError` naming neither file nor line — the exact
        # failure `_rows()` takes care to avoid one layer down, reintroduced one
        # layer up. The mutant keeps the code running for well-formed rows, which
        # is why only a wrong-shaped row can catch it.
        "the wrong-shaped-field guard is dropped",
        GUARD,
        "        if not isinstance(values, list):",
        "        if False:",
        _SHAPE,
    ),
    (
        # THE CRLF BYTE DROPPED — finding 2's defect exactly. Assuming the
        # terminator the cap budgeted rather than the one the checkout stores
        # makes a window EQUAL to the cap look sufficient, which blesses a
        # `_MAX_LINE_BYTES` of 4096 against the 4096 window. Every row on a
        # Windows clone is then one byte longer than the arithmetic believes, the
        # last one does not fit, and the dedupe double-records with this guard
        # green.
        "the window arithmetic assumes the terminator the cap budgeted",
        GUARD,
        "    return (max_line - 1 + terminator_bytes) - window",
        "    return max_line - window",
        _CRLF,
    ),
    (
        # THE SAME ARITHMETIC OFF BY ONE IN THE OTHER DIRECTION, which is the
        # partner that stops the mutant above being killed by a sign rather than
        # by the byte. A window one short of a maximal row must report 1, not 0.
        "the window arithmetic is one byte too generous",
        GUARD,
        "    return (max_line - 1 + terminator_bytes) - window",
        "    return (max_line - 2 + terminator_bytes) - window",
        _CRLF,
    ),
    (
        # THE EXTRACTOR STOPS READING ITS INPUT. Returning the value the real
        # hook happens to carry passes the live check identically — this is the
        # property the two withdrawn hook-mutating mutants used to prove, moved
        # to the seam so proving it costs nothing on disk.
        "the window extractor returns a constant instead of parsing",
        GUARD,
        "    tree = ast.parse(source)",
        "    return 4096\n    tree = ast.parse(source)",
        _LIVE,
    ),
    (
        # NON-VACUITY. `_rows()` feeds the real-file cap check, so a reader that
        # yields nothing leaves it iterating an empty list and passing. This is
        # killable precisely because the non-vacuity test does not iterate — it
        # asserts the population is there.
        "the guard's row reader silently yields nothing",
        GUARD,
        "        if not body.strip():",
        "        if True:",
        _VACUITY,
    ),
]
