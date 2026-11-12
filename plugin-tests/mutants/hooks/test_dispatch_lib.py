"""Mutant batch for the command-substitution handling in `strip_quoted_spans`
(`hooks/_dispatch_lib.py`).

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_dispatch_lib.py

`strip_quoted_spans` feeds every git guard. Inside double quotes the shell still
executes `$(...)` and backtick substitutions, so their bodies must stay visible
to the guards while the surrounding prose, single-quoted text and escaped
substitutions stay blanked. Each entry re-breaks one part of that rule.

Anchors are single lines (the source is CRLF in a Windows checkout).
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]                      # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
LIB = PLUGIN / "hooks" / "_dispatch_lib.py"
TARGETS = [
    DEV / "tests" / "hooks" / "test_dispatch_lib.py",
    DEV / "tests" / "hooks" / "test_dispatch.py",
]

MUTANTS = [
    (
        # Killed by the substitution ask-cases in test_dispatch.py and
        # test_strip_quoted_spans_keeps_executed_substitution_bodies_visible.
        "double-quoted spans are blanked whole again, hiding $(...) and "
        "backtick bodies the shell executes",
        LIB,
        "re.sub(r'\"[^\"]*\"', _double_quoted, stripped)",
        "re.sub(r'\"[^\"]*\"', _placeholder, stripped)",
        TARGETS,
    ),
    (
        # Killed by the `$(...)` ask-cases (backtick cases still pass).
        "the $(...) branch never fires, so only backtick bodies stay visible",
        LIB,
        'if ch == "$" and inner.startswith("$(", i):',
        'if False and inner.startswith("$(", i):',
        TARGETS,
    ),
    (
        # Killed by the backtick-in-double-quotes ask-case.
        "the backtick branch never fires inside double quotes",
        LIB,
        'elif ch == "`":',
        "elif False:",
        TARGETS,
    ),
    (
        # Killed by the escaped-substitution silent cases.
        "an escaped \\$( or \\` is treated as an executed substitution",
        LIB,
        'if ch == "\\\\":',
        "if False:",
        TARGETS,
    ),
    (
        # Killed by the `$(date) then git reset --hard` silent case: without the
        # closing-paren count the body runs to the end of the span.
        "the $(...) body never closes, so prose after it is exposed",
        LIB,
        'depth += (inner[j] == "(") - (inner[j] == ")")',
        'depth += (inner[j] == "(")',
        TARGETS,
    ),
    (
        # Killed by the unquoted-backtick ask-case: restoring the old
        # backtick pass blanks a substitution the shell runs.
        "unquoted backtick spans are blanked again",
        LIB,
        "    return stripped",
        '    return re.sub(r"`[^`]*`", _placeholder, stripped)',
        TARGETS,
    ),
]
