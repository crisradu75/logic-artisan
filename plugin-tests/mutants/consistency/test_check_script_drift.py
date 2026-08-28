"""Mutation batch for test_check_script_drift.py.

CLAUDE.md names this guard as the one covering a *silent* failure: the ledger
writer and its two readers each carry their own copy of the resolver that decides
where the ledger lives, and a writer/reader disagreement makes the retro report
zero runs — which reads as a cold start, not as a bug. An unproven guard is worth
least exactly there, which is why this batch was the first one the TODO entry
named.

Every mutant below re-breaks a defect `check_script_drift.py`'s own docstrings
record as having shipped once. That is deliberate: these are not hypothetical
edits, they are the versions of this file that existed and passed.

- 1 restores the original `_normalize_constants`, which blanked every string
  literal. The guarded functions are almost entirely string literals
  (`["git", "rev-parse", "--show-toplevel"]`, `<root>/cla.io/retro`), so that
  version reported CLEAN on a sibling switching git plumbing and on one writing
  its ledger to a different directory. Three tests should object.
- 2 restores `ast.walk`, under which a nested def sharing a guarded name
  overwrites the real top-level one and the comparison runs against the wrong
  body.
- 3 drops the WRITER from the resolver group, leaving the two readers comparing
  only against each other. Both can then be identically wrong about where the
  ledger lives with the group still green — the precise silent failure, and the
  reason the non-vacuity test pins all three files by name.
- 4 restores the early return on a missing file, which reported the first and
  hid every other problem in the group.
- 5 drops the missing-function report, so a sibling that deleted a guarded
  function compares equal to one that still has it.

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
]
