#!/usr/bin/env python3
"""PreToolUse hook: ask before a secret-shaped string is written into a committed briefing.

Problem this solves
--------------------
`/cla:checkpoint` writes a briefing to `cla.io/checkpoints/`, and the file gets
committed. Its rule is "Never copy a token, key, connection string, or the
contents of a `.env`. Name the file, not its value." The briefing is written
from the session's own context, which is where a pasted key or a connection
string from an error message sits, and nothing checked the rule.

Scope
-----
A Write's `content`, an Edit's `new_string`, and each `new_string` of a
MultiEdit's `edits` list, whose target lies under one of these directories, at
any depth below a `cla.io/` directory:

- `checkpoints/`: `/cla:checkpoint`, the rule this backs.
- `decisions/`: `/cla:shape-decision` writes a decision from the conversation.
- `feedback/`: `/cla:feedback` grounds notes with a file and a stack trace, and
  `/cla:diagnose` writes a finding with the failing command and its output.
- `lessons-learned/`: `/cla:codify-learnings` logs a failure into a tracked log.

Each is a committed file an agent fills by paraphrasing the session, so a key
in the session lands in git history the same way. Other `cla.io/` files
(`project-facts.md`, overlays) are configuration, not session paraphrase. The
directory names are compared case-insensitively and without a trailing dot or
space, since Windows and a case-insensitive file system write `Checkpoints/`
and `checkpoints./` into the same folder.

`hooks.json` matches `Edit|Write`. Claude Code reads a matcher made only of
letters, digits, `_` and `|` as a list of exact tool names, so MultiEdit is not
routed here today; an older reading as an unanchored regex did route it, and
reading `edits` costs nothing, so it is scanned whenever it is present.

Detection
---------
High-signal shapes only, so ordinary prose, a commit sha or a UUID stays silent:

- well-known key formats: AWS access key IDs (`AKIA`/`ASIA`), GitHub tokens
  (`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`), Anthropic (`sk-ant-`),
  OpenAI (`sk-proj-`, `sk-svcacct-`, `sk-admin-`, `sk-None-`, or a bare `sk-`
  followed by one unbroken alphanumeric run of 32 or more), Slack (`xoxa-`,
  `xoxb-`, `xoxp-`, `xoxr-`, `xoxe-`), Google API keys (`AIza`) and Stripe
  live keys (`sk_live_`, `rk_live_`).
  A random key mixes upper case, lower case and digits, so a body without all
  three (`ghp_xxxx...`, a slug) is a placeholder. Two formats with a fixed
  prefix and a fixed length, GitHub's classic tokens and Google's keys, need
  only both cases: a few in a thousand real ones have no digit. A Slack token
  carries numeric ids, so one without a digit is a placeholder too.
- a `-----BEGIN ... PRIVATE KEY` header.
- `scheme://user:password@host` with a password that is not a placeholder:
  `<...>`, `{...}`, `${...}` or `$NAME`, an upper-case stand-in (`TOKEN`,
  `GITHUB_TOKEN`), one repeated character (`***`, `xxx`), a stand-in word
  (`password`, `pass`, `secret`, `mysecretpassword`, ...) or the user name
  again (`postgres:postgres`). A percent-encoded password is decoded first
  (`%3Cpassword%3E` is `<password>`). The password runs to the last `@` of the
  authority, so an unencoded `@` or `/` inside it is still read whole.
- a JWT: three base64url segments, the first two starting `eyJ`.

A token can start only where a run starts: after a character its body could not
contain, or right after a written escape (`\\n`, `\\r`, `\\t`) or a
percent-escape (`%3D`, `%20`). A key-like stretch inside a base64 blob is not a
key. That rule also keeps the scan linear on a megabyte of content: no pattern
nests a quantifier, and no run is scanned from more than a few starts.

Decision: `ask`, naming each kind and the line of the new text it is on, and
never the value itself; the reason points at the rule, "name the file, not its
value". An ask, not a block: the pattern list backs the rule rather than
replacing it, and a person can say yes to a match that is not a real secret.

Failure: bad input (a parse error, a missing or mistyped field, a path that
cannot be resolved) fails open, exiting 0 with no output. A defect in the scan
itself is not caught: it propagates, and the Edit/Write dispatcher counts this
enforcing guard as not run and asks, as it does when the file fails to load. It
runs no subprocess and does no file I/O.
"""

from __future__ import annotations

import bisect
import json
import os
import re
import sys
from urllib.parse import unquote

# The directories under a `cla.io/` directory whose files are committed briefings.
_BRIEFING_DIRS = frozenset({"checkpoints", "decisions", "feedback", "lessons-learned"})

# Stand-in words a documented connection string uses for its password.
_PLACEHOLDER_WORDS = frozenset({
    "password", "passwd", "pass", "pwd", "secret", "changeme", "redacted", "example",
    "pw", "token", "mysecretpassword",
})

# At most this many findings are named; the rest are counted.
_MAX_NAMED = 10


