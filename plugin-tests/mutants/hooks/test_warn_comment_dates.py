"""Mutant batch for `tests/hooks/test_warn_comment_dates.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_warn_comment_dates.py

Scope: `_has_dated_comment`, which replaced the one-pattern `#.*\\b<date>\\b` (quadratic on
a line of hashes) with "find the first `#`, then search for a date after it". These re-break
what that form must keep: the line needs a `#` at all, the date must come after it, the
search starts right after the hash (so `#2026-10-30` still counts), and the search is
bounded to the text after the first hash rather than rescanning.

Not mutated: the date pattern's own shape (`\\d{4}-\\d{2}-\\d{2}`) and its word boundaries,
which the existing near-miss table covers and this change did not touch.

The timing mutant restores the old quadratic search; it takes up to about two minutes to be killed
because the timing test must run the slow code to fail.

Paths resolve from this file's own location, never an absolute developer path.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]  # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
HOOK = PLUGIN / "hooks" / "warn-comment-dates.py"
TARGETS = [DEV / "tests" / "hooks" / "test_warn_comment_dates.py"]

MUTANTS = [
    (
        "a line with no hash is treated as a comment",
        HOOK,
        "return i >= 0 and _DATE.search(line, i + 1) is not None",
        "return _DATE.search(line, i + 1) is not None",
        TARGETS,
    ),
    (
        "a date before the hash counts",
        HOOK,
        "return i >= 0 and _DATE.search(line, i + 1) is not None",
        "return i >= 0 and _DATE.search(line) is not None",
        TARGETS,
    ),
    (
        "the search skips the character right after the hash",
        HOOK,
        "_DATE.search(line, i + 1)",
        "_DATE.search(line, i + 2)",
        TARGETS,
    ),
    (
        "the last hash is used, so a date between two hashes is missed",
        HOOK,
        "i = line.find('#')",
        "i = line.rfind('#')",
        TARGETS,
    ),
    (
        "the quadratic one-pattern search is restored",
        HOOK,
        "return i >= 0 and _DATE.search(line, i + 1) is not None",
        "return re.search(r'#.*\\b\\d{4}-\\d{2}-\\d{2}\\b', line) is not None",
        TARGETS,
    ),
]
