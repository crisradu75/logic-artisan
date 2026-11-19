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
# `GitInvocation` (#526) is read by both git guards, so its mutants also run
# their tests.
GIT_TARGETS = TARGETS + [
    DEV / "tests" / "hooks" / "test_ask_destructive_git.py",
    DEV / "tests" / "hooks" / "test_warn_stray_scratch_artifact.py",
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
    # --- GitInvocation (#526): the git global-option matcher ---------------
    (
        # Moved here from the ask-destructive-git batch: `GIT_CMD` is now
        # composed once, here. Killed by the `GIT.exe` rows of the
        # differential test and test_branch_delete_fires_on_every_executable_spelling.
        "the git matcher anchors on a bare lowercase `git`, so git.exe / GIT "
        "/ Git.Exe stop matching",
        LIB,
        "_GIT_HEAD = re.compile(GIT_CMD + GIT_SEP)",
        '_GIT_HEAD = re.compile(r"git" + GIT_SEP)',
        GIT_TARGETS,
    ),
    (
        "`-c k=v` / `-C dir` stop taking their value, so the subcommand after "
        "one is never reached",
        LIB,
        "        _GIT_OPT_VALUED,",
        "",
        GIT_TARGETS,
    ),
    (
        "`--work-tree <path>` and its siblings stop taking a space-separated value",
        LIB,
        '        _GIT_OPT_NAMED + GIT_SEP + r"\\S+",',
        "",
        GIT_TARGETS,
    ),
    (
        # Killed by the differential test: when both readings reach a
        # subcommand the regex took the value-first one, and the tail differs.
        "a named option is read as value-less before it is read with a value",
        LIB,
        '        _GIT_OPT_NAMED + GIT_SEP + r"\\S+",',
        '        _GIT_OPT_NAMED, _GIT_OPT_NAMED + GIT_SEP + r"\\S+",',
        GIT_TARGETS,
    ),
    (
        "a bare short flag (`-p`) stops being skipped",
        LIB,
        "        _GIT_OPT_SHORT,",
        "",
        GIT_TARGETS,
    ),
    (
        "the last step (long options such as `--no-pager`) is never tried",
        LIB,
        "if step < len(_GIT_OPT_STEPS):",
        "if step < len(_GIT_OPT_STEPS) - 1:",
        GIT_TARGETS,
    ),
    (
        "every other step is skipped",
        LIB,
        "frame[1] = step + 1",
        "frame[1] = step + 2",
        GIT_TARGETS,
    ),
    (
        # Killed by the timing tests: every split is tried again (exponential).
        "a position already ruled out is walked again",
        LIB,
        "if m is not None and m.end() not in failed:",
        "if m is not None:",
        GIT_TARGETS,
    ),
    (
        # Killed by the timing tests (exponential).
        "a position that leads nowhere is not recorded",
        LIB,
        "            failed.add(pos)",
        "            pass",
        GIT_TARGETS,
    ),
    (
        # Killed by the 28 KB timing tests: each `git` inside an option run
        # walks the rest of it again (quadratic).
        "each git start gets a fresh record of failed positions",
        LIB,
        "found = self._resolve(text, head.end(), failed)",
        "found = self._resolve(text, head.end(), set())",
        GIT_TARGETS,
    ),
    (
        # Killed by the differential test (`git git reset ...`).
        "after a failed start, the search skips the first character of the next token",
        LIB,
        "pos = head.start() + 1",
        "pos = head.end() + 1",
        GIT_TARGETS,
    ),
    (
        # Killed by the differential test: matches overlap.
        "after a match, the search resumes inside it",
        LIB,
        "            pos = m.end()",
        "            pos = head.end()",
        GIT_TARGETS,
    ),
    (
        "the captured options group starts at `git` instead of after it",
        LIB,
        "spans.append((head.end(), opts_end))",
        "spans.append((head.start(), opts_end))",
        GIT_TARGETS,
    ),
    (
        "the last group of the subcommand pattern is dropped",
        LIB,
        "range(1, self.after.groups + 1)",
        "range(1, self.after.groups)",
        GIT_TARGETS,
    ),
    (
        "a group that did not take part reads as text instead of None",
        LIB,
        "return None if start < 0 else self.string[start:end]",
        "return self.string[start:end]",
        GIT_TARGETS,
    ),
    (
        "search finds nothing",
        LIB,
        "return next(self.finditer(text), None)",
        "return None",
        GIT_TARGETS,
    ),
    (
        # Killed by the differential test (group 0 spans) and the groups test.
        "a match starts after `git` instead of at it",
        LIB,
        "spans = [(head.start(), m.end())]",
        "spans = [(head.end(), m.end())]",
        GIT_TARGETS,
    ),
    (
        # Killed by the differential test: the subcommand is found anywhere later.
        "the subcommand pattern is searched for instead of matched where the options end",
        LIB,
        "m = self.after.match(text, pos)",
        "m = self.after.search(text, pos)",
        GIT_TARGETS,
    ),
    (
        "an option step no longer consumes the separator after the option",
        LIB,
        "re.compile(shape + GIT_SEP)",
        "re.compile(shape)",
        GIT_TARGETS,
    ),
    (
        "a git command is found only at the very start of the text",
        LIB,
        "head = _GIT_HEAD.search(text, pos)",
        "head = _GIT_HEAD.match(text, pos)",
        GIT_TARGETS,
    ),
    (
        "the options group is captured when it was not asked for, and not when it was",
        LIB,
        "if self.capture_opts:",
        "if not self.capture_opts:",
        GIT_TARGETS,
    ),
    (
        # Killed by test_git_invocation_groups_read_like_a_match (`start(2)`).
        "GitMatch.start returns the end",
        LIB,
        "return self._spans[group][0]",
        "return self._spans[group][1]",
        GIT_TARGETS,
    ),
    (
        # Killed by test_git_invocation_groups_read_like_a_match (`end()`).
        "GitMatch.end returns the start",
        LIB,
        "return self._spans[group][1]",
        "return self._spans[group][0]",
        GIT_TARGETS,
    ),
    (
        "long options such as `--no-pager` stop being skipped",
        LIB,
        "        _GIT_OPT_LONG,",
        "",
        GIT_TARGETS,
    ),
    (
        # Killed by test_git_invocation_refuses_a_subcommand_pattern_that_can_start_at_a_separator.
        "a subcommand pattern that can start at a separator is accepted",
        LIB,
        'if any(self.after.match(probe) for probe in (" x", "\\tx", "\\\\x")):',
        "if False:",
        GIT_TARGETS,
    ),
]


