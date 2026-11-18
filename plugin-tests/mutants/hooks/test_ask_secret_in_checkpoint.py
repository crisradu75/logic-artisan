"""Mutant batch for `tests/hooks/test_ask_secret_in_checkpoint.py` -- the enforcing ask
guard over a secret-shaped string written into a committed briefing under `cla.io/`,
in `ask-secret-in-checkpoint.py`.

Run:
    python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_ask_secret_in_checkpoint.py

Every mutant edits the hook, the Edit/Write dispatcher or `_dispatch_lib.py`,
never a test. The hook mutants re-break one line each, and several decisions on the
lines that carry more than one (a pattern's prefix, its boundaries and its
body check; the path split; the scope test): the briefing directories, the placeholder words, the cap on named findings, the three
character-class checks, each key pattern, its boundaries and its check, the private-key and JWT
shapes, the URL pattern and each placeholder rule, the path scope, the scan
loop, line numbering and ordering, the reason text, the input handling, the
fail-open catch and the ask payload. The dispatcher mutants re-break the hook's
place in the list and its enforcing tier; one more breaks its budget entry.

Deliberately absent, because no correct input can tell them from the real code:
- `bisect_left` against `bisect_right` in the line numbering. A match never
  starts on a newline, so the two return the same index.
- `>= 4` against `>= 3` in `_varied`. A body of three distinct characters in an
  AWS key shape is no more a placeholder than one of four; the batch pins the
  rule against two (`XY` repeated) instead.
- the connection URL's opening lookbehind. A scheme with a letter in front is
  still a scheme, so finditer finds the same password without it, and the scan
  stays linear either way (the scheme is at most 32 characters, so at most 32
  starts reach any one `://`). It only spares those repeat starts.
- the `return False` lines of `_real_password` are each pinned through their
  `if` condition, not separately: removing the condition and removing the
  return are the same planted bug.

Each anchor occurs once in its file; checked by hand when the batch was written,
in a scratch copy of the tree with bytecode writing off, not with mutate.py.

Paths resolve from this file's own location, never an absolute developer path.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]          # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
HOOK = PLUGIN / "hooks" / "ask-secret-in-checkpoint.py"
GUARD = DEV / "tests" / "hooks" / "test_ask_secret_in_checkpoint.py"
TARGETS = [GUARD]
DISPATCHER = PLUGIN / "hooks" / "dispatch-edit-write-pretooluse.py"
LIB = PLUGIN / "hooks" / "_dispatch_lib.py"
DISPATCH_TARGETS = [
    GUARD,
    DEV / "tests" / "hooks" / "test_dispatch.py",
    DEV / "tests" / "hooks" / "test_hooks_wiring.py",
]

MUTANTS = [
    # ---- scope and tables ----------------------------------------------------
    (
        "feedback/ is no longer a briefing directory",
        HOOK,
        '_BRIEFING_DIRS = frozenset({"checkpoints", "decisions", "feedback", "lessons-learned"})',
        '_BRIEFING_DIRS = frozenset({"checkpoints", "decisions", "lessons-learned"})',
        TARGETS,
    ),
    (
        "`password` is no longer a placeholder word",
        HOOK,
        '    "password", "passwd", "pass", "pwd",',
        '    "passwd", "pass", "pwd",',
        TARGETS,
    ),
    (
        "one more finding is named before the rest are counted",
        HOOK,
        "_MAX_NAMED = 10",
        "_MAX_NAMED = 11",
        TARGETS,
    ),
    # ---- the character-class checks ------------------------------------------
    (
        "a key body needs no upper case",
        HOOK,
        "        any(c.isupper() for c in body)\n        and",
        "        True\n        and",
        TARGETS,
    ),
    (
        "a key body needs no lower case",
        HOOK,
        "        and any(c.islower() for c in body)",
        "        and True",
        TARGETS,
    ),
    (
        "a key body needs no digit",
        HOOK,
        "        and any(c.isdigit() for c in body)\n    )",
        "        and True\n    )",
        TARGETS,
    ),
    (
        "a Slack token needs no digit",
        HOOK,
        "def _has_digit(body: str) -> bool:\n    return any(c.isdigit() for c in body)",
        "def _has_digit(body: str) -> bool:\n    return True",
        TARGETS,
    ),
    (
        "an AWS body of two repeated characters counts as a key",
        HOOK,
        "    return len(set(body)) >= 4",
        "    return len(set(body)) >= 2",
        TARGETS,
    ),
    # ---- the URL password placeholders ---------------------------------------
    (
        "a {password} placeholder counts as a password",
        HOOK,
        '    if password[0] + password[-1] in ("<>", "{}"):',
        '    if password[0] + password[-1] in ("<>",):',
        TARGETS,
    ),
    (
        "a ${VAR} placeholder counts as a password",
        HOOK,
        '    if password.startswith("${") or re.fullmatch(',
        '    if re.fullmatch(',
        TARGETS,
    ),
    (
        "a $VAR placeholder counts as a password",
        HOOK,
        r'or re.fullmatch(r"\$[A-Za-z_][A-Za-z0-9_]*", password):',
        r'or False:',
        TARGETS,
    ),
    (
        "a password of one repeated character counts as a password",
        HOOK,
        "    if len(set(password)) == 1:",
        "    if False:",
        TARGETS,
    ),
    (
        "a placeholder word in capitals counts as a password",
        HOOK,
        "    if password.lower() in _PLACEHOLDER_WORDS:",
        "    if password in _PLACEHOLDER_WORDS:",
        TARGETS,
    ),
    (
        "a password equal to the user name counts as a password",
        HOOK,
        "    return password != user",
        "    return True",
        TARGETS,
    ),
    # ---- the key patterns ----------------------------------------------------
    (
        "an ASIA session key ID is no longer an AWS key",
        HOOK,
        "(?:AKIA|ASIA)(?P<body>",
        "(?:AKIA)(?P<body>",
        TARGETS,
    ),
    (
        "an AWS key with a placeholder body asks",
        HOOK,
        "        _varied,\n",
        "        None,\n",
        TARGETS,
    ),
    (
        "only ghp_ GitHub tokens are found",
        HOOK,
        "gh[pousr]_(?P<body>",
        "ghp_(?P<body>",
        TARGETS,
    ),
    (
        "a GitHub token with a placeholder body asks",
        HOOK,
        "gh[pousr]_(?P<body>[A-Za-z0-9]{30,})\"),\n        _mixed,",
        "gh[pousr]_(?P<body>[A-Za-z0-9]{30,})\"),\n        None,",
        TARGETS,
    ),
    (
        "a fine-grained token's body must be longer than real ones are",
        HOOK,
        "github_pat_(?P<body>[A-Za-z0-9_]{30,})",
        "github_pat_(?P<body>[A-Za-z0-9_]{90,})",
        TARGETS,
    ),
    (
        "a fine-grained token with a placeholder body asks",
        HOOK,
        "github_pat_(?P<body>[A-Za-z0-9_]{30,})\"),\n        _mixed,",
        "github_pat_(?P<body>[A-Za-z0-9_]{30,})\"),\n        None,",
        TARGETS,
    ),
    (
        "the Anthropic prefix is misspelled",
        HOOK,
        "sk-ant-(?P<body>",
        "sk-anth-(?P<body>",
        TARGETS,
    ),
    (
        "an Anthropic key with a placeholder body asks",
        HOOK,
        "sk-ant-(?P<body>[A-Za-z0-9_-]{20,})\"),\n        _mixed,",
        "sk-ant-(?P<body>[A-Za-z0-9_-]{20,})\"),\n        None,",
        TARGETS,
    ),
    (
        "an Anthropic key is also named as an OpenAI key",
        HOOK,
        "sk-(?!ant-)(?P<body>",
        "sk-(?P<body>",
        TARGETS,
    ),
    (
        "a kebab-case slug after sk- asks",
        HOOK,
        "sk-(?!ant-)(?P<body>[A-Za-z0-9_-]{20,})\"),\n        _mixed,",
        "sk-(?!ant-)(?P<body>[A-Za-z0-9_-]{20,})\"),\n        None,",
        TARGETS,
    ),
    (
        "only xoxb- Slack tokens are found",
        HOOK,
        "xox[abpr]-(?P<body>",
        "xoxb-(?P<body>",
        TARGETS,
    ),
    (
        "a Slack token with no numeric id asks",
        HOOK,
        "        _has_digit,\n",
        "        None,\n",
        TARGETS,
    ),
    (
        "a Google key must be one character longer than real ones are",
        HOOK,
        "AIza(?P<body>[A-Za-z0-9_-]{35})",
        "AIza(?P<body>[A-Za-z0-9_-]{36})",
        TARGETS,
    ),
    (
        "a Google key with a placeholder body asks",
        HOOK,
        "AIza(?P<body>[A-Za-z0-9_-]{35})(?![A-Za-z0-9_-])\"),\n        _mixed,",
        "AIza(?P<body>[A-Za-z0-9_-]{35})(?![A-Za-z0-9_-])\"),\n        None,",
        TARGETS,
    ),
    (
        "a restricted Stripe key is no longer found",
        HOOK,
        "[sr]k_live_(?P<body>",
        "sk_live_(?P<body>",
        TARGETS,
    ),
    (
        "a Stripe key with a placeholder body asks",
        HOOK,
        "[sr]k_live_(?P<body>[A-Za-z0-9]{16,})\"),\n        _mixed,",
        "[sr]k_live_(?P<body>[A-Za-z0-9]{16,})\"),\n        None,",
        TARGETS,
    ),
    (
        "a PKCS8 private key header (no algorithm word) is no longer found",
        HOOK,
        "-----BEGIN [A-Z0-9 ]{0,40}PRIVATE KEY",
        "-----BEGIN [A-Z0-9 ]{1,40}PRIVATE KEY",
        TARGETS,
    ),
    (
        "the private key shape is run through a body check it has no group for",
        HOOK,
        "PRIVATE KEY\"),\n        None,",
        "PRIVATE KEY\"),\n        _mixed,",
        TARGETS,
    ),
    (
        "two base64url segments count as a JWT",
        HOOK,
        r"\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}",
        r"\.eyJ[A-Za-z0-9_-]{8,}",
        TARGETS,
    ),
    (
        "the JWT shape is run through a body check it has no group for",
        HOOK,
        "        ),\n        None,\n    ),\n]",
        "        ),\n        _mixed,\n    ),\n]",
        TARGETS,
    ),
    (
        "only short schemes are read, so postgres:// is missed",
        HOOK,
        "[A-Za-z][A-Za-z0-9+.-]{0,31}://",
        "[A-Za-z][A-Za-z0-9+.-]{0,3}://",
        TARGETS,
    ),
    (
        "the password runs on past a slash, into a path",
        HOOK,
        "(?P<password>[^\\s/@]+)@",
        "(?P<password>[^\\s@]+)@",
        TARGETS,
    ),
    # ---- each key prefix opens its run, and the fixed-length ends close it --
    (
        "an AWS key ID inside a longer word asks",
        HOOK,
        'r"(?<![A-Za-z0-9])(?:AKIA',
        'r"(?:AKIA',
        TARGETS,
    ),
    (
        "an AWS-shaped run one character too long asks",
        HOOK,
        '{16})(?![A-Za-z0-9])"),',
        '{16})"),',
        TARGETS,
    ),
    (
        "a GitHub token inside a longer run asks",
        HOOK,
        'r"(?<![A-Za-z0-9_])gh[pousr]',
        'r"gh[pousr]',
        TARGETS,
    ),
    (
        "a fine-grained token inside a longer run asks",
        HOOK,
        'r"(?<![A-Za-z0-9_])github_pat_',
        'r"github_pat_',
        TARGETS,
    ),
    (
        "an Anthropic key inside a longer run asks",
        HOOK,
        'r"(?<![A-Za-z0-9_-])sk-ant-',
        'r"sk-ant-',
        TARGETS,
    ),
    (
        "an OpenAI key inside a longer run asks",
        HOOK,
        'r"(?<![A-Za-z0-9_-])sk-(?!ant-)',
        'r"sk-(?!ant-)',
        TARGETS,
    ),
    (
        "a Slack token inside a longer run asks",
        HOOK,
        'r"(?<![A-Za-z0-9_-])xox',
        'r"xox',
        TARGETS,
    ),
    (
        "a Google key inside a longer run asks",
        HOOK,
        'r"(?<![A-Za-z0-9_-])AIza',
        'r"AIza',
        TARGETS,
    ),
    (
        "a Google-shaped run one character too long asks",
        HOOK,
        '{35})(?![A-Za-z0-9_-])"),',
        '{35})"),',
        TARGETS,
    ),
    (
        "a Stripe key inside a longer run asks",
        HOOK,
        'r"(?<![A-Za-z0-9_])[sr]k_live_',
        'r"[sr]k_live_',
        TARGETS,
    ),
    (
        "a JWT match may start inside a run, which also makes the scan quadratic",
        HOOK,
        'r"(?<![A-Za-z0-9_-])eyJ',
        'r"eyJ',
        TARGETS,
    ),
    # ---- the path scope ------------------------------------------------------
    (
        "a backslash path is not split into its parts",
        HOOK,
        'path.replace("\\\\", "/").split("/")',
        'path.split("/")',
        TARGETS,
    ),
    (
        "the scope is case-sensitive",
        HOOK,
        "parts = [p.lower() for p in path",
        "parts = [p for p in path",
        TARGETS,
    ),
    (
        "a file named after a briefing directory counts as inside it",
        HOOK,
        "    for i in range(len(parts) - 2):",
        "    for i in range(len(parts) - 1):",
        TARGETS,
    ),
    (
        "a folder whose name contains cla.io counts as cla.io",
        HOOK,
        'if parts[i] == "cla.io" and parts[i + 1] in _BRIEFING_DIRS:',
        'if "cla.io" in parts[i] and parts[i + 1] in _BRIEFING_DIRS:',
        TARGETS,
    ),
    (
        "a folder whose name contains a briefing name counts as one",
        HOOK,
        "and parts[i + 1] in _BRIEFING_DIRS:",
        "and any(d in parts[i + 1] for d in _BRIEFING_DIRS):",
        TARGETS,
    ),
    (
        "nothing is in scope",
        HOOK,
        "            return True\n    return False",
        "            return False\n    return False",
        TARGETS,
    ),
    # ---- the scan ------------------------------------------------------------
    (
        "every finding is on line 1",
        HOOK,
        '    newlines = [m.start() for m in re.finditer("\\n", text)]',
        "    newlines = []",
        TARGETS,
    ),
    (
        "the last key pattern (JWT) is never run",
        HOOK,
        "    for kind, pattern, check in _TOKEN_KINDS:",
        "    for kind, pattern, check in _TOKEN_KINDS[:-1]:",
        TARGETS,
    ),
    (
        "only the first match of each pattern is found",
        HOOK,
        "        for m in pattern.finditer(text):",
        "        for m in filter(None, [pattern.search(text)]):",
        TARGETS,
    ),
    (
        "a pattern's body check is skipped",
        HOOK,
        '            if check is None or check(m.group("body")):',
        "            if True:",
        TARGETS,
    ),
    (
        "a key-pattern match is dropped",
        HOOK,
        "                hits.append((m.start(), kind))",
        "                pass",
        TARGETS,
    ),
    (
        "connection URLs are never scanned",
        HOOK,
        "    for m in _URL_CREDENTIALS.finditer(text):",
        "    for m in _URL_CREDENTIALS.finditer(text[:0]):",
        TARGETS,
    ),
    (
        "every URL password counts, placeholders included",
        HOOK,
        '        if _real_password(m.group("user"), m.group("password")):',
        "        if True:",
        TARGETS,
    ),
    (
        "a URL password is reported under a kind that names nothing",
        HOOK,
        '            hits.append((m.start(), "a password in a connection URL"))',
        '            hits.append((m.start(), "a match"))',
        TARGETS,
    ),
    (
        "findings are listed by pattern, not by line",
        HOOK,
        "    hits.sort(key=lambda hit: hit[0])",
        "    pass",
        TARGETS,
    ),
    (
        "line numbers start at 0",
        HOOK,
        "    return [(bisect.bisect_left(newlines, start) + 1, kind) for start, kind in hits]",
        "    return [(bisect.bisect_left(newlines, start), kind) for start, kind in hits]",
        TARGETS,
    ),
    # ---- the reason ----------------------------------------------------------
    (
        "every finding is named, past the cap",
        HOOK,
        "for line, kind in findings[:_MAX_NAMED]]",
        "for line, kind in findings]",
        TARGETS,
    ),
    (
        "the count of the rest is off by one",
        HOOK,
        "    more = len(findings) - len(named)",
        "    more = len(findings) - len(named) + 1",
        TARGETS,
    ),
    (
        "an empty remainder is still counted",
        HOOK,
        '(f"; and {more} more" if more > 0 else "")',
        '(f"; and {more} more" if more >= 0 else "")',
        TARGETS,
    ),
    (
        "the reason stops naming the target",
        HOOK,
        "        f\"The new text for '{target}' holds what looks like a secret: {listing} \"",
        "        f\"The new text holds what looks like a secret: {listing} \"",
        TARGETS,
    ),
    (
        "the reason stops saying the file is committed",
        HOOK,
        '        "committed briefing, so a secret written here lands in git history. Name "',
        '        "briefing. Name "',
        TARGETS,
    ),
    (
        "the reason stops pointing at the rule",
        HOOK,
        '        "the file, not its value: say where the secret lives (for example `.env`, "',
        '        "it: say where the secret lives (for example `.env`, "',
        TARGETS,
    ),
    (
        "the reason stops naming the hook",
        HOOK,
        '        "not a real secret. (hook: ask-secret-in-checkpoint.py)"',
        '        "not a real secret."',
        TARGETS,
    ),
    # ---- input handling ------------------------------------------------------
    (
        "an empty file_path is joined to the cwd",
        HOOK,
        "        if not isinstance(file_path, str) or not file_path:",
        "        if not isinstance(file_path, str):",
        TARGETS,
    ),
    (
        "a missing cwd gives up instead of using the process cwd",
        HOOK,
        "            cwd = os.getcwd()",
        "            return 0",
        TARGETS,
    ),
    (
        "an empty cwd is kept, so the target stays relative",
        HOOK,
        "        if not isinstance(cwd, str) or not cwd:",
        "        if not isinstance(cwd, str):",
        TARGETS,
    ),
    (
        "a ~ path is not expanded",
        HOOK,
        "        target = os.path.join(cwd, os.path.expanduser(file_path))",
        "        target = os.path.join(cwd, file_path)",
        TARGETS,
    ),
    (
        "a symlink into a briefing directory is not followed",
        HOOK,
        "_in_briefing_dir(target) or _in_briefing_dir(os.path.realpath(target))",
        "_in_briefing_dir(target)",
        TARGETS,
    ),
    (
        "a briefing directory that is itself a link is judged only where it points",
        HOOK,
        "if not (_in_briefing_dir(target) or _in_briefing_dir(",
        "if not (_in_briefing_dir(",
        TARGETS,
    ),
    (
        "an Edit's new_string is not read",
        HOOK,
        '        for key in ("content", "new_string"):',
        '        for key in ("content",):',
        TARGETS,
    ),
    (
        "a non-string field aborts the scan of the other field",
        HOOK,
        "            if isinstance(text, str):\n",
        "            if text is not None or True:\n",
        TARGETS,
    ),
    (
        "only a JSON error fails open; a crash in the scan escapes",
        HOOK,
        "    except Exception:  # noqa: BLE001 -- fail open: a guard does not break normal work",
        "    except ValueError:  # noqa: BLE001 -- fail open: a guard does not break normal work",
        TARGETS,
    ),
    (
        "a clean briefing still asks",
        HOOK,
        "    if not findings:\n        return 0",
        "    if False:\n        return 0",
        TARGETS,
    ),
    # ---- the ask payload -----------------------------------------------------
    (
        "the payload names no event",
        HOOK,
        '        "hookEventName": "PreToolUse",',
        '        "hookEventName": "",',
        TARGETS,
    ),
    (
        "the guard allows instead of asking",
        HOOK,
        '        "permissionDecision": "ask",',
        '        "permissionDecision": "allow",',
        TARGETS,
    ),
    (
        "the ask carries no reason",
        HOOK,
        '        "permissionDecisionReason": _reason(target, findings),',
        '        "permissionDecisionReason": "",',
        TARGETS,
    ),
    # ---- the Edit/Write dispatcher -------------------------------------------
    (
        "the dispatcher no longer runs the hook",
        DISPATCHER,
        '    "ask-secret-in-checkpoint.py",\n    "block-worktree-path-escape.py",\n]',
        '    "block-worktree-path-escape.py",\n]',
        DISPATCH_TARGETS,
    ),
    (
        "the hook is advisory, so a spent budget drops its ask",
        DISPATCHER,
        '_ADVISORY_HOOKS = frozenset({\n    "warn-comment-dates.py",\n})',
        '_ADVISORY_HOOKS = frozenset({\n    "warn-comment-dates.py",\n    "ask-secret-in-checkpoint.py",\n})',
        DISPATCH_TARGETS,
    ),
    (
        "the hook's budget entry claims a subprocess it does not run",
        LIB,
        '    "ask-secret-in-checkpoint.py": 0.0,',
        '    "ask-secret-in-checkpoint.py": 3.0,',
        DISPATCH_TARGETS,
    ),
]