def _mixed(body: str) -> bool:
    """A random key's body: upper case, lower case and a digit, all three."""
    return (
        any(c.isupper() for c in body)
        and any(c.islower() for c in body)
        and any(c.isdigit() for c in body)
    )


def _cased(body: str) -> bool:
    """Both cases, digit or not: for fixed-prefix, fixed-length formats."""
    return any(c.isupper() for c in body) and any(c.islower() for c in body)


def _has_digit(body: str) -> bool:
    return any(c.isdigit() for c in body)


def _varied(body: str) -> bool:
    """Not a run of one or two characters (`AKIAXXXXXXXXXXXXXXXX`)."""
    return len(set(body)) >= 4


def _token(boundary: str, body: str) -> re.Pattern:
    """`body`, allowed to start only where a run starts: after a character
    outside `boundary`, after a written `\\n`/`\\r`/`\\t`, or after a `%XX`."""
    return re.compile(rf"(?:(?<!{boundary})|(?<=\\[nrt])|(?<=%[0-9A-Fa-f]{{2}})){body}")


# (kind, pattern, check). `check` gets the pattern's `body` group, or None for a
# shape that is a secret as soon as it matches.
_TOKEN_KINDS = [
    (
        "an AWS access key ID",
        _token("[A-Za-z0-9]", r"(?:AKIA|ASIA)(?P<body>[A-Z0-9]{16})(?![A-Za-z0-9])"),
        _varied,
    ),
    (
        "a GitHub token",
        _token("[A-Za-z0-9_]", r"gh[pousr]_(?P<body>[A-Za-z0-9]{36})(?![A-Za-z0-9])"),
        _cased,
    ),
    (
        "a GitHub fine-grained token",
        _token("[A-Za-z0-9_]", r"github_pat_(?P<body>[A-Za-z0-9_]{30,})"),
        _mixed,
    ),
    (
        "an Anthropic API key",
        _token("[A-Za-z0-9_-]", r"sk-ant-(?P<body>[A-Za-z0-9_-]{20,})"),
        _mixed,
    ),
    (
        "an OpenAI API key",
        _token("[A-Za-z0-9_-]", r"sk-(?:proj|svcacct|admin|None)-(?P<body>[A-Za-z0-9_-]{40,})"),
        _mixed,
    ),
    (
        # A bare `sk-` key is one unbroken run: a slug (`sk-Learn2Rank-...`) is not.
        "an OpenAI API key",
        _token("[A-Za-z0-9_-]", r"sk-(?P<body>[A-Za-z0-9]{32,})(?![A-Za-z0-9_-])"),
        _mixed,
    ),
    (
        "a Slack token",
        _token("[A-Za-z0-9_-]", r"xox[abpre]-(?P<body>[A-Za-z0-9-]{10,})"),
        _has_digit,
    ),
    (
        "a Google API key",
        _token("[A-Za-z0-9_-]", r"AIza(?P<body>[A-Za-z0-9_-]{35})(?![A-Za-z0-9_-])"),
        _cased,
    ),
    (
        "a Stripe live key",
        _token("[A-Za-z0-9_]", r"[sr]k_live_(?P<body>[A-Za-z0-9]{16,})"),
        _mixed,
    ),
    (
        "a private key",
        re.compile(r"-----BEGIN [A-Z0-9 ]{0,40}PRIVATE KEY"),
        None,
    ),
    (
        "a JWT",
        _token(
            "[A-Za-z0-9_-]",
            r"eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}",
        ),
        None,
    ),
]

# `scheme://user:`. The user part stops at `:`, so the first colon after `//`
# splits user from password. `[` is left out of the user so an IPv6 host
# (`http://[::1]:8080/`) is not read as a user.
_URL_START = re.compile(r"(?<![A-Za-z0-9+.-])[A-Za-z][A-Za-z0-9+.-]{0,31}://(?P<user>[^\s:/@\[]*):")
# What follows `user:`, up to whitespace or the next `://`. Stopping at the next
# `://` keeps every start's stretch apart from the next one's, so the scan is linear.
_URL_REST = re.compile(r"(?:[^\s:]|:(?!//))*")
# Where the userinfo can no longer run. `?` and `#` start the query and the
# fragment, so an `@` after them (`:3000?email=a@b`) separates nothing. A comma,
# a semicolon, a bracket or a quote ends a URL in prose (`http://host:3000,@bob`).
# The limit this leaves: a password holding one of these unencoded is cut there,
# and the stub before it is all that is checked.
_AUTHORITY_END = re.compile(r"[?#,;()'\"]")


