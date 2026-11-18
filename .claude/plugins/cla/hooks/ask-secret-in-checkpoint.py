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
A Write's `content` or an Edit's `new_string` whose target lies under one of
these directories, at any depth below a `cla.io/` directory:

- `checkpoints/`: `/cla:checkpoint`, the rule this backs.
- `decisions/`: `/cla:shape-decision` writes a decision from the conversation.
- `feedback/`: `/cla:feedback` grounds notes with a file and a stack trace, and
  `/cla:diagnose` writes a finding with the failing command and its output.
- `lessons-learned/`: `/cla:codify-learnings` logs a failure into a tracked log.

Each is a committed file an agent fills by paraphrasing the session, so a key
in the session lands in git history the same way. Other `cla.io/` files
(`project-facts.md`, overlays) are configuration, not session paraphrase. The
directory names are compared case-insensitively, since a case-insensitive file
system writes `Checkpoints/` into the same folder.

Detection
---------
High-signal shapes only, so ordinary prose, a commit sha or a UUID stays silent:

- well-known key formats: AWS access key IDs (`AKIA`/`ASIA`), GitHub tokens
  (`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`), Anthropic (`sk-ant-`),
  OpenAI (`sk-`, at least 20 characters), Slack (`xoxa-`, `xoxb-`, `xoxp-`,
  `xoxr-`), Google API keys (`AIza`) and Stripe live keys (`sk_live_`,
  `rk_live_`). A random key mixes upper case, lower case and digits, so a
  body without all three (`ghp_xxxx...`, a kebab-case slug after `sk-`) is a
  placeholder; a Slack token carries numeric ids, so one without a digit is too.
- a `-----BEGIN ... PRIVATE KEY` header.
- `scheme://user:password@host` with a non-empty password that is not a
  placeholder: `<...>`, `{...}`, `${VAR}` or `$VAR`, one repeated character
  (`***`, `xxx`), a stand-in word (`password`, `pass`, `secret`, ...) or the
  user name again (`postgres:postgres`, a local default).
- a JWT: three base64url segments, the first two starting `eyJ`.

Each token pattern opens with a lookbehind on the characters its body consumes,
so a match can only start at the beginning of a run (a key-like stretch inside a
base64 blob is not a key), and no pattern nests a quantifier: the scan stays
linear on a megabyte of content.

Decision: `ask`, naming each kind and the line of the new text it is on, and
never the value itself; the reason points at the rule, "name the file, not its
value". An ask, not a block: the pattern list backs the rule rather than
replacing it, and a person can say yes to a match that is not a real secret.

Failure: bad input (a parse error, a missing or mistyped field) fails open,
exiting 0 with no output. If this file itself fails to load or crashes, the
Edit/Write dispatcher counts it as an enforcing guard that did not run and asks
on every Edit and Write until it is fixed. It runs no subprocess and does no
file I/O.
"""

from __future__ import annotations

import bisect
import json
import os
import re
import sys

# The directories under a `cla.io/` directory whose files are committed briefings.
_BRIEFING_DIRS = frozenset({"checkpoints", "decisions", "feedback", "lessons-learned"})

# Stand-in words a documented connection string uses for its password.
_PLACEHOLDER_WORDS = frozenset({
    "password", "passwd", "pass", "pwd", "secret", "changeme", "redacted", "example",
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


def _has_digit(body: str) -> bool:
    return any(c.isdigit() for c in body)


def _varied(body: str) -> bool:
    """Not a run of one or two characters (`AKIAXXXXXXXXXXXXXXXX`)."""
    return len(set(body)) >= 4


def _real_password(user: str, password: str) -> bool:
    """False for a documented stand-in rather than a password."""
    if password[0] + password[-1] in ("<>", "{}"):
        return False
    if password.startswith("${") or re.fullmatch(r"\$[A-Za-z_][A-Za-z0-9_]*", password):
        return False
    if len(set(password)) == 1:
        return False
    if password.lower() in _PLACEHOLDER_WORDS:
        return False
    return password != user


# (kind, pattern, check). `check` gets the pattern's `body` group, or None for a
# shape that is a secret as soon as it matches.
_TOKEN_KINDS = [
    (
        "an AWS access key ID",
        re.compile(r"(?<![A-Za-z0-9])(?:AKIA|ASIA)(?P<body>[A-Z0-9]{16})(?![A-Za-z0-9])"),
        _varied,
    ),
    (
        "a GitHub token",
        re.compile(r"(?<![A-Za-z0-9_])gh[pousr]_(?P<body>[A-Za-z0-9]{30,})"),
        _mixed,
    ),
    (
        "a GitHub fine-grained token",
        re.compile(r"(?<![A-Za-z0-9_])github_pat_(?P<body>[A-Za-z0-9_]{30,})"),
        _mixed,
    ),
    (
        "an Anthropic API key",
        re.compile(r"(?<![A-Za-z0-9_-])sk-ant-(?P<body>[A-Za-z0-9_-]{20,})"),
        _mixed,
    ),
    (
        "an OpenAI API key",
        re.compile(r"(?<![A-Za-z0-9_-])sk-(?!ant-)(?P<body>[A-Za-z0-9_-]{20,})"),
        _mixed,
    ),
    (
        "a Slack token",
        re.compile(r"(?<![A-Za-z0-9_-])xox[abpr]-(?P<body>[A-Za-z0-9-]{10,})"),
        _has_digit,
    ),
    (
        "a Google API key",
        re.compile(r"(?<![A-Za-z0-9_-])AIza(?P<body>[A-Za-z0-9_-]{35})(?![A-Za-z0-9_-])"),
        _mixed,
    ),
    (
        "a Stripe live key",
        re.compile(r"(?<![A-Za-z0-9_])[sr]k_live_(?P<body>[A-Za-z0-9]{16,})"),
        _mixed,
    ),
    (
        "a private key",
        re.compile(r"-----BEGIN [A-Z0-9 ]{0,40}PRIVATE KEY"),
        None,
    ),
    (
        "a JWT",
        re.compile(
            r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"
        ),
        None,
    ),
]

# `scheme://user:password@`. The user part stops at `:`, so the first colon
# after `//` splits user from password; the password stops at `/`, `@` or space.
_URL_CREDENTIALS = re.compile(
    r"(?<![A-Za-z0-9+.-])[A-Za-z][A-Za-z0-9+.-]{0,31}://"
    r"(?P<user>[^\s:/@]*):(?P<password>[^\s/@]+)@"
)


def _in_briefing_dir(path: str) -> bool:
    """True when `path` lies below `cla.io/<one of the briefing dirs>/`."""
    parts = [p.lower() for p in path.replace("\\", "/").split("/")]
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
    for m in _URL_CREDENTIALS.finditer(text):
        if _real_password(m.group("user"), m.group("password")):
            hits.append((m.start(), "a password in a connection URL"))
    hits.sort(key=lambda hit: hit[0])
    return [(bisect.bisect_left(newlines, start) + 1, kind) for start, kind in hits]


def _reason(target: str, findings: list[tuple[int, str]]) -> str:
    named = [f"{kind} on line {line}" for line, kind in findings[:_MAX_NAMED]]
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
        findings: list[tuple[int, str]] = []
        for key in ("content", "new_string"):
            text = tool_input.get(key)
            if isinstance(text, str):
                findings.extend(_findings(text))
    except Exception:  # noqa: BLE001 -- fail open: a guard does not break normal work
        return 0
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
