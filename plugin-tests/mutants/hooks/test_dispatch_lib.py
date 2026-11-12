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
ASK = PLUGIN / "hooks" / "ask-destructive-git.py"
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
        'if ch == "$" and text.startswith("$(", i):',
        'if False and text.startswith("$(", i):',
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
        'depth += (text[j] == "(") - (text[j] == ")")',
        'depth += (text[j] == "(")',
        TARGETS,
    ),
    (
        # Killed by the quoted-delimiter heredoc silent cases (commit and PR
        # body shapes), which the substitution fix would otherwise turn into asks.
        "heredoc bodies are no longer blanked before the quote passes",
        LIB,
        "    stripped = _blank_heredoc_bodies(cmd)",
        "    stripped = cmd",
        TARGETS,
    ),
    (
        # Killed by the Markdown-code-span-in-a-quoted-heredoc silent cases.
        "a quoted heredoc delimiter is treated as unquoted, so backtick prose runs",
        LIB,
        'quoted = m.group(2) is not None or m.group(3) is not None or m.group(4) == "\\\\"',
        "quoted = False",
        TARGETS,
    ),
    (
        # Killed by the `bash <<'EOF'` ask-case.
        "a heredoc fed to a shell is blanked although the shell runs it",
        LIB,
        "if _SHELL_WORD.search(cmd[line_start : m.start()]):",
        "if False:",
        TARGETS,
    ),
    (
        # Killed by test_strip_quoted_spans_leaves_executed_heredoc_shapes_visible.
        "an unterminated heredoc body is blanked to the end of the command",
        LIB,
        "        if not found:",
        "        if False:",
        TARGETS,
    ),
    (
        # Killed by the here-string case in the same test.
        "a `<<<` here-string is read as a heredoc operator",
        LIB,
        '    r"(?<!<)<<(?!<)(-?)',
        '    r"<<(?!<)(-?)',
        TARGETS,
    ),
    (
        # Killed by the unquoted-heredoc tests: its executed substitutions go dark.
        "an unquoted heredoc body is blanked whole, hiding its substitutions",
        LIB,
        "else _blank_keeping_substitutions(body, True)",
        'else "".join(c if c in "\\r\\n" else "#" for c in body)',
        TARGETS,
    ),
    (
        # Killed by the no-trailing-operand ask-cases (`$(git reset --hard)`).
        "the flag terminator no longer accepts `)` or a backtick",
        ASK,
        '_END = r"(?:[\\s\\\\)`]|=|$)"',
        '_END = r"(?:[\\s\\\\]|=|$)"',
        TARGETS,
    ),
    (
        # Killed by the `$(git push -f)` ask-case.
        "the bundled short-flag force terminator no longer accepts `)`",
        ASK,
        '+ _END + r"|-[A-Za-z]*f[A-Za-z]*(?:[\\s\\\\)`]|$))"',
        '+ _END + r"|-[A-Za-z]*f[A-Za-z]*(?:[\\s\\\\]|$))"',
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
