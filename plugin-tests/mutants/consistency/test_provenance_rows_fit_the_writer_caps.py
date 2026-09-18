"""Mutation batch for test_provenance_rows_fit_the_writer_caps.py.

The guard claims no row in the provenance ledger exceeds a cap the writer
enforces, and that the dedupe's tail window still clears a maximal row.

**NO MUTANT HERE TOUCHES THE LEDGER, and that is a deliberate correction.** An
earlier version of this batch mutated `cla.io/retro/commit-provenance.jsonl` to
plant cap violations, which is the textbook answer when a guard's two candidate
rules agree on every correct input. It is the wrong answer when the input is a
LIVE file the harness writes to: `log-commit-provenance.py` appends a row on
every commit, and `mutate.py` snapshots the file, runs six pytest rounds, then
restores the snapshot — so a commit landing mid-run has its row erased, and the
post-restore integrity check compares against that same snapshot and reports
success. The batch would print "All 6 killed" while destroying exactly the data
the change it guards exists to repair.

The guard was restructured instead. `_cap_violations` takes rows as an argument,
so `test_each_cap_is_actually_checked` feeds it synthetic rows that violate one
cap each. That makes the comparisons genuinely killable from the GUARD side —
mutants 1-3 — with nothing on disk mutated. The general form: when mutating the
input is unsafe, give the checker a seam and mutate through it.

**Six mutants.** Three break a cap comparison, two break the two halves of the
dedupe ratio, one breaks the non-vacuity partner.

Mutants 4-5 move `_MAX_LINE_BYTES` and the window literal past each other in
opposite directions, and both must genuinely break the dedupe rather than merely
trip a stricter-than-necessary assertion: the guard's bound is
`window >= _MAX_LINE_BYTES`, because the last line is whole whenever the window
holds one maximal row. So mutant 4 raises the cap ABOVE the 4096 window rather
than to a value inside it, and mutant 5 drops the window BELOW the 2048 cap. A
`_MAX_LINE_BYTES` of 4096 would be legitimate and is deliberately not a mutant.

EVERY MUTANT IS SCOPED TO ONE TEST, so a kill attributes to the branch it aims at
rather than to "something in this file".

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_provenance_rows_fit_the_writer_caps.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"

GUARD = DEV / "tests" / "consistency" / "test_provenance_rows_fit_the_writer_caps.py"
HOOK = PLUGIN / "hooks" / "log-commit-provenance.py"

_CAPS = [f"{GUARD}::test_each_cap_is_actually_checked"]
_WINDOW = [f"{GUARD}::test_the_dedupe_window_clears_a_maximal_row"]
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
        # row past the 4096 WINDOW, at the end of the file. The cap is the margin
        # that keeps the window's assumption out of reach, and this branch
        # defends the margin.
        "the line-length check accepts twice _MAX_LINE_BYTES",
        GUARD,
        "        if nbytes > maxb:",
        "        if nbytes > maxb * 2:",
        _CAPS,
    ),
    (
        # THE RATIO FROM THE ROW SIDE, and it must clear the WINDOW to be a real
        # defect. At 8192 a maximal row cannot fit in the 4096 tail at all, so
        # `lines[-1]` is a truncated row, `json.loads` fails, the dedupe reads
        # "not recorded" and the next commit is appended twice.
        "_MAX_LINE_BYTES grows past the dedupe window entirely",
        HOOK,
        "_MAX_LINE_BYTES = 2048",
        "_MAX_LINE_BYTES = 8192",
        _WINDOW,
    ),
    (
        # THE SAME RATIO FROM THE WINDOW SIDE, below the cap this time, and the
        # reason both are here: the guard reads BOTH numbers live — one as a
        # module constant, one by AST out of `_already_recorded_fh` alone. A
        # batch moving only one would leave the other a value the guard could
        # have hardcoded and nobody would know.
        "the dedupe tail shrinks below a maximal row",
        HOOK,
        "fh.seek(max(0, size - 4096))",
        "fh.seek(max(0, size - 1024))",
        _WINDOW,
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
