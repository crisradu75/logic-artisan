#!/usr/bin/env python3
r"""PreToolUse hook: WARN (never block) when a Bash heredoc body carries a
backslash escape that the shell/Python layering will silently eat.

THE FAILURE. Writing file content through `python3 - <<'PY' ... PY` looks safe
because the delimiter is quoted, so the shell does not expand `$` or backticks.
It does NOT protect a backslash escape that the INNER language then re-reads: a
`"\n"` intended as a two-character Python escape arrives as a real newline,
which inside a string literal is a `SyntaxError` — and inside a data string is a
silently wrong value. The same applies to `\r`, `\t`, `\b`, `\x00` and friends.

WHY A HOOK RATHER THAN ANOTHER SENTENCE. This is a third-instance re-offense.
It is already written down twice: user memory
(`feedback_no_heredocs_for_file_content` — "shell+Python layers mangle escapes
(\n, \b, \x00); use Write/Edit") and
`skills/_shared/references/bash-discipline.md` ("no heredoc subshells"). Both
were in context and it happened anyway, three times in one session (2026-08-23):
twice writing mutant batches whose anchors needed a literal `\n`, and once MORE
while writing the verification for the fix to the first two. A rule that loses
three times to the same shape is not under-stated; it is at the wrong rung.

DETECTION, deliberately narrow. The command must (a) open a heredoc, and (b)
carry a backslash escape from the set that actually gets eaten, in the heredoc
body. A heredoc with no such escape is left alone — heredocs are legitimate and
this repo uses them constantly for ordinary multi-line text. That narrowness is
the point: a hook that fires on every heredoc would be muted within a day.

WARN, never block. A heredoc containing `\n` can be entirely correct (a regex
written as a raw string, prose describing an escape). Blocking would over-fire
on a judgement the author is better placed to make; the warning just prompts a
look before a mangled file lands.

Best-effort: any parse failure exits 0 silently — a warning hook must never
disrupt the workflow.
"""

from __future__ import annotations

import json
import re
import sys

from pathlib import Path

# The `_dispatch_lib` import below resolves through `sys.path`; running
# standalone normally puts the hooks dir at `sys.path[0]`, but that is
# suppressed under `PYTHONSAFEPATH=1` / `python -I` / `python -P`. Insert it
# explicitly so an import failure can't silently disable this hook.
_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

# Opening delimiter: `<<WORD`, `<<'WORD'`, `<<"WORD"`, `<<-WORD`.
_HEREDOC_OPEN = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")

# The escapes that a shell/inner-language sandwich actually eats.
#
# The lookbehind is load-bearing, not decoration: without it `\\n` matches on its
# SECOND backslash and the hook fires on a doubled escape — the case an author
# has already thought about, and precisely the false positive that would get a
# warn hook muted. This repo's own test for it failed on the first cut.
_EATEN_ESCAPE = re.compile(r"(?<!\\)\\[nrtbfva0xu]")


def _heredoc_bodies(cmd: str) -> list[tuple[str, str]]:
    """Every `(delimiter, body)` pair the command opens.

    Scans line by line rather than with one regex over the whole string: a
    command can open more than one heredoc, and the body runs to a line that is
    exactly the delimiter. An unterminated heredoc yields the rest of the
    command, which is the right conservative reading — that text IS the body.
    """
    lines = cmd.splitlines()
    out: list[tuple[str, str]] = []
    i = 0
    while i < len(lines):
        m = _HEREDOC_OPEN.search(lines[i])
        if not m:
            i += 1
            continue
        delim = m.group(2)
        body: list[str] = []
        i += 1
        while i < len(lines) and lines[i].strip() != delim:
            body.append(lines[i])
            i += 1
        i += 1  # step past the terminator (or off the end)
        out.append((delim, "\n".join(body)))
    return out


def offending_heredocs(cmd: str) -> list[tuple[str, list[str]]]:
    """`(delimiter, sorted distinct escapes)` for each body carrying an eaten escape."""
    found = []
    for delim, body in _heredoc_bodies(cmd):
        escapes = sorted({m.group(0) for m in _EATEN_ESCAPE.finditer(body)})
        if escapes:
            found.append((delim, escapes))
    return found


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    tool_input = payload.get("tool_input")
    cmd = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not isinstance(cmd, str) or not cmd:
        return 0

    offenders = offending_heredocs(cmd)
    if not offenders:
        return 0

    detail = "; ".join(
        f"<<{delim} carries {', '.join(esc)}" for delim, esc in offenders
    )
    print(
        f"[warn-heredoc-escape-mangling] {detail}. A quoted heredoc delimiter "
        f"stops the shell expanding `$` and backticks, but NOT a backslash "
        f"escape the inner language re-reads: `\\n` arrives as a real newline, "
        f"which is a SyntaxError inside a string literal and a silently wrong "
        f"value inside data. If the escape is meant to survive, use Write/Edit "
        f"for the file, or Write a script and run it by path.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
