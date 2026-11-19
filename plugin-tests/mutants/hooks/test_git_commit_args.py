"""Mutant batch for the unit tests of `hooks/_git_commit_args.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_git_commit_args.py

The reader's other batch (`test_commit_honesty_guards.py`) is killed through
the two guards that use it. This one targets
`tests/hooks/test_git_commit_args.py` alone, so each kill shows the unit tests
catch the break without a guard's help.

Anchors are single lines (the source is CRLF in a Windows checkout).
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]                      # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
ARGS = PLUGIN / "hooks" / "_git_commit_args.py"
T = [DEV / "tests" / "hooks" / "test_git_commit_args.py"]

MUTANTS = [
    # --- read_word ----------------------------------------------------------
    ("inside double quotes every backslash escapes",
     ARGS, "if nxt in '$`\"\\\\':", "if True:", T),
    ("ANSI-C escapes are not decoded",
     ARGS, 'out.append(escapes.get(text[i + 1], "\\\\" + text[i + 1]))', 'out.append("\\\\" + text[i + 1])', T),
    ("a cat heredoc word does not take the body",
     ARGS, "        heredoc = substs[0][1][0]", "        heredoc = None", T),
    ("a word with text around the substitution takes the body",
     ARGS, "if len(substs) == 1 and value == substs[0][0] and len(substs[0][1]) == 1",
     "if len(substs) == 1 and len(substs[0][1]) == 1", T),
    ("one more level of nesting is allowed",
     ARGS, "    if depth > _MAX_DEPTH:", "    if depth > _MAX_DEPTH + 1:", T),
    ("one level less of nesting is allowed",
     ARGS, "    if depth > _MAX_DEPTH:", "    if depth >= _MAX_DEPTH:", T),
    ("an unterminated double quote in a word is read to the end",
     ARGS, '                    raise ParseError("unterminated double quote")', "                    break", T),
    # --- command_words ------------------------------------------------------
    ("a comment does not end the command",
     ARGS, 'if text[i] in _COMMAND_END or text[i] == "#":', "if text[i] in _COMMAND_END:", T),
    ("a line continuation is not a separator",
     ARGS, '        elif text.startswith("\\\\\\n", i):', "        elif False:", T),
    ("a heredoc's fd is dropped",
     ARGS, "            bodies.append((fd, body))", '            bodies.append(("", body))', T),
    ("a <<- body keeps its leading tabs",
     ARGS, '            line = line.lstrip("\\t")', "            pass", T),
    # --- directory_of -------------------------------------------------------
    ("each -C starts again from the cwd",
     ARGS, "directory = os.path.normpath(os.path.join(directory, value))",
     "directory = os.path.normpath(os.path.join(cwd, value))", T),
    ("--git-dir=<path> is not read as naming the repository",
     ARGS, 'if token.split("=", 1)[0] in _REPO_ELSEWHERE:', "if token in _REPO_ELSEWHERE:", T),
    # --- read_commit --------------------------------------------------------
    ("/dev/stdin is not read as stdin",
     ARGS, 'if value in ("-", "/dev/stdin"):', 'if value == "-":', T),
    ("no message means a message in sight",
     ARGS, "commit.message_hidden = True  # the editor, or the commit being amended", "pass", T),
    ("an abbreviated long option is refused",
     ARGS, "hits = [opt for opt in options if opt.startswith(name)]", "hits = []", T),
    ("an ambiguous abbreviation takes the first option",
     ARGS, "return hits[0] if len(hits) == 1 and name else None", "return hits[0] if hits and name else None", T),
    ("a --no- option is refused",
     ARGS, '    if name.startswith("no-"):', "    if False:", T),
    ("--no-allow-empty leaves allow_empty set",
     ARGS, "commit.allow_empty = not negated", "commit.allow_empty = True", T),
    ("--dry-run is not read",
     ARGS, "commit.dry_run = not negated", "commit.dry_run = False", T),
    ("-a is not read as --all",
     ARGS, "                commit.all_files = True", "                pass", T),
    ("an attached short value is not read",
     ARGS, "rest = letters[index + 1:]", 'rest = ""', T),
    ("-S takes no attached value and refuses",
     ARGS, "            if letter in _COMMIT_SHORT_OPTIONAL:", "            if False:", T),
    ("an unknown short flag is accepted",
     ARGS, "            if letter not in _COMMIT_SHORT_FLAGS:", "            if False:", T),
    ("a long option missing its value is accepted",
     ARGS, "return _refuse(commit)  # git: requires a value", "pass", T),
    ("a trailer is read as message",
     ARGS, "commit.trailers.append(value.message)", "commit.messages.append(value.message)", T),
    ("a short option that hides the message does not",
     ARGS, "                    commit.message_hidden = True", "                    pass", T),
    ("pathspecs are dropped",
     ARGS, "            commit.pathspecs.append(token)", "            pass", T),
    # --- read_add -----------------------------------------------------------
    ("-A is not read",
     ARGS, 'all_flag = all_flag or "A" in letters', "all_flag = all_flag", T),
    ("-u is not tracked-only",
     ARGS, 'add.tracked_only = add.tracked_only or "u" in letters', "add.tracked_only = add.tracked_only", T),
    ("-n and -p are accepted",
     ARGS, '        if set(letters) & set("nipe"):', "        if False:", T),
    ("--dry-run and --pathspec-from-file are accepted",
     ARGS, "            if option in _ADD_NOTHING_KNOWN and not negated:", "            if False:", T),
    ("a value option's separate value is read as a pathspec",
     ARGS, "            if option in _ADD_LONG_VALUED and value_text is None and not negated:", "            if False:", T),
    ("an exclude pathspec is a positive one",
     ARGS, 'positive = [spec for spec in add.pathspecs if not spec.startswith((":!", ":^", ":(exclude"))]',
     "positive = list(add.pathspecs)", T),
    # --- find_invocations ---------------------------------------------------
    ("a refused invocation is kept",
     ARGS, "        if not invocation.refused:", "        if True:", T),
    ("text inside a heredoc body is read as a command",
     ARGS, "            continue  # text inside a heredoc body is data, not a command", "            pass", T),
    ("an invocation's consumed text is read again",
     ARGS, "        consumed = invocation.end", "        consumed = match.end()", T),
    ("unreadable text raises out of the walk",
     ARGS, "        except ParseError:", "        except ZeroDivisionError:", T),
    ("GIT_DIR= keeps the directory",
     ARGS, "base: str | None = None if _GIT_ENV_REPO.search(command) else cwd", "base: str | None = cwd", T),
]
