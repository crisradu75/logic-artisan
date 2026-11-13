#!/usr/bin/env python3
"""PreToolUse hook — warn when an Edit/Write adds a code comment containing a
bare YYYY-MM-DD date.

Dates rot in code comments: "confirmed <date>", "PR #<n>", "today's fix"
all turn into misleading noise within weeks. The timeless WHY belongs in the
comment; the session/PR context belongs in the PR description.

Non-blocking: prints an `additionalContext` warning when it finds a hit and
always exits 0. Scoped to `.py` / `.sh` files so Markdown headings and
docs (which legitimately carry dates) never trigger it.
"""
import sys
import json
import re

_DATE = re.compile(r'\b\d{4}-\d{2}-\d{2}\b')


def _has_dated_comment(line: str) -> bool:
    """True when a date follows a `#` on the line.

    The first `#` is enough: a date after any later `#` is also after the first.
    Searching only the text after it keeps this linear; the one-pattern form
    `#.*\\b<date>\\b` retries from every `#` and is quadratic on a line of hashes.
    """
    i = line.find('#')
    return i >= 0 and _DATE.search(line, i + 1) is not None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_input = payload.get('tool_input', {})
    path = tool_input.get('file_path', '')
    if not path.endswith(('.py', '.sh')):
        return 0

    # Edit supplies `new_string`; Write supplies `content`.
    added = tool_input.get('new_string') or tool_input.get('content') or ''

    hits = [line.strip() for line in added.splitlines() if _has_dated_comment(line)]

    if hits:
        msg = (
            'Warning: added comment line(s) contain a YYYY-MM-DD date. Dates rot '
            'in code comments — state the timeless WHY in the comment and keep '
            'session/PR context in the PR description. Lines: '
            + ' | '.join(hits[:3])
        )
        # hookSpecificOutput.additionalContext is the documented PreToolUse
        # output shape; a bare top-level `additionalContext` key (the prior
        # form here) isn't part of the contract and was a silent no-op.
        print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'additionalContext': msg}}))

    return 0


if __name__ == '__main__':
    sys.exit(main())
