"""Mutant batch for `tests/hooks/test_warn_heredoc_escape_mangling.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_warn_heredoc_escape_mangling.py

Scope: only the terminator lookup in `_heredoc_bodies`, which replaced a
per-operator scan of the rest of the command (quadratic, 13 s on 25000 `cat <<A`
lines) with an index of line numbers per delimiter and a bisect. These re-break
the three things the index must keep: a terminator is the first matching line at
or after the lines not yet claimed, `<<-` matches on the stripped line while
`<<` matches the exact line, and an operator with no matching line is skipped.

Not mutated: building the index once (`if exact is None ...`). Rebuilding it for
every operator is the original slowness, and the mutant would take minutes to
run before the timing test could fail.

Paths resolve from this file's own location, never an absolute developer path.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]  # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
HOOK = PLUGIN / "hooks" / "warn-heredoc-escape-mangling.py"
TARGETS = [DEV / "tests" / "hooks" / "test_warn_heredoc_escape_mangling.py"]

MUTANTS = [
    (
        "terminator search ignores the lines an earlier heredoc already claimed",
        HOOK,
        "bisect.bisect_left(found, start)",
        "bisect.bisect_left(found, i + 1)",
        TARGETS,
    ),
    (
        "a terminator on the first unclaimed line is skipped",
        HOOK,
        "bisect.bisect_left(found, start)",
        "bisect.bisect_right(found, start)",
        TARGETS,
    ),
    (
        "a <<- operator matches the exact line, not the stripped one",
        HOOK,
        "(stripped if dash else exact)",
        "(exact if dash else exact)",
        TARGETS,
    ),
    (
        "a plain << operator matches the stripped line",
        HOOK,
        "(stripped if dash else exact)",
        "(stripped if dash else stripped)",
        TARGETS,
    ),
    (
        "an operator with no terminator line crashes instead of being skipped",
        HOOK,
        "end = found[k] if k < len(found) else None",
        "end = found[k]",
        TARGETS,
    ),
]
