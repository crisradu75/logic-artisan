"""Mutant batch for `tests/hooks/test_ask_secret_in_checkpoint.py` -- the enforcing ask
guard over a secret-shaped string written into a committed briefing under `cla.io/`,
in `ask-secret-in-checkpoint.py`, and the Copilot adapter's check for the new text.

Run:
    python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_ask_secret_in_checkpoint.py

Every mutant edits the hook, the Edit/Write dispatcher, `_dispatch_lib.py` or the
Copilot adapter, never a test. The hook mutants re-break one line each, and
several decisions on the lines that carry more than one (a pattern's prefix, its
start rule, its end and its body check; the path split; the scope test): the
briefing directories, the placeholder words, the cap on named findings, the
character-class checks, the start rule shared by every token pattern (a run
boundary, a written escape, a percent-escape), each key pattern, the private-key
and JWT shapes, the URL start, what follows `user:`, where the authority ends
(a slash, a query, a fragment, punctuation), a stand-in port, where the password
ends, each placeholder rule, the path scope, the scan, the new texts an Edit,
Write or MultiEdit carries, the reason text, the input handling, the boundary
between failing open and propagating a crash, and the ask payload. The
dispatcher mutants re-break the hook's place in the list and its enforcing tier;
one more breaks its budget entry. The adapter mutants re-break the key each tool
carries its text under, the type check and the denial's wording.

Deliberately absent, because no correct input can tell them from the real code,
or because the planted bug would hang the run rather than fail it:
- `bisect_left` against `bisect_right` in the line numbering. A match never
  starts on a newline, so the two return the same index.
- `>= 4` against `>= 3` in `_varied`. The batch pins the rule against two
  (`XY` repeated) instead.
- the connection URL's opening lookbehind. A scheme with a letter in front is
  still a scheme, so finditer finds the same password without it, and the scan
  stays linear either way (the scheme is at most 32 characters).
- `:(?!//)` in `_URL_REST`. Its only job is to stop each start's stretch at the
  next `://`, which keeps the scan linear; without it the 1 MB timing test runs
  for hours instead of failing. The colon itself is pinned by a password that
  holds a `:`.
- `.endswith("}")` in the `${...}` test on its own. A real password that starts
  `${` and does not end `}` is no likelier than one that does; the whole
  condition carries a mutant.
- `isinstance(edits, list)` against a plain truth test. A non-list `edits`
  either iterates harmlessly or raises inside the fail-open `try`, so both
  return silence; the batch pins the type with `dict` instead.
- the `return False` lines of `_real_password` are each pinned through their
  `if` condition: removing the condition and removing the return are the same
  planted bug.

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
ADAPTER = PLUGIN / "hooks" / "copilot-pretooluse.py"
ADAPTER_TARGETS = [DEV / "tests" / "hooks" / "test_copilot_hooks.py"]


def _check(anchor: str, kind: str, why: str) -> tuple:
    """A pattern's body check replaced with `kind`, for the line `anchor` ends."""
    return (why, HOOK, f'{anchor}"),\n        {kind.split(">")[0]},',
            f'{anchor}"),\n        {kind.split(">")[1]},', TARGETS)


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
        "`pw` is no longer a placeholder word",
        HOOK,
        '"pw", "token", "mysecretpassword"',
        '"token", "mysecretpassword"',
        TARGETS,
    ),
    (
        "`token` is no longer a placeholder word",
        HOOK,
        '"token", "mysecretpassword"',
        '"mysecretpassword"',
        TARGETS,
    ),
    (
        "the Docker docs' `mysecretpassword` is no longer a placeholder word",
        HOOK,
        '"mysecretpassword",\n})',
        '\n})',
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
        "a fixed-length key needs no upper case",
        HOOK,
        "    return any(c.isupper() for c in body) and any",
        "    return True and any",
        TARGETS,
    ),
    (
        "a fixed-length key needs no lower case",
        HOOK,
        "for c in body) and any(c.islower() for c in body)\n",
        "for c in body) and True\n",
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
    # ---- the start rule every token pattern shares ---------------------------
    (
        "a token may start anywhere, inside a longer run too",
        HOOK,
        r'rf"(?:(?<!{boundary})|',
        r'rf"(?:|',
        TARGETS,
    ),
    (
        "a key after a written escape is missed",
        HOOK,
        r"|(?<=\\[nrt])|",
        r"|",
        TARGETS,
    ),
    (
        "a key after a written \\r or \\t is missed",
        HOOK,
        r"(?<=\\[nrt])",
        r"(?<=\\[n])",
        TARGETS,
    ),
    (
        "a key after a percent-escape is missed",
        HOOK,
        r"|(?<=%[0-9A-Fa-f]{{2}})){body}",
        r"){body}",
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
        "an AWS key ID inside a longer word asks",
        HOOK,
        '_token("[A-Za-z0-9]", r"(?:AKIA',
        '_token("\\\\x00", r"(?:AKIA',
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
        "a GitHub token inside a longer run asks",
        HOOK,
        '_token("[A-Za-z0-9_]", r"gh[pousr]',
        '_token("\\\\x00", r"gh[pousr]',
        TARGETS,
    ),
    (
        "a GitHub token body may run past its fixed length",
        HOOK,
        "gh[pousr]_(?P<body>[A-Za-z0-9]{36})",
        "gh[pousr]_(?P<body>[A-Za-z0-9]{36,})",
        TARGETS,
    ),
    _check("gh[pousr]_(?P<body>[A-Za-z0-9]{36})(?![A-Za-z0-9])", "_cased>None",
           "a GitHub token with a placeholder body asks"),
    _check("gh[pousr]_(?P<body>[A-Za-z0-9]{36})(?![A-Za-z0-9])", "_cased>_mixed",
           "a real GitHub token with no digit is missed"),
    (
        "a fine-grained token's body must be longer than real ones are",
        HOOK,
        "github_pat_(?P<body>[A-Za-z0-9_]{30,})",
        "github_pat_(?P<body>[A-Za-z0-9_]{90,})",
        TARGETS,
    ),
    (
        "a fine-grained token inside a longer run asks",
        HOOK,
        '_token("[A-Za-z0-9_]", r"github_pat_',
        '_token("\\\\x00", r"github_pat_',
        TARGETS,
    ),
    _check("github_pat_(?P<body>[A-Za-z0-9_]{30,})", "_mixed>None",
           "a fine-grained token with a placeholder body asks"),
    (
        "the Anthropic prefix is misspelled",
        HOOK,
        "sk-ant-(?P<body>",
        "sk-anth-(?P<body>",
        TARGETS,
    ),
    (
        "an Anthropic key inside a longer run asks",
        HOOK,
        '_token("[A-Za-z0-9_-]", r"sk-ant-',
        '_token("\\\\x00", r"sk-ant-',
        TARGETS,
    ),
    _check("sk-ant-(?P<body>[A-Za-z0-9_-]{20,})", "_mixed>None",
           "an Anthropic key with a placeholder body asks"),
    (
        "an sk-proj- key is no longer found",
        HOOK,
        "sk-(?:proj|svcacct|admin|None)-",
        "sk-(?:svcacct|admin|None)-",
        TARGETS,
    ),
    (
        "a prefixed OpenAI key inside a longer run asks",
        HOOK,
        '_token("[A-Za-z0-9_-]", r"sk-(?:proj',
        '_token("\\\\x00", r"sk-(?:proj',
        TARGETS,
    ),
    _check("sk-(?:proj|svcacct|admin|None)-(?P<body>[A-Za-z0-9_-]{40,})", "_mixed>None",
           "a prefixed OpenAI key with a placeholder body asks"),
    (
        "a bare sk- key may be the first part of a longer slug",
        HOOK,
        r'sk-(?P<body>[A-Za-z0-9]{32,})(?![A-Za-z0-9_-])"',
        r'sk-(?P<body>[A-Za-z0-9]{32,})"',
        TARGETS,
    ),
    (
        "a bare sk- key may hold dashes, so a slug matches",
        HOOK,
        "sk-(?P<body>[A-Za-z0-9]{32,})",
        "sk-(?P<body>[A-Za-z0-9-]{32,})",
        TARGETS,
    ),
    (
        "a bare OpenAI key inside a longer run asks",
        HOOK,
        '_token("[A-Za-z0-9_-]", r"sk-(?P<body>',
        '_token("\\\\x00", r"sk-(?P<body>',
        TARGETS,
    ),
    _check("sk-(?P<body>[A-Za-z0-9]{32,})(?![A-Za-z0-9_-])", "_mixed>None",
           "a bare sk- run without mixed classes asks"),
    (
        "xoxe- refresh tokens are no longer found",
        HOOK,
        "xox[abpre]-(?P<body>",
        "xox[abpr]-(?P<body>",
        TARGETS,
    ),
    (
        "a Slack token inside a longer run asks",
        HOOK,
        '_token("[A-Za-z0-9_-]", r"xox',
        '_token("\\\\x00", r"xox',
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
        "a Google key inside a longer run asks",
        HOOK,
        '_token("[A-Za-z0-9_-]", r"AIza',
        '_token("\\\\x00", r"AIza',
        TARGETS,
    ),
    (
        "a Google-shaped run one character too long asks",
        HOOK,
        '{35})(?![A-Za-z0-9_-])"),',
        '{35})"),',
        TARGETS,
    ),
    _check("AIza(?P<body>[A-Za-z0-9_-]{35})(?![A-Za-z0-9_-])", "_cased>None",
           "a Google key with a placeholder body asks"),
    _check("AIza(?P<body>[A-Za-z0-9_-]{35})(?![A-Za-z0-9_-])", "_cased>_mixed",
           "a real Google key with no digit is missed"),
    (
        "a restricted Stripe key is no longer found",
        HOOK,
        "[sr]k_live_(?P<body>",
        "sk_live_(?P<body>",
        TARGETS,
    ),
    (
        "a Stripe key inside a longer run asks",
        HOOK,
        '_token("[A-Za-z0-9_]", r"[sr]k_live_',
        '_token("\\\\x00", r"[sr]k_live_',
        TARGETS,
    ),
    _check("[sr]k_live_(?P<body>[A-Za-z0-9]{16,})", "_mixed>None",
           "a Stripe key with a placeholder body asks"),
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
        "a JWT may start inside a run, which also makes the scan quadratic",
        HOOK,
        '            "[A-Za-z0-9_-]",\n            r"eyJ',
        '            "\\\\x00",\n            r"eyJ',
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
    # ---- the connection URL --------------------------------------------------
    (
        "only short schemes are read, so postgres:// is missed",
        HOOK,
        "[A-Za-z][A-Za-z0-9+.-]{0,31}://",
        "[A-Za-z][A-Za-z0-9+.-]{0,3}://",
        TARGETS,
    ),
    (
        "an IPv6 host's bracket is read as a user",
        HOOK,
        r"(?P<user>[^\s:/@\[]*):",
        r"(?P<user>[^\s:/@]*):",
        TARGETS,
    ),
    (
        "a password stops at its first colon",
        HOOK,
        r'_URL_REST = re.compile(r"(?:[^\s:]|:(?!//))*")',
        r'_URL_REST = re.compile(r"[^\s:]*")',
        TARGETS,
    ),
    (
        "the stretch after user: is read from the scheme instead",
        HOOK,
        "_URL_REST.match(text, m.end())",
        "_URL_REST.match(text, m.start())",
        TARGETS,
    ),
    (
        "the authority runs to the end, so a query's @ moves the password's end",
        HOOK,
        '    slash = rest.find("/")',
        "    slash = -1",
        TARGETS,
    ),
    (
        "the password stops at its first @",
        HOOK,
        '        return authority[:authority.rindex("@")]',
        '        return authority[:authority.index("@")]',
        TARGETS,
    ),
    (
        "an @ before the first / is not read as the userinfo's end",
        HOOK,
        '    if "@" in authority:',
        "    if False:",
        TARGETS,
    ),
    (
        "a URL with no @ at all crashes the scan",
        HOOK,
        '    if "@" not in rest or authority.isdigit() or',
        "    if authority.isdigit() or",
        TARGETS,
    ),
    (
        "a port before the first / is read as a password",
        HOOK,
        '"@" not in rest or authority.isdigit() or',
        '"@" not in rest or',
        TARGETS,
    ),
    (
        "a stand-in port (<port>, ${PORT}) before a path @ is read as a password",
        HOOK,
        " or not _real_password(user, authority):",
        ":",
        TARGETS,
    ),
    (
        "a query's @ is read as the end of the userinfo",
        HOOK,
        """_AUTHORITY_END = re.compile(r"[?#,;()'\\"]")""",
        """_AUTHORITY_END = re.compile(r"[#,;()'\\"]")""",
        TARGETS,
    ),
    (
        "a fragment's @ is read as the end of the userinfo",
        HOOK,
        """re.compile(r"[?#,;""",
        """re.compile(r"[?,;""",
        TARGETS,
    ),
    (
        "a comma before an @mention is read as part of a password",
        HOOK,
        """#,;()'""",
        """#;()'""",
        TARGETS,
    ),
    (
        "nothing ends the authority but a slash",
        HOOK,
        "    end = _AUTHORITY_END.search(rest)",
        "    end = None",
        TARGETS,
    ),
    (
        "the authority's end is looked up even when there is none, and crashes",
        HOOK,
        "    if end is not None:",
        "    if end is None:",
        TARGETS,
    ),
    (
        "the text past the authority's end is kept",
        HOOK,
        "        rest = rest[:end.start()]",
        "        pass",
        TARGETS,
    ),
    (
        "the user name is not passed, so a port equal to it reads as a password",
        HOOK,
        '_url_password(m.group("user"), ',
        '_url_password("", ',
        TARGETS,
    ),
    (
        "a password holding an unencoded / is missed",
        HOOK,
        '    return rest[:rest.rindex("@")]',
        "    return None",
        TARGETS,
    ),
    # ---- the URL password placeholders ---------------------------------------
    (
        "a percent-encoded placeholder counts as a password",
        HOOK,
        "    user, password = unquote(user), unquote(password)",
        "    pass",
        TARGETS,
    ),
    (
        "an empty password crashes the scan",
        HOOK,
        "    if not password:",
        "    if False:",
        TARGETS,
    ),
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
        '    if password.startswith("${") and password.endswith("}"):',
        "    if False:",
        TARGETS,
    ),
    (
        "a password starting $ and a lower-case letter is read as a variable",
        HOOK,
        r'r"\$[A-Z_][A-Z0-9_]*"',
        r'r"\$[A-Za-z_][A-Za-z0-9_]*"',
        TARGETS,
    ),
    (
        "an upper-case stand-in (TOKEN) counts as a password",
        HOOK,
        r'    if re.fullmatch(r"[A-Z]+(?:_[A-Z]+)*", password):',
        "    if False:",
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
    # ---- the path scope ------------------------------------------------------
    (
        "a trailing dot or space on a folder name hides the folder",
        HOOK,
        'p.rstrip(". ").lower()',
        "p.lower()",
        TARGETS,
    ),
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
        'parts = [p.rstrip(". ").lower() for p',
        'parts = [p.rstrip(". ") for p',
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
        "    for m in _URL_START.finditer(text):",
        "    for m in _URL_START.finditer(text[:0]):",
        TARGETS,
    ),
    (
        "a URL with no password reaches the placeholder rules, and crashes",
        HOOK,
        "        if password is not None and _real_password(",
        "        if _real_password(",
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
    # ---- the new texts a call carries ----------------------------------------
    (
        "an Edit's new_string is not read",
        HOOK,
        '    for key in ("content", "new_string"):',
        '    for key in ("content",):',
        TARGETS,
    ),
    (
        "a non-string field reaches the scan, and crashes it",
        HOOK,
        "        if isinstance(value, str):\n",
        "        if True:\n",
        TARGETS,
    ),
    (
        "a Write's content is dropped",
        HOOK,
        '            texts.append(("", value))',
        "            pass",
        TARGETS,
    ),
    (
        "a MultiEdit's edits are not read",
        HOOK,
        '    edits = tool_input.get("edits")',
        "    edits = None",
        TARGETS,
    ),
    (
        "edits are read only from a mapping, never from the list a MultiEdit sends",
        HOOK,
        "    if isinstance(edits, list):",
        "    if isinstance(edits, dict):",
        TARGETS,
    ),
    (
        "edits are numbered from 0",
        HOOK,
        "        for n, edit in enumerate(edits, 1):",
        "        for n, edit in enumerate(edits):",
        TARGETS,
    ),
    (
        "an edit with no string new_string reaches the scan, and crashes it",
        HOOK,
        '            if isinstance(edit, dict) and isinstance(edit.get("new_string"), str):',
        "            if isinstance(edit, dict):",
        TARGETS,
    ),
    (
        "the ask stops saying which edit holds the secret",
        HOOK,
        '                texts.append((f" of edit {n}", edit["new_string"]))',
        '                texts.append(("", edit["new_string"]))',
        TARGETS,
    ),
    # ---- the reason ----------------------------------------------------------
    (
        "every finding is named, past the cap",
        HOOK,
        "for line, kind, where in findings[:_MAX_NAMED]]",
        "for line, kind, where in findings]",
        TARGETS,
    ),
    (
        "a finding's place drops its edit number",
        HOOK,
        'f"{kind} on line {line}{where}"',
        'f"{kind} on line {line}"',
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
    # ---- input handling, and where failing open stops -------------------------
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
        "no new text is collected",
        HOOK,
        "        texts = _new_texts(tool_input)",
        "        texts = []",
        TARGETS,
    ),
    (
        "only a JSON error fails open; other bad input escapes",
        HOOK,
        "    except Exception:  # noqa: BLE001 -- bad input fails open; the scan below does not",
        "    except ValueError:  # noqa: BLE001 -- bad input fails open; the scan below does not",
        TARGETS,
    ),
    (
        "a crash in the scan fails open silently again",
        HOOK,
        "    findings = [(line, kind, where) for where, text in texts for line, kind in _findings(text)]",
        "    try:\n        findings = [(line, kind, where) for where, text in texts"
        " for line, kind in _findings(text)]\n    except Exception:\n        return 0",
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
    # ---- the Copilot adapter -------------------------------------------------
    (
        "the adapter looks for each tool's text under the other tool's key",
        ADAPTER,
        '_TEXT_KEYS = {"Edit": "new_string", "Write": "content"}',
        '_TEXT_KEYS = {"Edit": "content", "Write": "new_string"}',
        ADAPTER_TARGETS,
    ),
    (
        "the adapter accepts new text that is not a string",
        ADAPTER,
        "    elif not isinstance(tool_input.get(_TEXT_KEYS[tool_name]), str):",
        "    elif tool_input.get(_TEXT_KEYS[tool_name]) is None:",
        ADAPTER_TARGETS,
    ),
    (
        "the adapter's denial stops naming the missing key",
        ADAPTER,
        '            f"CLA guard received no `{_TEXT_KEYS[tool_name]}` to check; refusing the call."',
        '            "CLA guard received no text to check; refusing the call."',
        ADAPTER_TARGETS,
    ),
]
