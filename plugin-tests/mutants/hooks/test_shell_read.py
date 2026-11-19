"""Mutant batch for the unit tests of `hooks/_shell_read.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_shell_read.py

The shell reading's other batch (`test_dispatch_lib.py`) is killed through the
dispatcher and the guards. This one targets `tests/hooks/test_shell_read.py`
alone, so each kill shows the unit tests catch the break without a guard's help.

Anchors are single lines (the source is CRLF in a Windows checkout).
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]                      # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
SHELL = PLUGIN / "hooks" / "_shell_read.py"
T = [DEV / "tests" / "hooks" / "test_shell_read.py"]

MUTANTS = [
    # --- the wrapper forms and their option words (_body_words) -------------
    ("eval is no longer a wrapper",
     SHELL, r'r"|eval|iex|invoke-expression)(?i:\.exe)?(?=[ \t]|\\\r?\n)"',
     r'r"|iex|invoke-expression)(?i:\.exe)?(?=[ \t]|\\\r?\n)"', T),
    ("an encoded PowerShell command is not decoded for the guards",
     SHELL, 'texts.append(base64.b64decode(value).decode("utf_16_le"))', "pass", T),
    ("-c inside a short-option cluster is not read as -c",
     SHELL, 'string = string or "c" in word[1:]', 'string = string or word == "-c"', T),
    ("-o's value is read as the command",
     SHELL, 'at += 2 if word[-1] in "oO" else 1', "at += 1", T),
    ("--rcfile's value is read as the command",
     SHELL, 'at += 2 if word in ("--rcfile", "--init-file") else 1', "at += 1", T),
    ("after -c every word is the body",
     SHELL, "return words[at:at + 1] if string else words[at:]", "return words[at:]", T),
    ("a pwsh value parameter's value is read as the command",
     SHELL, "at += 2 if any(p.startswith(flag) for p in _PS_VALUE_PARAMS) else 1", "at += 1", T),
    ("cmd's switches stay in the body",
     SHELL, "while at < len(words) and _CMD_SWITCH.fullmatch(words[at]):", "while False:", T),
    ("su's -c value is not the body",
     SHELL, 'if word in ("-c", "--command") and at + 1 < len(words):', "if False:", T),
    ("Invoke-Expression's -Command stays in the body",
     SHELL,
     'return words[1:] if words and "-command".startswith(words[0].lower()) and len(words[0]) > 1 else words',
     "return words", T),
    ("a wrapper's words run past its backtick span",
     SHELL, "wrapper_words = _command_words(part, w.end(), _span_close(scanned, w.start()))",
     "wrapper_words = _command_words(part, w.end())", T),
    # --- heredoc data -------------------------------------------------------
    ("a quoted heredoc's body is read as unquoted",
     SHELL, "            spans.append((nl + 1, end))", "            spans += _unquoted_data(part, nl + 1, end)", T),
    ("an unquoted heredoc's substitutions are data",
     SHELL, "        m = _LIVE_OPEN.search(part, at, b)", "        m = None", T),
    ("a <<- body's tab-indented end is not found",
     SHELL, 'tabs = r"\\t*" if m.group(1) else ""', 'tabs = ""', T),
    ("a heredoc operator inside a string is an operator",
     SHELL, "    for m in _HEREDOC_START.finditer(scanned):", "    for m in _HEREDOC_START.finditer(part):", T),
    # --- remote runners -----------------------------------------------------
    ("no command is a remote runner's",
     SHELL, "    return base in _REMOTE_RUNNERS", "    return False", T),
    ("a prefix command hides the runner behind it",
     SHELL, "while w_at < len(words) and words[w_at] in _RUNNER_PREFIXES:", "while False:", T),
    ("timeout's duration is read as the command word",
     SHELL, 'if prefix == "timeout" and w_at < len(words) and _DURATION.match(words[w_at]):', "if False:", T),
    ("a prefix option's value is read as the command word",
     SHELL, "w_at += 2 if opt[-1] in _PREFIX_VALUE_LETTERS else 1", "w_at += 1", T),
    ("an unknown long prefix option is stepped over",
     SHELL, 'if "=" not in opt:', "if False:", T),
    # --- assignments carried ------------------------------------------------
    ("an earlier assignment is not carried",
     SHELL, 'prefix = "".join("export " + n + "=" + known[n] + "; " for n in used)', 'prefix = ""', T),
    ("every earlier assignment is carried, named or not",
     SHELL, "used = dict.fromkeys(n for n in _NAME_USE.findall(text) if n in known)",
     "used = dict.fromkeys(known)", T),
    ("an assignment after the wrapper is carried",
     SHELL, "while next_assign < len(assigned) and assigned[next_assign][0] < w.start():",
     "while next_assign < len(assigned):", T),
    ("the first value before the wrapper wins",
     SHELL, "            known[name] = value", "            known.setdefault(name, value)", T),
    # --- nesting and caps ---------------------------------------------------
    ("a wrapper past the depth cap is reported complete",
     SHELL, "            if any(_guard_bodies(p) for p in frontier):", "            if False:", T),
    ("the appended-text cap never trips",
     SHELL, "            budget -= sum(map(len, frontier))", "            budget -= 0", T),
    ("the work cap does not bound guard_parts",
     SHELL, "    _WORK_LEFT[0] = _WORK_FACTOR * budget", '    _WORK_LEFT[0] = float("inf")', T),
    ("a body found twice is handed on twice",
     SHELL, "return tuple(b for b in dict.fromkeys(bodies) if b != command), complete",
     "return tuple(b for b in bodies if b != command), complete", T),
    # --- expand -------------------------------------------------------------
    ("expand appends a wrapper body with no git",
     SHELL, "    return [b for b in bodies if _HAS_GIT.search(b)]", "    return bodies", T),
    ("no assignment is ever read",
     SHELL, "found.setdefault(m.group(1), []).append(value)", "pass", T),
    ("only the last value a name is given is tried",
     SHELL, "choices.append(list(dict.fromkeys(values)))", "choices.append(list(dict.fromkeys(values))[-1:])", T),
    ("a quoted flag is not read unquoted",
     SHELL, "values = [value]  # a quoted or escaped flag or refspec", "continue", T),
    ("an unresolved expansion is not reported",
     SHELL, "    return lines, unresolved", "    return lines, False", T),
    ("an operand expansion asks",
     SHELL, 'not operand and raw.startswith("$") and _SINGLE_VAR.fullmatch(raw) is not None',
     'raw.startswith("$") and _SINGLE_VAR.fullmatch(raw) is not None', T),
    ("a git wrapper past the depth cap is not reported",
     SHELL, "            return parts, WRAP_DEPTH_REASON", "            return parts, None", T),
    ("the work cap does not bound expand",
     SHELL, "    _WORK_LEFT[0] = _WORK_FACTOR * (len(command) + _EXPAND_SLACK)", '    _WORK_LEFT[0] = float("inf")', T),
    # --- word helpers -------------------------------------------------------
    ("ANSI-C escapes are not decoded",
     SHELL, "out.append(_ANSI_ESCAPE.sub(_ansi_char, ansi))", "out.append(ansi)", T),
    ("a backslash inside double quotes is kept",
     SHELL, 'out.append(_DOUBLE_ESCAPE.sub(r"\\1", double))', "out.append(double)", T),
    ("an abbreviation must be spelled in full",
     SHELL, 'out = "(?:" + re.escape(char) + out + ")?"', "out = re.escape(char) + out", T),
]
