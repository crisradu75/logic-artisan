"""Mutant batch for the command-substitution handling in `strip_quoted_spans`
and the `GitInvocation` matcher (`hooks/_shell_text.py`), then for the budget
stamp and the runner in `hooks/_dispatch_lib.py`, and the shell reading in
`hooks/_shell_read.py`.

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
# The quote stripping and the git matcher moved out of `_dispatch_lib.py`.
TEXT = PLUGIN / "hooks" / "_shell_text.py"
DISPATCH = PLUGIN / "hooks" / "dispatch-bash-pretooluse.py"
SHELL = PLUGIN / "hooks" / "_shell_read.py"
# The flag tables moved out of `ask-destructive-git.py` into this file.
ASK = PLUGIN / "hooks" / "_destructive_git_rules.py"
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
        TEXT,
        "re.sub(r'\"[^\"]*\"', _double_quoted, stripped)",
        "re.sub(r'\"[^\"]*\"', _placeholder, stripped)",
        TARGETS,
    ),
    (
        # Killed by the `$(...)` ask-cases (backtick cases still pass).
        "the $(...) branch never fires, so only backtick bodies stay visible",
        TEXT,
        'if ch == "$" and text.startswith("$(", i):',
        'if False and text.startswith("$(", i):',
        TARGETS,
    ),
    (
        # Killed by the backtick-in-double-quotes ask-case.
        "the backtick branch never fires inside double quotes",
        TEXT,
        'elif ch == "`":',
        "elif False:",
        TARGETS,
    ),
    (
        # Killed by the escaped-substitution silent cases.
        "an escaped \\$( or \\` is treated as an executed substitution",
        TEXT,
        'if ch == "\\\\":',
        "if False:",
        TARGETS,
    ),
    (
        # Killed by the `$(date) then git reset --hard` silent case: without the
        # closing-paren count the body runs to the end of the span.
        "the $(...) body never closes, so prose after it is exposed",
        TEXT,
        'depth += (text[j] == "(") - (text[j] == ")")',
        'depth += (text[j] == "(")',
        TARGETS,
    ),
    (
        # Killed by the commit/PR-body silent cases: those bodies would ask.
        "heredoc bodies are no longer blanked before the quote passes",
        TEXT,
        "    stripped = _blank_heredoc_bodies(cmd)",
        "    stripped = cmd",
        TARGETS,
    ),
    (
        # Killed by the `; git reset --hard` after the message: the WHOLE command
        # must match, not just its start.
        "the message command only has to match at the start of the command",
        TEXT,
        "message = _MESSAGE_COMMAND.fullmatch(cmd)",
        "message = _MESSAGE_COMMAND.match(cmd)",
        TARGETS,
    ),
    (
        # Killed by the `git commit -m $(cat <<'EOF' ... )"` visible case: a
        # substitution NOT wrapped in double quotes has its output run.
        "the message shape no longer requires a double quote before $(",
        TEXT,
        r'''rf"(?: {_ARG})* \"\$\(cat <<''',
        r'''rf"(?: {_ARG})* \$\(cat <<''',
        TARGETS,
    ),
    (
        # Killed by the `echo "$(cat <<'EOF'` visible case.
        "echo counts as a message verb",
        TEXT,
        'r"(?:git (?:commit|tag|notes)|gh (?:pr',
        'r"(?:echo|git (?:commit|tag|notes)|gh (?:pr',
        TARGETS,
    ),
    (
        # Killed by the `-m "a | b"` visible case: a double-quoted word may not
        # carry shell syntax.
        "a double-quoted word may carry a pipe",
        TEXT,
        r'''_DQ = r"\"[A-Za-z0-9 ._,:/()#@%+=~-]*\""''',
        r'''_DQ = r"\"[A-Za-z0-9 ._,:/()#@%+=~|-]*\""''',
        TARGETS,
    ),
    (
        # Killed by the `git commit -m x # "$(cat` visible case (a comment).
        "a bare word may be a comment marker",
        TEXT,
        '_W = r"[A-Za-z0-9_.,:=@+%~/-]+"',
        '_W = r"[A-Za-z0-9_.,:=@+%~/#-]+"',
        TARGETS,
    ),
    (
        # Killed by the single-quote visible case (`git commit -m 'a "$(cat`).
        "a bare word may open a single quote",
        TEXT,
        '_W = r"[A-Za-z0-9_.,:=@+%~/-]+"',
        "_W = r\"[A-Za-z0-9_.,:=@+%~/'-]+\"",
        TARGETS,
    ),
    (
        # Killed by the early-terminator case: the shell ends the heredoc at the
        # FIRST line equal to the word.
        "a body line equal to the delimiter no longer ends the body",
        TEXT,
        r'''r"(?P<body>(?:(?!(?P=w))[^\n]*\n)*)"''',
        r'''r"(?P<body>(?:[^\n]*\n)*?)"''',
        TARGETS,
    ),
    (
        # Killed by the `EOF)` / `EOFx)` cases: inside $( ) bash ends the heredoc at
        # a line that only STARTS with the word.
        "only a line exactly equal to the delimiter ends the body",
        TEXT,
        r'''r"(?P<body>(?:(?!(?P=w))[^\n]*\n)*)"''',
        r'''r"(?P<body>(?:(?!(?P=w)\r?\n)[^\n]*\n)*)"''',
        TARGETS,
    ),
    (
        # Killed by the quoted-backtick case (`echo ' ` '; git reset --hard; ...`).
        "backticks are paired in a body that contains quotes",
        TEXT,
        """    if "'" in body or '"' in body:""",
        "    if False:",
        TARGETS,
    ),
    (
        # Killed by the `&& bash x.sh` visible case.
        "bash is allowed as a trailing command",
        TEXT,
        'rf"(?: && (?:git (?:status|push|add|log|diff|show|fetch|pull)"',
        'rf"(?: && (?:bash|git (?:status|push|add|log|diff|show|fetch|pull)"',
        TARGETS,
    ),
    (
        # Killed by the `$SHELL`/`$0` cases through `_runs_an_interpreter`.
        "$SHELL and $0 no longer count as interpreters",
        TEXT,
        "    if _SHELL_VAR.search(text):",
        "    if False:",
        TARGETS,
    ),
    (
        # Killed by the `sh <<'EOF'` + backtick ask-case.
        "an interpreter word no longer keeps Markdown-span blanking off",
        TEXT,
        "    if _runs_an_interpreter(cmd[: nl + 1] + cmd[body_end:]):",
        "    if False:",
        TARGETS,
    ),
    (
        # Killed by the path-form interpreter case below.
        "an interpreter given by path is no longer recognised",
        TEXT,
        'base = word.replace("\\\\", "/").rsplit("/", 1)[-1].lower()',
        "base = word.lower()",
        TARGETS,
    ),
    (
        # Killed by the `.exe` case below.
        "an interpreter with an .exe suffix is no longer recognised",
        TEXT,
        "            if base.endswith(ext):",
        "            if False:",
        TARGETS,
    ),
    (
        # Killed by the unquoted-first-heredoc ask-case: an earlier `<<` may make
        # the quoted one a fake.
        "an earlier heredoc operator no longer disqualifies the later one",
        TEXT,
        '    if cmd.find("<<") != first.start():',
        "    if False:",
        TARGETS,
    ),
    (
        # Killed by `ls # cat <<'EOF'` + a backtick command line.
        "a comment marker before the operator no longer keeps the body visible",
        TEXT,
        'for ch in ("#", "`", "\\\\"):',
        'for ch in ("`", "\\\\"):',
        TARGETS,
    ),
    (
        # Killed by "echo `cat <<'EOF'" + a backtick command line.
        "a backtick before the operator no longer keeps the body visible",
        TEXT,
        'for ch in ("#", "`", "\\\\"):',
        'for ch in ("#", "\\\\"):',
        TARGETS,
    ),
    (
        # Killed by the stray single quote before the operator case.
        "a stray single quote before the operator no longer keeps the body visible",
        TEXT,
        "    if (head.count(\"'\") - (2 if first.group(1) else 0)) % 2 or (",
        "    if False or (",
        TARGETS,
    ),
    (
        # Killed by test_strip_quoted_spans_blanks_nothing_past_the_operator_and_line_caps.
        "the operator-count cap is gone",
        TEXT,
        "if not ops or len(_ANY_HEREDOC.findall(cmd)) > _HEREDOC_MAX_OPS:",
        "if not ops:",
        TARGETS,
    ),
    (
        # Killed by the same test (5000-char operator line).
        "the operator-line length cap is gone",
        TEXT,
        "> _HEREDOC_MAX_LINE:",
        "> 10**9:",
        TARGETS,
    ),
    (
        # Killed by test_strip_quoted_spans_keeps_line_structure_and_crlf_of_a_blanked_body.
        "blanking a heredoc body also blanks its line breaks",
        TEXT,
        '        if out[i] not in "\\r\\n":',
        "        if True:",
        TARGETS,
    ),
    (
        # Killed by the "$body" silent case: Markdown spans in a plain-quoted
        # body stay blanked, as on main.
        "backtick spans in a plain-quoted body are no longer blanked",
        TEXT,
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
        TEXT,
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
        TEXT,
        "_GIT_HEAD = re.compile(GIT_CMD + GIT_SEP)",
        '_GIT_HEAD = re.compile(r"git" + GIT_SEP)',
        GIT_TARGETS,
    ),
    (
        "`-c k=v` / `-C dir` stop taking their value, so the subcommand after "
        "one is never reached",
        TEXT,
        "        _GIT_OPT_VALUED,",
        "",
        GIT_TARGETS,
    ),
    (
        "`--work-tree <path>` and its siblings stop taking a space-separated value",
        TEXT,
        '        _GIT_OPT_NAMED + GIT_SEP + r"\\S+",',
        "",
        GIT_TARGETS,
    ),
    (
        # Killed by the differential test: when both readings reach a
        # subcommand the regex took the value-first one, and the tail differs.
        "a named option is read as value-less before it is read with a value",
        TEXT,
        '        _GIT_OPT_NAMED + GIT_SEP + r"\\S+",',
        '        _GIT_OPT_NAMED, _GIT_OPT_NAMED + GIT_SEP + r"\\S+",',
        GIT_TARGETS,
    ),
    (
        "a bare short flag (`-p`) stops being skipped",
        TEXT,
        "        _GIT_OPT_SHORT,",
        "",
        GIT_TARGETS,
    ),
    (
        "the last step (long options such as `--no-pager`) is never tried",
        TEXT,
        "if step < len(_GIT_OPT_STEPS):",
        "if step < len(_GIT_OPT_STEPS) - 1:",
        GIT_TARGETS,
    ),
    (
        "every other step is skipped",
        TEXT,
        "frame[1] = step + 1",
        "frame[1] = step + 2",
        GIT_TARGETS,
    ),
    (
        # Killed by the timing tests: every split is tried again (exponential).
        "a position already ruled out is walked again",
        TEXT,
        "if m is not None and m.end() not in failed:",
        "if m is not None:",
        GIT_TARGETS,
    ),
    (
        # Killed by the timing tests (exponential).
        "a position that leads nowhere is not recorded",
        TEXT,
        "            failed.add(pos)",
        "            pass",
        GIT_TARGETS,
    ),
    (
        # Killed by the 28 KB timing tests: each `git` inside an option run
        # walks the rest of it again (quadratic).
        "each git start gets a fresh record of failed positions",
        TEXT,
        "found = self._resolve(text, head.end(), failed)",
        "found = self._resolve(text, head.end(), set())",
        GIT_TARGETS,
    ),
    (
        # Killed by the differential test (`git git reset ...`).
        "after a failed start, the search skips the first character of the next token",
        TEXT,
        "pos = head.start() + 1",
        "pos = head.end() + 1",
        GIT_TARGETS,
    ),
    (
        # Killed by the differential test: matches overlap.
        "after a match, the search resumes inside it",
        TEXT,
        "            pos = m.end()",
        "            pos = head.end()",
        GIT_TARGETS,
    ),
    (
        "the captured options group starts at `git` instead of after it",
        TEXT,
        "spans.append((head.end(), opts_end))",
        "spans.append((head.start(), opts_end))",
        GIT_TARGETS,
    ),
    (
        "the last group of the subcommand pattern is dropped",
        TEXT,
        "range(1, self.after.groups + 1)",
        "range(1, self.after.groups)",
        GIT_TARGETS,
    ),
    (
        "a group that did not take part reads as text instead of None",
        TEXT,
        "return None if start < 0 else self.string[start:end]",
        "return self.string[start:end]",
        GIT_TARGETS,
    ),
    (
        "search finds nothing",
        TEXT,
        "return next(self.finditer(text), None)",
        "return None",
        GIT_TARGETS,
    ),
    (
        # Killed by the differential test (group 0 spans) and the groups test.
        "a match starts after `git` instead of at it",
        TEXT,
        "spans = [(head.start(), m.end())]",
        "spans = [(head.end(), m.end())]",
        GIT_TARGETS,
    ),
    (
        # Killed by the differential test: the subcommand is found anywhere later.
        "the subcommand pattern is searched for instead of matched where the options end",
        TEXT,
        "m = self.after.match(text, pos)",
        "m = self.after.search(text, pos)",
        GIT_TARGETS,
    ),
    (
        "an option step no longer consumes the separator after the option",
        TEXT,
        "re.compile(shape + GIT_SEP)",
        "re.compile(shape)",
        GIT_TARGETS,
    ),
    (
        "a git command is found only at the very start of the text",
        TEXT,
        "head = _GIT_HEAD.search(text, pos)",
        "head = _GIT_HEAD.match(text, pos)",
        GIT_TARGETS,
    ),
    (
        "the options group is captured when it was not asked for, and not when it was",
        TEXT,
        "if self.capture_opts:",
        "if not self.capture_opts:",
        GIT_TARGETS,
    ),
    (
        # Killed by test_git_invocation_groups_read_like_a_match (`start(2)`).
        "GitMatch.start returns the end",
        TEXT,
        "return self._spans[group][0]",
        "return self._spans[group][1]",
        GIT_TARGETS,
    ),
    (
        # Killed by test_git_invocation_groups_read_like_a_match (`end()`).
        "GitMatch.end returns the start",
        TEXT,
        "return self._spans[group][1]",
        "return self._spans[group][0]",
        GIT_TARGETS,
    ),
    (
        "long options such as `--no-pager` stop being skipped",
        TEXT,
        "        _GIT_OPT_LONG,",
        "",
        GIT_TARGETS,
    ),
    (
        # Killed by test_git_invocation_refuses_a_subcommand_pattern_that_can_start_at_a_separator.
        "a subcommand pattern that can start at a separator is accepted",
        TEXT,
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
    # --- The Bash dispatcher hands each guard the parts `_shell_read` reads ---
    ("no guard reads a wrapper's body",
     DISPATCH, "        inputs = [stdin_text] + ([] if filename in _READS_COMMAND_ONLY else part_inputs)",
     "        inputs = [stdin_text]", TARGETS),
    ("the cd guard reads a wrapper's own shell",
     DISPATCH, '_READS_COMMAND_ONLY = frozenset({"block-cd-in-bash.py", "ask-destructive-git.py", "warn-lossy-merge-resolution.py"})',
     '_READS_COMMAND_ONLY = frozenset({"ask-destructive-git.py", "warn-lossy-merge-resolution.py"})', TARGETS),
    ("parts past the scan cap are read anyway",
     DISPATCH, "    if len(command) + sum(len(p) for p in extra) > MAX_SCANNED_COMMAND_CHARS:",
     "    if False:", TARGETS),
    ("the command's own length is left out of the scan cap",
     DISPATCH, "    if len(command) + sum(len(p) for p in extra) > MAX_SCANNED_COMMAND_CHARS:",
     "    if sum(len(p) for p in extra) > MAX_SCANNED_COMMAND_CHARS:", TARGETS),
    ("a reading that raises crashes the dispatcher",
     DISPATCH, "    except Exception as exc:  # noqa: BLE001 -- see the docstring",
     "    except ValueError as exc:  # noqa: BLE001 -- see the docstring", TARGETS),
    ("a reading that raises is not asked about",
     DISPATCH, '        return [], _unread_parts_ask(f"reading those bodies failed',
     '        return [], None and _unread_parts_ask(f"reading those bodies failed', TARGETS),
    ("parts over the scan cap are dropped silently",
     DISPATCH, "        return [], _unread_parts_ask(\n",
     "        return [], None and _unread_parts_ask(\n", TARGETS),
    ("a reading stopped at a cap is not asked about",
     DISPATCH, "    return inputs, None if complete else _unread_parts_ask(",
     "    return inputs, None if True else _unread_parts_ask(", TARGETS),
    ("a reading stopped at a cap hands on nothing",
     DISPATCH, "    return inputs, None if complete else _unread_parts_ask(",
     "    return [], None if complete else _unread_parts_ask(", TARGETS),
    ("an unread-parts ask is dropped",
     DISPATCH, "    asks: list[str] = [unread_parts] if unread_parts else []",
     "    asks: list[str] = []", TARGETS),
    # `run_hook_file_each`
    ("a hook that cannot load is not reported when it has parts",
     LIB, '        yield run_hook_file(filename, stdin_texts[0] if stdin_texts else "")',
     "        pass", TARGETS),
    ("only the command is run, never a part",
     LIB, "    for text in stdin_texts:", "    for text in stdin_texts[:1]:", TARGETS),
    # `_shell_read`'s reading for the guards
    ("heredoc text is read as a command",
     SHELL, "        if h >= 0 and w.start() < data[h][1]:", "        if False:", TARGETS),
    ("a quoted heredoc's body is read as unquoted",
     SHELL, "        if d.group(4) is None:", "        if False:", TARGETS),
    ("an unquoted heredoc's body is all command",
     SHELL, "            spans += _unquoted_data(part, nl + 1, end)", "            pass", TARGETS),
    ("an unquoted heredoc delimiter is not recognised",
     SHELL, "|([A-Za-z_][A-Za-z0-9_]*)\"\"\"", "|(?!)([A-Za-z_][A-Za-z0-9_]*)\"\"\"", TARGETS),
    ("a heredoc body runs to the end of the text",
     SHELL, "        end = close.start() if close else len(part)", "        end = len(part)", TARGETS),
    ("an operator inside a body opens another",
     SHELL, "        done = end", "        done = 0", TARGETS),
    ("a <<- body's tab-indented end is not found",
     SHELL, '        tabs = r"\\t*" if m.group(1) else ""', '        tabs = ""', TARGETS),
    ("an escaped backtick opens a live span",
     SHELL, '        if m.group().startswith("\\\\"):', "        if False:", TARGETS),
    ("a $(...) in an unquoted body is data",
     SHELL, '        if m.group() == "$(":', '        if m.group() == "$(" and False:', TARGETS),
    ("an unclosed $( ends at once",
     SHELL, "            end = _paren_close(part).get(m.start() + 1, b - 1) + 1",
     "            end = _paren_close(part).get(m.start() + 1, m.start()) + 1", TARGETS),
    ("a backtick span never closes",
     SHELL, '            while t is not None and t.group() != "`":', "            while t is not None:", TARGETS),
    ("the text before a live span is not data",
     SHELL, "        data.append((start, m.start()))", "        pass", TARGETS),
    ("the text after the last live span is not data",
     SHELL, "    data.append((start, b))", "    pass", TARGETS),
    ("a remote runner's wrapper is read as local",
     SHELL, "        if _remote(scanned, w.start()):", "        if False:", TARGETS),
    ("a remote runner is found only at the start of the line",
     SHELL, "    while pos > 0 and scanned[pos - 1] not in _SEGMENT_STOP:", "    while pos > 0:", TARGETS),
    ("ssh is not a remote runner",
     SHELL, '_REMOTE_RUNNERS = frozenset({"docker", "podman", "nerdctl", "kubectl", "oc", "ssh"})',
     '_REMOTE_RUNNERS = frozenset({"docker", "podman", "nerdctl", "kubectl", "oc"})', TARGETS),
    ("the wrapper's option words stay in its body",
     SHELL, '        texts = [" ".join(_body_words(w.group().split(".")[0], unquoted))]',
     '        texts = [" ".join(unquoted)]', TARGETS),
    ("after -c every word is the body",
     SHELL, "    return words[at:at + 1] if string else words[at:]", "    return words[at:]", TARGETS),
    ("-lc is not read as carrying -c",
     SHELL, '            string = string or "c" in word[1:]', '            string = string or word == "-c"', TARGETS),
    ("-o's value is read as the command",
     SHELL, '            at += 2 if word[-1] in "oO" else 1', "            at += 1", TARGETS),
    ("--rcfile's value is read as the command",
     SHELL, '            at += 2 if word in ("--rcfile", "--init-file") else 1', "            at += 1", TARGETS),
    ("-- is read as the command",
     SHELL, '        if word == "--":', '        if word == "--x":', TARGETS),
    ("pwsh's -Command stays in the body",
     SHELL, '            if "-command".startswith(flag) or flag == "-file"', '            if False', TARGETS),
    ("a pwsh value parameter's value is read as the command",
     SHELL, "            at += 2 if any(p.startswith(flag) for p in _PS_VALUE_PARAMS) else 1", "            at += 1", TARGETS),
    ("pwsh's raw -EncodedCommand text is a body",
     SHELL, "                return []  # the decoded body is read on its own", "                return words", TARGETS),
    ("cmd's switches stay in the body",
     SHELL, "        while at < len(words) and _CMD_SWITCH.fullmatch(words[at]):", "        while False:", TARGETS),
    ("su's -c value is not the body",
     SHELL, '            if word in ("-c", "--command") and at + 1 < len(words):', "            if False:", TARGETS),
    ("Invoke-Expression's -Command stays in the body",
     SHELL, '        return words[1:] if words and "-command".startswith(words[0].lower()) and len(words[0]) > 1 else words',
     "        return words", TARGETS),
    ("a wrapper's words run past its backtick span",
     SHELL, "        wrapper_words = _command_words(part, w.end(), _span_close(scanned, w.start()))",
     "        wrapper_words = _command_words(part, w.end())", TARGETS),
    ("an earlier assignment is not inherited",
     SHELL, '            prefix = "".join("export " + n + "=" + known[n] + "; " for n in used)',
     '            prefix = ""', TARGETS),
    ("every earlier assignment is carried, named or not",
     SHELL, "            used = dict.fromkeys(n for n in _NAME_USE.findall(text) if n in known)",
     "            used = dict.fromkeys(known)", TARGETS),
    ("an assignment after the wrapper is inherited",
     SHELL, "        while next_assign < len(assigned) and assigned[next_assign][0] < w.start():",
     "        while next_assign < len(assigned):", TARGETS),
    ("a later assignment does not replace an earlier one",
     SHELL, "            known.pop(name, None)\n            known[name] = value",
     "            known.setdefault(name, value)", TARGETS),
    ("a nested wrapper's body is not read",
     SHELL, "            frontier = [b for p in frontier for b in _guard_bodies(p)]",
     "            frontier = [b for p in frontier for b in _guard_bodies(p)] if not found else []", TARGETS),
    ("the appended text cap never trips",
     SHELL, "            budget -= sum(map(len, frontier))", "            budget -= 0", TARGETS),
    ("text past the appended cap is reported complete",
     SHELL, "            if budget < 0:\n                return found, False", "            if budget < 0:\n                return found, True", TARGETS),
    ("the work cap is reported complete",
     SHELL, "    except _OverBudget:  # past the work cap: what was found so far\n        return found, False",
     "    except _OverBudget:  # past the work cap: what was found so far\n        return found, True", TARGETS),
    ("the work cap does not bound the reading",
     SHELL, "    _WORK_LEFT[0] = _WORK_FACTOR * budget", '    _WORK_LEFT[0] = float("inf")', TARGETS),
    ("a body found twice is handed on twice",
     SHELL, "    return tuple(b for b in dict.fromkeys(bodies) if b != command), complete",
     "    return tuple(b for b in bodies if b != command), complete", TARGETS),
    # review round 2: a wrapper past the depth cap makes the reading incomplete
    ("a wrapper past the depth cap is reported complete",
     SHELL, "            if any(_guard_bodies(p) for p in frontier):\n                return found, False",
     "            if any(_guard_bodies(p) for p in frontier):\n                return found, True", TARGETS),
    # review round 2: only the command word makes a command remote
    ("a runner's name anywhere in the command makes it remote",
     SHELL, "    if w_at >= len(words):\n        return False\n",
     "    if any(w.rsplit('/', 1)[-1] in _REMOTE_RUNNERS for w in words):\n        return True\n    if w_at >= len(words):\n        return False\n", TARGETS),
    ("a prefix command hides the runner behind it",
     SHELL, "    while w_at < len(words) and words[w_at] in _RUNNER_PREFIXES:",
     "    while False and w_at < len(words) and words[w_at] in _RUNNER_PREFIXES:", TARGETS),
    ("a prefix option's value is read as the command word",
     SHELL, "                w_at += 2 if opt[-1] in _PREFIX_VALUE_LETTERS else 1", "                w_at += 1", TARGETS),
    ("an unknown long prefix option is stepped over",
     SHELL, "                    return False  # a long option whose value this cannot see: read the body",
     "                    pass", TARGETS),
    ("timeout's duration is read as the command word",
     SHELL, "        if prefix == \"timeout\" and w_at < len(words) and _DURATION.match(words[w_at]):",
     "        if False:", TARGETS),
    ("an assignment is read as the command word",
     SHELL, "    while w_at < len(words) and _ASSIGNMENT_WORD.match(words[w_at]):\n        w_at += 1\n",
     "", TARGETS),
]
