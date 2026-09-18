"""Mutation batch for test_ledger_summary.py.

`ledger_summary.py` reads ANY ledger by deriving the shape from the records
rather than being configured with it, so the thing worth pinning is the TYPE
DISPATCH in `summarise_field`: which kind of field reports what. Every mutant
below either collapses one branch into another or removes a signal a reader would
otherwise act on.

**Two of them are about not LYING rather than about being right.** Mutant 2 turns
producer drift — a field whose type changed across records — into an ordinary
frequency table, which is the one signal the specific readers spend real code
detecting. Mutant 5 drops the row for a ledger that resolved to nothing, so a
one-repo result is indistinguishable from a two-repo one. Both leave a plausible,
well-formed report; that is what makes them worth a mutant rather than a comment.

**A FINDING ABOUT THE GUARD, not the code, and the reason mutant 7 is written the
way it is.** Dropping the frequency component of the sort key entirely — plain
alphabetical — SURVIVES. The fixture's field names are `common` (present 3) and
`rare` (present 1), and `common` sorts before `rare` alphabetically too, so
sorted-by-name and sorted-by-frequency agree on the only input supplied.
`test_fields_are_ordered_by_how_many_records_carry_them` would therefore pass on
a purely alphabetical implementation. Mutant 7 INVERTS the key instead, which
that fixture does discriminate. The real fix is on the test side — rename the
frequent field to something late in the alphabet — after which the plain-key
mutant becomes usable too. This is CLAUDE.md's "where two candidate rules agree
on all correct inputs, mutate the input" case, and the input is the fixture.

**DELIBERATELY NOT MUTANTS, each unkillable in a correct tree:**

  * removing `and not isinstance(v, bool)` from the numeric branch. The bool
    branch runs first and consumes every all-bool field, so the redundant guard
    never decides anything on any input. It is correct defensive code; it is just
    not pinnable as written, and mutant 1 pins the ordering it depends on.
  * `_TOP_N = 10` -> any larger value, and `round(..., 2)` -> `round(..., 3)`.
    No fixture has more than 10 distinct strings, and `mean([2,4,9])` is exactly
    5.0, so both agree with the original everywhere.
  * the fleet-bullet parse `line[2:].split("#", 1)[0].strip().strip("`").strip()`
    -> `line[2:].strip()`. The fleet fixtures write bare `- <path>` bullets with
    no comments and no backticks.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/lib/test_ledger_summary.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"

SCRIPT = PLUGIN / "lib" / "ledger_summary.py"

TARGETS = [DEV / "tests" / "lib" / "test_ledger_summary.py"]

MUTANTS = [
    (
        # The comment above that branch names the trap by hand: without the
        # bool-first split a boolean field reports `mean: 0.67`, which reads as a
        # measurement and is a coin flip.
        "bool stops being handled before int, so a boolean field is reported as a "
        "mean rather than a true/false split",
        SCRIPT,
        "    if all(isinstance(v, bool) for v in non_null):",
        "    if False:",
        TARGETS,
    ),
    (
        # `all` -> `any` is the quiet one: all-string fields behave identically,
        # so only the MIXED case moves and the kill is attributable.
        "producer drift is coerced into a frequency table, so a field whose type "
        "changed across records is reported as strings and never named as mixed",
        SCRIPT,
        "    elif all(isinstance(v, str) for v in non_null):",
        "    elif any(isinstance(v, str) for v in non_null):",
        TARGETS,
    ),
    (
        "nulls stop being counted, so every mean below reads as if it were taken "
        "over the whole ledger rather than over the rows that carried the field",
        SCRIPT,
        '    out["null"] = len(values) - len(non_null)',
        '    out["null"] = 0',
        TARGETS,
    ),
    (
        "the duplicate-path guard is dropped, so the same ledger passed twice "
        "counts twice and a fleet run reports double the sample it read",
        SCRIPT,
        "        if key in seen:",
        "        if False:",
        TARGETS,
    ),
    (
        # `continue` on the next line is left intact, so the ONLY observable
        # change is the dropped row — no loop breakage to muddy the kill.
        "a ledger that resolved to nothing vanishes from the report, so a 1-repo "
        "result is indistinguishable from a 2-repo one",
        SCRIPT,
        '            ledgers.append({"path": str(p), "found": False, "records": 0, "skipped": 0})',
        "            pass",
        TARGETS,
    ),
    (
        # The continuation line `"fields": {}}` is untouched, so the literal stays
        # syntactically valid and the only change is the missing skeleton.
        "the empty result loses its window skeleton, so a consumer's "
        "`.get(\"window\")` reads a clean value where it should read 'nothing measured'",
        SCRIPT,
        '        return {"records": 0, "window": {"first_ts": None, "last_ts": None},',
        '        return {"records": 0,',
        TARGETS,
    ),
    (
        # Inverted rather than removed — see the header for why removing it
        # survives, and why that is a finding about the fixture.
        "field ordering inverts, so the once-seen drift keys come first and the "
        "field present in every record is buried at the bottom",
        SCRIPT,
        '            key=lambda kv: (-kv[1]["present"], kv[0]))),',
        '            key=lambda kv: (kv[1]["present"], kv[0]))),',
        TARGETS,
    ),
]
