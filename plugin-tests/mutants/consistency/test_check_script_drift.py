"""Mutation batch for test_check_script_drift.py.

CLAUDE.md names this guard as the one covering a *silent* failure: the ledger
writer and its two readers each carry their own copy of the resolver that decides
where the ledger lives, and a writer/reader disagreement makes the retro report
zero runs — which reads as a cold start, not as a bug. An unproven guard is worth
least exactly there, which is why this batch was the first one issue #176 named.

**Provenance, per mutant, because the blanket version was false.** An earlier
draft of this docstring said every mutant below "re-breaks a defect this file's
own docstrings record as having shipped once… these are the versions of this file
that existed and passed." Review measured it and only one is a git fact:

    git log --oneline --all --follow -- plugin-tests/scripts/check_script_drift.py
    git log --all -S'for node in ast.walk(tree)' -- '*check_script_drift.py'

The first returns six commits; the second returns only the commit that added THIS
batch, i.e. the string never existed in the script. So the mutants divide three
ways, and saying which is which is the whole point — a mutant justified by
invented history is the reasoning-as-measurement defect this repo pays most for.

**Git-verifiable defects.** Mutant 3 only. Before `086947e` ("Point the drift
check at the pair that can actually fail silently") the resolver group listed the
two readers and not the writer, so both could be identically wrong about where the
ledger lives with the group green. That is the silent failure the whole script
exists for.

**Recorded by the script's own docstrings, from before its first commit
(`873538f`), so not recoverable from history.** Mutants 1 and 4. The
`_normalize_constants` docstring records a version that blanked every string
literal — fatal here, because the guarded functions are almost entirely string
literals (`["git", "rev-parse", "--show-toplevel"]`, `<root>/cla.io/retro`), so a
sibling switching git plumbing compared EQUAL. Three tests should object to
mutant 1. The `check_group` comment records an early return that reported the
first missing file and hid every other problem in the group.

**Constructed probes with no historical instance.** Mutants 2, 5, 6 and 7.
Mutant 2 (`ast.walk` shadowing a top-level def by a nested one) is a rationale the
code states, never a shipped bug — `for node in tree.body:` is in `873538f` and
every commit since. Mutant 5 drops the missing-function report. Mutants 6 and 7
empty and disable a `SIBLING_GROUPS` group; both SURVIVED until
`test_every_group_still_compares_at_least_two_files_and_one_function` and
`test_the_group_set_itself_has_not_shrunk` were added, because only the resolver
group had ever been pinned by name.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_check_script_drift.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]

SCRIPT = DEV / "scripts" / "check_script_drift.py"

# Scoped to the ONE guard file. Pointing at `tests/consistency/` as a whole would
# report every mutant "killed" the moment anything else in that directory went
# red, which proves nothing about this guard.
GUARD = [DEV / "tests" / "consistency" / "test_check_script_drift.py"]

# `check_script_drift.py` is CRLF in this checkout, so a bare "\n" in a
# multi-line anchor matches nothing and every mutant it anchors would report
# "checks nothing". Build the separator off the file's own bytes rather than
# assuming either ending — the batch then works whatever the checkout does.
_NL = "\r\n" if b"\r\n" in SCRIPT.read_bytes() else "\n"


def _lines(*rows: str) -> str:
    return _NL.join(rows)


_DOCSTRING_ONLY = _lines(
    "    if (",
    "        node.body",
    "        and isinstance(node.body[0], ast.Expr)",
    "        and isinstance(node.body[0].value, ast.Constant)",
    "        and isinstance(node.body[0].value.value, str)",
    "    ):",
    '        node.body[0].value.value = ""',
    "    return node",
)

_BLANK_EVERY_STRING = _lines(
    "    for sub in ast.walk(node):",
    "        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):",
    '            sub.value = ""',
    "    return node",
)

_WRITER_AND_BOTH_READERS = _lines(
    '        "files": (',
    '            "lib/log_run.py",',
    '            "skills/codify-retro/scripts/codify_aggregate.py",',
)

_READERS_ONLY = _lines(
    '        "files": (',
    '            "skills/codify-retro/scripts/codify_aggregate.py",',
)

_MISSING_FILE_REPORT = (
    "            problems.append("
    "f\"{rel}: file not found (listed in {group['name']!r})\")"
)

_COLLECT_MISSING = _lines(_MISSING_FILE_REPORT, "            continue")

_RETURN_ON_FIRST_MISSING = _lines(_MISSING_FILE_REPORT, "            return problems")

_REPORT_MISSING_FN = _lines(
    "                problems.append("
    "f\"{rel}: missing `{fn}` (expected in {group['name']})\")",
    "                continue",
)

_SWALLOW_MISSING_FN = "                continue"

MUTANTS = [
    (
        "_normalize_constants blanks every string, not just the docstring",
        SCRIPT,
        _DOCSTRING_ONLY,
        _BLANK_EVERY_STRING,
        GUARD,
    ),
    (
        "extract_functions walks the whole tree, so a nested def shadows the real one",
        SCRIPT,
        "    for node in tree.body:",
        "    for node in ast.walk(tree):",
        GUARD,
    ),
    (
        "the resolver group drops the writer and compares the two readers only",
        SCRIPT,
        _WRITER_AND_BOTH_READERS,
        _READERS_ONLY,
        GUARD,
    ),
    (
        "a missing file returns early instead of collecting the rest",
        SCRIPT,
        _COLLECT_MISSING,
        _RETURN_ON_FIRST_MISSING,
        GUARD,
    ),
    (
        "a guarded function missing from a sibling is not reported",
        SCRIPT,
        _REPORT_MISSING_FN,
        _SWALLOW_MISSING_FN,
        GUARD,
    ),
    (
        # Group 3's helper is what makes three tests actually RUN on Windows; a
        # group with no functions compares nothing and every test still passes.
        # This mutant SURVIVED before `test_every_group_still_compares_at_least_
        # _two_files_and_one_function` existed — the resolver group was pinned by
        # name and the other two were not, so the protection stopped where someone
        # had last been burned rather than where the risk was.
        "a group is silently emptied of the functions it compares",
        SCRIPT,
        '        "functions": ("make_dir_alias",),',
        '        "functions": (),',
        GUARD,
    ),
    (
        # And the level above: a group deleted outright leaves nothing to iterate,
        # so narrowing checks cannot see it either.
        "the aggregator record-loading group is dropped entirely",
        SCRIPT,
        '        "name": "retro aggregator record loading",',
        '        "name": "retro aggregator record loading (disabled)",',
        GUARD,
    ),
]
