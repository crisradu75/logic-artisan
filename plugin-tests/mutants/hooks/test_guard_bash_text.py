"""Mutant batch for `tests/hooks/test_guard_bash_text.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_guard_bash_text.py

`hooks/guard-bash-text.py` reads the text of a Bash command and does three things with it: BLOCKS
an unresolved plugin root (exit 2), ASKS before a write outside the checkout through `..`, and
WARNS about a multi-line inline commit or PR message. The mutants below re-break one decision at a
time, grouped by what a break would let through:

- the three verdicts and what each exit/print path carries (`main`);
- what counts as an unresolved root and what silences it (the two regexes, the assignment escape,
  heredoc bodies, comments, quoting);
- what counts as a write target (redirect operators, `tee`, `mkdir`, `cp`/`mv`) and where `..`
  lands (the checkout boundary, `.git` as a file for a linked worktree, absolute / `~` / `$` / drive
  / URL paths);
- what counts as a multi-line message (`git commit -m` in every spelling, `gh pr|issue ...
  --body`), and how the command name is found behind wrappers.

Not in the batch, because no input tells the edit from the original:
- dropping the `(?![A-Za-z0-9_])` after `$CLAUDE_PLUGIN_ROOT` in `_PLACEHOLDER`: the pattern then
  needs `"` or a slash right after the name, and a name character is neither, so
  `$CLAUDE_PLUGIN_ROOT_X/y` stays unmatched either way;
- dropping the `<<<` branch of `_angle`: a here-string then reads as an empty-delimiter heredoc
  operator plus a `<`, and the empty delimiter registers nothing, so the scan comes out the same
  (1,200 random token sequences gave identical verdicts, orig against mutant, 2026-11-19);
- dropping the non-object-payload or non-string-command checks in `main`: the `except Exception`
  that wraps them exits 0 for the same inputs, silently;
- dropping the optional `export ` from the assignment escape: the alternative before it already
  matches `CLAUDE_PLUGIN_ROOT=` after the space that follows `export`;
- a `$x` no longer marking its word quoted, `>&2` read as a write to a file named `2`, an absolute
  path judged as relative, and a path that does not climb judged as an escape: each reaches a
  verdict (a target `2`, `/x`, or a path inside the checkout) that is not "outside" by any input.

Anchors sit within one physical line, or take the file's own line ending, so the batch runs on LF and CRLF checkouts alike. Paths
resolve from this file, never from a developer's absolute path.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]  # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
HOOK = PLUGIN / "hooks" / "guard-bash-text.py"
TARGETS = [DEV / "tests" / "hooks" / "test_guard_bash_text.py"]

_SPEC = [
    # ---- main(): the verdicts -------------------------------------------------------------
    ("a payload without a usable cwd no longer falls back to the process cwd",
     "        if not isinstance(cwd, str) or not cwd:",
     "        if False:"),
    ("an unresolved root is no longer blocked",
     "    if found.placeholders:",
     "    if False:"),
    ("a block no longer exits 2",
     "        return 2",
     "        return 0"),
    ("a block no longer names an outside write found beside it",
     '            parts.append("Also: " + _ask_reason(found))',
     "            pass"),
    ("a block no longer carries the multi-line warning found beside it",
     "            parts.append(_warning(found))",
     "            pass"),
    ("a multi-line message no longer warns",
     "        print(_warning(found), file=sys.stderr)",
     "        pass"),
    ("an outside write is no longer asked about",
     "    if found.outside:\n        print(json.dumps",
     "    if False:\n        print(json.dumps"),
    ("an outside write is denied instead of asked",
     '"permissionDecision": "ask",',
     '"permissionDecision": "deny",'),
    # ---- check(): what is reported ----------------------------------------------------------
    ("an unterminated command is judged instead of ignored",
     "    if not scan.complete:",
     "    if False:"),
    ("a command that assigns the root itself is still blocked",
     "    if scan.placeholders and not _ASSIGNS_ROOT.search(command):",
     "    if scan.placeholders:"),
    ("every write target is reported as outside",
     "            if boundary.escapes(target):",
     "            if True:"),
    # ---- the placeholder and assignment regexes -----------------------------------------
    ("a comparison `$CLAUDE_PLUGIN_ROOT ==` reads as an assignment",
     "[ \\t]*=(?!=)",
     "[ \\t]*="),
    ("the PowerShell `$env:` assignment is no longer recognised",
     "|\\$(?:env:)?CLAUDE_PLUGIN_ROOT",
     "|\\$CLAUDE_PLUGIN_ROOT"),
    # ---- the scan: quoting, comments, heredocs ---------------------------------------------
    ("a comment is read as code even after a word",
     '            if c == "#" and f.word is None:',
     '            if c == "#":'),
    ("a backslash-escaped character is dropped from its word",
     "                w.chars.append(cmd[i + 1 : i + 2])",
     "                pass"),
    ("a quoted heredoc delimiter is read as unquoted",
     "            if not quoted:",
     "            if True:"),
    ("an unquoted heredoc body is never scanned for the root",
     "                self._scan_expanding(start, body_end)",
     "                pass"),
    ("`<<-` no longer strips leading tabs from the terminator",
     '                if (line.lstrip("\\t") if strip else line) == delim:',
     "                if line == delim:"),
    ("a heredoc terminator with a CRLF is not recognised",
     '                if line.endswith("\\r"):',
     "                if False:"),
    ("an `$'...'` string no longer decodes `\\n` as a newline",
     '                    if cmd[j + 1 : j + 2] == "n":',
     "                    if False:"),
    ("a `$((` arithmetic expansion is read as a command substitution",
     '            if cmd.startswith("$((", i):',
     "            if False:"),
    ("a `${...}` is read as plain text",
     '        if nxt == "{":',
     "        if False:"),
    ("an unclosed frame at the end of the command is judged",
     "        if len(stack) > 1:",
     "        if False:"),
    ("a backtick substitution closes on a paren count",
     '            if c == f.closer and (c == "`" or f.parens == 0):',
     "            if c == f.closer and f.parens == 0:"),
    ("a backslash-newline joins no lines",
     '                if cmd.startswith("\\\\\\n", i):',
     "                if False:"),
    ("`&>>` is read as `&>`",
     '                op = "&>>" if cmd.startswith("&>>", i) else "&>"',
     '                op = "&>"'),
    ("`2>` no longer drops the descriptor digits from the words",
     "        if w is not None and not w.quoted and w.value.isdigit():",
     "        if False:"),
    # ---- write targets ----------------------------------------------------------------------
    ("`<>` is no longer a write operator",
     '_WRITE_OPS = frozenset({">", ">>", ">|", "&>", "&>>", "<>", ">&"})',
     '_WRITE_OPS = frozenset({">", ">>", ">|", "&>", "&>>", ">&"})'),
    ("a read redirect reads as a write",
     "            if item.op not in _WRITE_OPS:",
     "            if False:"),
    ("`tee` operands are no longer write targets",
     '    if name == "tee":',
     '    if name == "tee-disabled":'),
    ("`mkdir` operands are no longer write targets",
     '    if name == "mkdir":',
     '    if name == "mkdir-disabled":'),
    ("`mv` is no longer treated like `cp`",
     '    if name in ("cp", "mv"):',
     '    if name in ("cp",):'),
    ("`-t` / `--target-directory` is ignored for cp and mv",
     "        if named:",
     "        if False:"),
    ("a one-operand cp is read as having a destination",
     "        if len(operands) >= 2:",
     "        if len(operands) >= 1:"),
    ("`--` no longer ends the options",
     "            after_dashdash = True",
     "            pass"),
    ("`-` alone is read as an option",
     '        if after_dashdash or v == "-" or not v.startswith("-"):',
     '        if after_dashdash or not v.startswith("-"):'),
    # ---- where `..` lands ---------------------------------------------------------------
    ("a `~` path is judged as relative",
     '        if not path or "://" in path or path.startswith(("/", "~", "$")):',
     '        if not path or "://" in path or path.startswith(("/", "$")):'),
    ("a `$` path is judged as relative",
     '        if not path or "://" in path or path.startswith(("/", "~", "$")):',
     '        if not path or "://" in path or path.startswith(("/", "~")):'),
    ("a URL is judged as a path",
     '        if not path or "://" in path or path.startswith(("/", "~", "$")):',
     '        if not path or path.startswith(("/", "~", "$")):'),
    ("a Windows drive path is judged as relative",
     '        if re.match(r"[A-Za-z]:", path):',
     "        if False:"),
    ("a path that climbs and returns is judged by its first segment",
     "        norm = posixpath.normpath(path)",
     "        norm = path"),
    ("a `..` that stays inside the checkout is reported",
     "        return not _is_inside(resolved, self.root())",
     "        return True"),
    ("the boundary is the cwd, not the checkout that holds it",
     "            self._root = _checkout_root(self.cwd) or os.path.abspath(self.cwd)",
     "            self._root = os.path.abspath(self.cwd)"),
    ("a `.git` file (a linked worktree) is not a checkout marker",
     '        if os.path.exists(os.path.join(d, ".git")):',
     '        if os.path.isdir(os.path.join(d, ".git")):'),
    ("any path is inside any root",
     "    return common == os.path.normcase(root)",
     "    return True"),
    # ---- the command name, behind wrappers -------------------------------------------------
    ("variable assignments are not skipped before the command name",
     "        if _is_assignment(w):",
     "        if False:"),
    ("a quoted `A=b` word is read as an assignment",
     "    return m is not None and (w.plain_prefix is None or m.end() <= w.plain_prefix)",
     "    return m is not None"),
    ("`time`, `nohup`, `!` and friends are not skipped",
     "        if name in _PREFIX_WORDS:",
     "        if False:"),
    ("`env` is not skipped",
     '        elif name == "env":',
     '        elif name == "env-disabled":'),
    ("`env -u NAME` reads its value as the command",
     '                if v in ("-u", "--unset", "-C", "--chdir"):',
     "                if False:"),
    ("`sudo` is not skipped",
     '        elif name == "sudo":',
     '        elif name == "sudo-disabled":'),
    ("a `sudo -u user` value is read as the command",
     "                if len(v) == 2 and v[1] in _SUDO_VALUE_LETTERS:",
     "                if False:"),
    ("`command -v` is read as running the command",
     '                if words[i].value in ("-v", "-V"):',
     "                if False:"),
    ("a Windows extension is not stripped from the command name",
     "    return stem if dot and ext in _EXTENSIONS else base",
     "    return base"),
    ("a directory is not stripped from the command name",
     '    return value.replace("\\\\", "/").rsplit("/", 1)[-1]',
     "    return value"),
    # ---- multi-line messages ------------------------------------------------------------------
    ("git global options with a value are not skipped before the subcommand",
     "            j += 2 if rest[j].value in _GIT_GLOBAL_VALUE_OPTS else 1",
     "            j += 1"),
    ("only `git commit` -m with a real newline warns, not a heredoc",
     "            if any(w.newline or w.heredoc for w in _commit_messages(rest[j + 1 :])):",
     "            if any(w.newline for w in _commit_messages(rest[j + 1 :])):"),
    ("a heredoc message in a commit does not warn",
     "            if any(w.newline or w.heredoc for w in _commit_messages(rest[j + 1 :])):",
     "            if any(w.heredoc for w in _commit_messages(rest[j + 1 :])):"),
    ("`gh issue` is not checked",
     '        if group in ("pr", "issue") and action in _GH_MESSAGE_SUBCOMMANDS:',
     '        if group in ("pr",) and action in _GH_MESSAGE_SUBCOMMANDS:'),
    ("`gh pr view` is checked as if it set a body",
     '        if group in ("pr", "issue") and action in _GH_MESSAGE_SUBCOMMANDS:',
     '        if group in ("pr", "issue"):'),
    ("a gh body in `--body` / `-b` spelling is missed",
     '        if v in ("--body", "-b"):',
     '        if v in ("--body",):'),
    ("`--body=text` is missed",
     '        elif v.startswith("--body="):',
     '        elif v.startswith("--body-disabled="):'),
    ("`-btext` is missed",
     '        elif v.startswith("-b") and not v.startswith("--"):',
     "        elif False:"),
    ("`--message` is missed",
     '            if name == "--message":',
     '            if name == "--message-disabled":'),
    ("a commit option's value is read as the next option",
     "            elif name in _COMMIT_VALUE_LONG and not eq:",
     "            elif False:"),
    ("`-m` is not told from other short options with a value",
     '            if ch in "mFCct":',
     '            if ch in "mFCc":'),
    ("a commit `-m` with an attached value is missed",
     "                    if attached:",
     "                    if False:"),
    ("a commit `-m` with a separate value is missed",
     "                        found.append(args[i])",
     "                        pass"),
    ("`-S` / `-u` optional values swallow the next word",
     '            if ch in "Su":',
     '            if ch in "S":'),
    ("a commit without messages is judged (the command name is not compared)",
     '        if j < len(rest) and rest[j].value == "commit":',
     "        if j < len(rest):"),
    ("the git command name is matched loosely",
     "    if _GIT_NAME.fullmatch(name):",
     "    if _GIT_NAME.match(name):"),
    ("the gh command name is matched loosely",
     "    if _GH_NAME.fullmatch(name) and len(rest) >= 2:",
     "    if _GH_NAME.match(name) and len(rest) >= 2:"),
    ("more than the shown findings are not counted",
     '    more = f", and {len(items) - MAX_NAMED} more" if len(items) > MAX_NAMED else ""',
     '    more = ""'),
    ("the shown findings are not capped",
     "    shown = \", \".join(f\"`{item[:200]}`\" for item in items[:MAX_NAMED])",
     "    shown = \", \".join(f\"`{item[:200]}`\" for item in items)"),
]

# Multi-line anchors take the file's own line ending, so the batch runs on LF and CRLF checkouts.
_NL = "\r\n" if b"\r\n" in HOOK.read_bytes() else "\n"
MUTANTS = [(name, HOOK, old.replace("\n", _NL), new.replace("\n", _NL), TARGETS) for name, old, new in _SPEC]