def _url_password(user: str, rest: str) -> str | None:
    """The password at the start of `rest` (the text after `user:`), or None."""
    end = _AUTHORITY_END.search(rest)
    if end is not None:
        rest = rest[:end.start()]
    slash = rest.find("/")
    authority = rest if slash < 0 else rest[:slash]
    if "@" in authority:
        # The userinfo ends at the authority's LAST `@`, so `P@ss@host` gives `P@ss`.
        return authority[:authority.rindex("@")]
    # No `@` before the first `/`: either that `/` sits inside an unencoded
    # password (`user:pa/ss@host`), or there is no password and a later `@` is
    # in the path (`host:8080/a@b`, Vite's `localhost:<port>/@vite/client`). A
    # port is all digits or a stand-in (`<port>`, `${PORT}`, `PORT`), so such a
    # stretch before the `/` reads as a port, and so does an empty one. The limit
    # this leaves: a real password whose first `/` follows only digits
    # (`user:2024/x@host`) is read as a port and missed.
    if "@" not in rest or authority.isdigit() or not _real_password(user, authority):
        return None
    return rest[:rest.rindex("@")]


def _real_password(user: str, password: str) -> bool:
    """False for a documented stand-in rather than a password."""
    user, password = unquote(user), unquote(password)
    if not password:
        return False
    if password[0] + password[-1] in ("<>", "{}"):
        return False
    if password.startswith("${") and password.endswith("}"):
        return False
    if re.fullmatch(r"\$[A-Z_][A-Z0-9_]*", password):
        return False
    if re.fullmatch(r"[A-Z]+(?:_[A-Z]+)*", password):
        return False
    if len(set(password)) == 1:
        return False
    if password.lower() in _PLACEHOLDER_WORDS:
        return False
    return password != user


def _in_briefing_dir(path: str) -> bool:
    """True when `path` lies below `cla.io/<one of the briefing dirs>/`."""
    parts = [p.rstrip(". ").lower() for p in path.replace("\\", "/").split("/")]
    # The last part is the file itself; the pair must sit above it.
    for i in range(len(parts) - 2):
        if parts[i] == "cla.io" and parts[i + 1] in _BRIEFING_DIRS:
            return True
    return False


def _findings(text: str) -> list[tuple[int, str]]:
    """(line, kind) for every secret-shaped match, in line order. No values."""
    newlines = [m.start() for m in re.finditer("\n", text)]
    hits: list[tuple[int, str]] = []
    for kind, pattern, check in _TOKEN_KINDS:
        for m in pattern.finditer(text):
            if check is None or check(m.group("body")):
                hits.append((m.start(), kind))
    for m in _URL_START.finditer(text):
        password = _url_password(m.group("user"), _URL_REST.match(text, m.end()).group())
        if password is not None and _real_password(m.group("user"), password):
            hits.append((m.start(), "a password in a connection URL"))
    hits.sort(key=lambda hit: hit[0])
    return [(bisect.bisect_left(newlines, start) + 1, kind) for start, kind in hits]


def _new_texts(tool_input: dict) -> list[tuple[str, str]]:
    """(where, text) for each piece of new text the call writes.

    Only the new text is read. A key split across an Edit's boundary, half
    already in the file and half in `new_string`, is not seen: finding it means
    reading the file on every Edit and re-doing Edit's own matching, file I/O
    this guard does not do, and half a key alone is no key. A whole key in the
    new text, the case a briefing written from the session produces, is seen.
    """
    texts = []
    for key in ("content", "new_string"):
        value = tool_input.get(key)
        if isinstance(value, str):
            texts.append(("", value))
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for n, edit in enumerate(edits, 1):
            if isinstance(edit, dict) and isinstance(edit.get("new_string"), str):
                texts.append((f" of edit {n}", edit["new_string"]))
    return texts


def _reason(target: str, findings: list[tuple[int, str, str]]) -> str:
    named = [f"{kind} on line {line}{where}" for line, kind, where in findings[:_MAX_NAMED]]
    more = len(findings) - len(named)
    listing = "; ".join(named) + (f"; and {more} more" if more > 0 else "")
    return (
        f"The new text for '{target}' holds what looks like a secret: {listing} "
        "(line numbers count from the start of the new text). This file is a "
        "committed briefing, so a secret written here lands in git history. Name "
        "the file, not its value: say where the secret lives (for example `.env`, "
        "key `DATABASE_URL`) and leave the value out. Confirm only if the match is "
        "not a real secret. (hook: ask-secret-in-checkpoint.py)"
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        tool_input = payload["tool_input"]
        file_path = tool_input["file_path"]
        if not isinstance(file_path, str) or not file_path:
            return 0
        cwd = payload.get("cwd")
        if not isinstance(cwd, str) or not cwd:
            cwd = os.getcwd()
        target = os.path.join(cwd, os.path.expanduser(file_path))
        if not (_in_briefing_dir(target) or _in_briefing_dir(os.path.realpath(target))):
            return 0
        texts = _new_texts(tool_input)
    except Exception:  # noqa: BLE001 -- bad input fails open; the scan below does not
        return 0
    # Outside the `try` on purpose: a defect in the scan must not pass as "no
    # secret". It propagates, and the dispatcher reports this enforcing guard as
    # not run and asks.
    findings = [(line, kind, where) for where, text in texts for line, kind in _findings(text)]
    if not findings:
        return 0

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": _reason(target, findings),
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