# --- CLA_HOOK_T0, the measured pre-main window, and the shared ask reader ------
# Added with the guard-shell-wrappers change. Killing tests are in
# tests/hooks/test_dispatch_lib.py unless named otherwise.
_HOOK_TARGETS = TARGETS + [DEV / "tests" / "hooks" / "test_ask_destructive_git.py"]
MUTANTS += [
    ("a stamp is never read, so every run uses the fixed guess",
     LIB, '    raw = os.environ.get(HOOK_T0_ENV, "")', '    raw = ""', TARGETS),
    ("a comma decimal point is refused",
     LIB, r'if not re.fullmatch(r"\d+(?:[.,]\d+)?", raw):', r'if not re.fullmatch(r"\d+(?:[.]\d+)?", raw):',
     TARGETS),
    ("a comma decimal point is not converted",
     LIB, 'float(raw.replace(",", "."))', "float(raw)", TARGETS),
    ("a stamp in the future is trusted",
     LIB, "if elapsed < -1.0 or elapsed >= HANDLER_TIMEOUT_SECONDS:", "if elapsed >= HANDLER_TIMEOUT_SECONDS:",
     TARGETS),
    ("a stale stamp is trusted",
     LIB, "if elapsed < -1.0 or elapsed >= HANDLER_TIMEOUT_SECONDS:", "if elapsed < -1.0:", TARGETS),
    ("a stamp slightly ahead is refused, not read as zero",
     LIB, "if elapsed < -1.0 or elapsed >= HANDLER_TIMEOUT_SECONDS:",
     "if elapsed < 0.0 or elapsed >= HANDLER_TIMEOUT_SECONDS:", TARGETS),
    ("jitter ahead of the clock adds budget",
     LIB, "    return max(0.0, elapsed)", "    return elapsed", TARGETS),
    ("a measured run reserves nothing after the last hook",
     LIB, "else before + _POST_HOOK_RESERVE_SECONDS", "else before", TARGETS),
    ("a measured run still subtracts the fixed guess",
     LIB, "else before + _POST_HOOK_RESERVE_SECONDS", "else before + _BUDGET_RESERVE_SECONDS", TARGETS),
    ("a measurement is never reported, so the history probes ignore it",
     LIB, "            self.measured = before is not None", "            self.measured = False",
     _HOOK_TARGETS),
    ("an explicit budget is reported as measured",
     LIB, "        self.measured = False\n        if budget_seconds is None:",
     "        self.measured = True\n        if budget_seconds is None:", TARGETS),
    ("extract_ask reads any decision as an ask",
     LIB, 'if not isinstance(nested, dict) or nested.get("permissionDecision") != "ask":',
     "if not isinstance(nested, dict):", TARGETS),
    ("extract_ask drops the default reason",
     LIB, 'or "A guard requested confirmation.")', 'or "")', TARGETS),
]
