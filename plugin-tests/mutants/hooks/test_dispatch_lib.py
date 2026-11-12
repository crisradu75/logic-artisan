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
        # Killed by the odd-delimiter cases (`END-OF-FILE`) which must stay visible.
        "any quoted word, hyphens included, counts as a plain delimiter",
        LIB,
        "<<(?!<)[ \\t]*(?:'([A-Za-z0-9_]+)'",
        "<<(?!<)[ \\t]*(?:'([^'\\n]+)'",
        TARGETS,
    ),
    (
        # Killed by the `ssh`/`source`/`fish`/`pwsh`/`bash` ask-cases.
        "the interpreter-word check on the operator line is off",
        LIB,
        "    if _line_runs_an_interpreter(line):",
        "    if False:",
        TARGETS,
    ),
    (
        # Killed by the `/bin/bash <<'EOF'` ask-case.
        "an interpreter given by path is no longer recognised",
        LIB,
        'base = word.replace("\\\\", "/").rsplit("/", 1)[-1].lower()',
        "base = word.lower()",
        TARGETS,
    ),
    (
        # Killed by the `bash.exe <<'EOF'` ask-case.
        "an interpreter with an .exe suffix is no longer recognised",
        LIB,
        "            if base.endswith(ext):",
        "            if False:",
        TARGETS,
    ),
    (
        # Killed by the `cat <<'EOF' && git status` case: anything after the
        # operator but a redirect must keep the body visible.
        "text after the operator (a chain) no longer keeps the body visible",
        LIB,
        "    if tail is None:",
        "    if False:",
        TARGETS,
    ),
    (
        # Killed by the x.sh / no-suffix ask-cases.
        "any redirect target counts as a document",
        LIB,
        "    return target.strip(\"'\\\"\").lower().endswith(_DOC_SUFFIXES)",
        "    return True",
        TARGETS,
    ),
    (
        # Killed by the same-body-first-then-exec ask-case: an operator written
        # inside an earlier body is data, one after it is not.
        "an operator inside an earlier body is no longer skipped",
        LIB,
        "        if k <= skip_to:",
        "        if False:",
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
        "ends[k] - starts[k] > _HEREDOC_MAX_LINE",
        "ends[k] - starts[k] > 10**9",
        TARGETS,
    ),
    (
        # Killed by test_strip_quoted_spans_keeps_line_structure_and_crlf_of_a_blanked_body.
        "a CRLF terminator line is no longer found",
        LIB,
        '.rstrip("\\r")',
        "",
        TARGETS,
    ),
    (
        # Killed by the same test: blanking must keep the line breaks.
        "blanking a heredoc body also blanks its line breaks",
        LIB,
        '        if out[i] not in "\\r\\n":',
        "        if True:",
        TARGETS,
    ),
    (
        # Killed by the "$body" silent case: Markdown spans in a visible quoted
        # body stay blanked, as before.
        "backtick spans in a not-known-data quoted body are no longer blanked",
        LIB,
        "            ticks.append(piece)",
        "            pass",
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
