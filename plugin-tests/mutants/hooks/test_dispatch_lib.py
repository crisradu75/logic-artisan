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
        # Killed by the commit/PR-body silent cases: those bodies would ask.
        "heredoc bodies are no longer blanked before the quote passes",
        LIB,
        "    stripped = _blank_heredoc_bodies(cmd)",
        "    stripped = cmd",
        TARGETS,
    ),
    (
        # Killed by the `; git reset --hard` after the message: the WHOLE command
        # must match, not just its start.
        "the message command only has to match at the start of the command",
        LIB,
        "message = _MESSAGE_COMMAND.fullmatch(cmd)",
        "message = _MESSAGE_COMMAND.match(cmd)",
        TARGETS,
    ),
    (
        # Killed by the `git commit -m $(cat <<'EOF' ... )"` visible case: a
        # substitution NOT wrapped in double quotes has its output run.
        "the message shape no longer requires a double quote before $(",
        LIB,
        r'''rf"(?: {_ARG})* \"\$\(cat <<''',
        r'''rf"(?: {_ARG})* \$\(cat <<''',
        TARGETS,
    ),
    (
        # Killed by the `echo "$(cat <<'EOF'` visible case.
        "echo counts as a message verb",
        LIB,
        'r"(?:git (?:commit|tag|notes)|gh (?:pr',
        'r"(?:echo|git (?:commit|tag|notes)|gh (?:pr',
        TARGETS,
    ),
    (
        # Killed by the `-m "a | b"` visible case: a double-quoted word may not
        # carry shell syntax.
        "a double-quoted word may carry a pipe",
        LIB,
        r'''_DQ = r"\"[A-Za-z0-9 ._,:/()#@%+=~-]*\""''',
        r'''_DQ = r"\"[A-Za-z0-9 ._,:/()#@%+=~|-]*\""''',
        TARGETS,
    ),
    (
        # Killed by the `git commit -m x # "$(cat` visible case (a comment).
        "a bare word may be a comment marker",
        LIB,
        '_W = r"[A-Za-z0-9_.,:=@+%~/-]+"',
        '_W = r"[A-Za-z0-9_.,:=@+%~/#-]+"',
        TARGETS,
    ),
    (
        # Killed by the single-quote visible case (`git commit -m 'a "$(cat`).
        "a bare word may open a single quote",
        LIB,
        '_W = r"[A-Za-z0-9_.,:=@+%~/-]+"',
        "_W = r\"[A-Za-z0-9_.,:=@+%~/'-]+\"",
        TARGETS,
    ),
    (
        # Killed by the early-terminator case: the shell ends the heredoc at the
        # FIRST line equal to the word.
        "a body line equal to the delimiter no longer ends the body",
        LIB,
        r'''r"(?P<body>(?:(?!(?P=w))[^\n]*\n)*)"''',
        r'''r"(?P<body>(?:[^\n]*\n)*?)"''',
        TARGETS,
    ),
    (
        # Killed by the `EOF)` / `EOFx)` cases: inside $( ) bash ends the heredoc at
        # a line that only STARTS with the word.
        "only a line exactly equal to the delimiter ends the body",
        LIB,
        r'''r"(?P<body>(?:(?!(?P=w))[^\n]*\n)*)"''',
        r'''r"(?P<body>(?:(?!(?P=w)\r?\n)[^\n]*\n)*)"''',
        TARGETS,
    ),
    (
        # Killed by the quoted-backtick case (`echo ' ` '; git reset --hard; ...`).
        "backticks are paired in a body that contains quotes",
        LIB,
        """    if "'" in body or '"' in body:""",
        "    if False:",
        TARGETS,
    ),
    (
        # Killed by the `&& bash x.sh` visible case.
        "bash is allowed as a trailing command",
        LIB,
        'rf"(?: && (?:git (?:status|push|add|log|diff|show|fetch|pull)"',
        'rf"(?: && (?:bash|git (?:status|push|add|log|diff|show|fetch|pull)"',
        TARGETS,
    ),
    (
        # Killed by the `$SHELL`/`$0` cases through `_runs_an_interpreter`.
        "$SHELL and $0 no longer count as interpreters",
        LIB,
        "    if _SHELL_VAR.search(text):",
        "    if False:",
        TARGETS,
    ),
    (
        # Killed by the `sh <<'EOF'` + backtick ask-case.
        "an interpreter word no longer keeps Markdown-span blanking off",
        LIB,
        "    if _runs_an_interpreter(cmd[: nl + 1] + cmd[body_end:]):",
        "    if False:",
        TARGETS,
    ),
    (
        # Killed by the path-form interpreter case below.
        "an interpreter given by path is no longer recognised",
        LIB,
        'base = word.replace("\\\\", "/").rsplit("/", 1)[-1].lower()',
        "base = word.lower()",
        TARGETS,
    ),
    (
        # Killed by the `.exe` case below.
        "an interpreter with an .exe suffix is no longer recognised",
        LIB,
        "            if base.endswith(ext):",
        "            if False:",
        TARGETS,
    ),
    (
        # Killed by the unquoted-first-heredoc ask-case: an earlier `<<` may make
        # the quoted one a fake.
        "an earlier heredoc operator no longer disqualifies the later one",
        LIB,
        '    if cmd.find("<<") != first.start():',
        "    if False:",
        TARGETS,
    ),
    (
        # Killed by `ls # cat <<'EOF'` + a backtick command line.
        "a comment marker before the operator no longer keeps the body visible",
        LIB,
        'for ch in ("#", "`", "\\\\"):',
        'for ch in ("`", "\\\\"):',
        TARGETS,
    ),
    (
        # Killed by "echo `cat <<'EOF'" + a backtick command line.
        "a backtick before the operator no longer keeps the body visible",
        LIB,
        'for ch in ("#", "`", "\\\\"):',
        'for ch in ("#", "\\\\"):',
        TARGETS,
    ),
    (
        # Killed by the stray single quote before the operator case.
        "a stray single quote before the operator no longer keeps the body visible",
        LIB,
        "    if (head.count(\"'\") - (2 if first.group(1) else 0)) % 2 or (",
        "    if False or (",
        TARGETS,
    ),
    (
        # Killed by test_strip_quoted_spans_blanks_nothing_past_the_operator_and_line_caps.
        "the operator-count cap is gone",
        LIB,
        "if not ops or len(_ANY_HEREDOC.findall(cmd)) > _HEREDOC_MAX_OPS:",
        "if not ops:",
        TARGETS,
    ),
    (
        # Killed by the same test (5000-char operator line).
        "the operator-line length cap is gone",
        LIB,
        "> _HEREDOC_MAX_LINE:",
        "> 10**9:",
        TARGETS,
    ),
    (
        # Killed by test_strip_quoted_spans_keeps_line_structure_and_crlf_of_a_blanked_body.
        "blanking a heredoc body also blanks its line breaks",
        LIB,
        '        if out[i] not in "\\r\\n":',
        "        if True:",
        TARGETS,
    ),
    (
        # Killed by the "$body" silent case: Markdown spans in a plain-quoted
        # body stay blanked, as on main.
        "backtick spans in a plain-quoted body are no longer blanked",
        LIB,
        "        _blank_data(out, nl + 1 + span.start() + 1, nl + 1 + span.end() - 1)",
        "        pass",
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
