"""Mutation batch for test_provenance_rows_fit_the_writer_caps.py.

The guard claims no row in the provenance ledger can violate the three caps
`main()` applies before writing — and that the dedupe's tail window still clears
a maximal row — without a test going red.

**Six mutants, and the split follows CLAUDE.md's rule about unkillable mutants.**
Three mutate the INPUT (the ledger), two mutate the HOOK's constants, one mutates
the guard.

Why the cap checks are mutated from the INPUT side. Breaking the guard's own
comparison — `> mod._MAX_TRAILERS` to `>= 0`, say — cannot be killed: in a
correct tree no row violates any cap, so a comparison that is right and one that
is merely satisfied produce the identical empty `offenders` list. That is the
named unkillable class, and its rule is to mutate the input instead. Each of
mutants 1-3 plants exactly ONE violation and leaves the other two caps satisfied,
so a kill attributes to the branch it is aimed at rather than to "something in
that function".

Mutants 4-5 are the two halves of the same ratio, from opposite sides. The
window test compares a literal inside `_already_recorded_fh` against
`_MAX_LINE_BYTES`, and it reads BOTH live. A batch that moved only one of them
would leave the other a number the guard could have hardcoded.

Mutant 6 is the non-vacuity partner. Every other assertion here iterates the
ledger, so a `_rows()` that yields nothing turns the whole module green while
checking nothing — the exact shape `test_the_ledger_is_there_and_has_rows_to_check`
exists to catch, and the only one of the six aimed at the guard's own plumbing.

EVERY MUTANT IS SCOPED TO ONE TEST. Mutant 3 also reds
`test_the_longest_row_on_disk_is_reported_against_both_bounds`, and a kill that
could have come from either proves neither.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_provenance_rows_fit_the_writer_caps.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"

GUARD = DEV / "tests" / "consistency" / "test_provenance_rows_fit_the_writer_caps.py"
HOOK = PLUGIN / "hooks" / "log-commit-provenance.py"
LEDGER = DEV.parent / "cla.io" / "retro" / "commit-provenance.jsonl"

_CAPS = [f"{GUARD}::test_no_row_exceeds_the_caps_the_writer_enforces"]
_WINDOW = [f"{GUARD}::test_the_dedupe_window_still_clears_a_maximal_row"]
_VACUITY = [f"{GUARD}::test_the_ledger_is_there_and_has_rows_to_check"]

# One real row, by its `measured_by` field, which is unique in the file. Short
# and ASCII, so each mutant below changes exactly the property it names.
_ROW = (
    ', "measured_by": ["pytest plugin-tests/tests/conformance -q -n auto '
    '--dist loadfile -> 145 passed"]}'
)


def _field(values: list[str]) -> str:
    import json
    return ', "measured_by": ' + json.dumps(values, ensure_ascii=False) + "}"


MUTANTS = [
    (
        # ELEVEN VALUES. `_MAX_TRAILERS` is 10, so the writer could not have
        # produced this row however long the commit message was. Values are one
        # character each: the char cap and the byte cap stay satisfied, so only
        # the count branch can fire.
        "a ledger row carries more trailer values than _MAX_TRAILERS allows",
        LEDGER,
        _ROW,
        _field([chr(ord("a") + i) for i in range(11)]),
        _CAPS,
    ),
    (
        # ONE VALUE OF 161 CHARACTERS, one past `_MAX_TRAILER_CHARS`. This is the
        # hand-edit defect in its smallest form: the raw extraction stored
        # without `[v[:_MAX_TRAILER_CHARS] for v in ...]`. One value, and 161
        # ASCII bytes is nowhere near the line ceiling, so only the char branch
        # can fire.
        "a ledger row carries a trailer value past _MAX_TRAILER_CHARS",
        LEDGER,
        _ROW,
        _field(["x" * 161]),
        _CAPS,
    ),
    (
        # A LINE PAST `_MAX_LINE_BYTES` WITH BOTH OTHER CAPS RESPECTED — four
        # values, each exactly 160 CHARACTERS, each 480 BYTES because an em dash
        # is three. This is precisely what the shedding loop exists for, so a row
        # like this is one that skipped it, and it is the only one of the three
        # that can break the dedupe: past 4096 bytes at the tail,
        # `_already_recorded_fh` fails to parse the last line, reads "not
        # recorded", and the hook appends a duplicate.
        "a ledger row exceeds _MAX_LINE_BYTES although every value is within its own cap",
        LEDGER,
        _ROW,
        _field(["—" * 160] * 4),
        _CAPS,
    ),
    (
        # THE RATIO FROM THE ROW SIDE. A doubled `_MAX_LINE_BYTES` makes a
        # maximal row exactly the size of the dedupe's whole read window, so the
        # partial line above it can no longer be skipped past — the margin the
        # `_already_recorded_fh` docstring claims is gone. No row on disk moves,
        # so the caps test stays green and only the window test can fire.
        "_MAX_LINE_BYTES grows until a maximal row fills the dedupe window",
        HOOK,
        "_MAX_LINE_BYTES = 2048",
        "_MAX_LINE_BYTES = 4096",
        _WINDOW,
    ),
    (
        # THE SAME RATIO FROM THE WINDOW SIDE, and the reason both are here: the
        # guard extracts this literal by AST from `_already_recorded_fh` alone.
        # Mutating only the constant would leave a guard that could have
        # hardcoded 4096 and still passed.
        "the dedupe tail shrinks to the size of a single maximal row",
        HOOK,
        "fh.seek(max(0, size - 4096))",
        "fh.seek(max(0, size - 2048))",
        _WINDOW,
    ),
    (
        # NON-VACUITY. `_rows()` feeds every other assertion in the file, so a
        # filter that admits nothing leaves them all iterating an empty list and
        # passing. This is the one mutant aimed at the guard rather than at its
        # subject, and it is killable exactly because the non-vacuity test does
        # not iterate — it asserts the population is there.
        "the guard's row reader silently yields nothing",
        GUARD,
        "        if line.strip():",
        "        if line.strip() and False:",
        _VACUITY,
    ),
]
