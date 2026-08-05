#!/usr/bin/env python3
"""PreToolUse hook: block `cd` directives inside Bash tool calls.

The `cd` shell builtin persists working directory across Bash tool calls in
this session, which silently breaks subsequent commands that assume the
project root, so never use a compound Bash `cd && cmd` — the working dir is
already the project root. This deterministic hook enforces that.

Detection: scan the Bash command for any unquoted occurrence of `cd ` as a
shell directive. Specifically block:
  - leading `cd ` / `cd\t` / `cd;` / `cd&`
  - ` && cd `, ` || cd `, ` ; cd `
  - newline-followed-`cd `

Allow `cd` when it appears inside quoted strings (commit messages, docstrings,
echoed prose). The matcher walks the command token-by-token outside quotes.

Exit codes:
  0 — allow (no cd detected, or cd only inside quoted text)
  2 — block with stderr explaining the rule

This hook is best-effort: a sufficiently adversarial heredoc or process
substitution can still slip a cd past it, but the common offenses
(`cd subdir && cmd`, `cd /some/path; cmd`, leading `cd ...`) are caught.
"""

from __future__ import annotations

import json
import re
import sys


def cd_outside_quotes(cmd: str) -> bool:
    """Return True iff `cd ` appears outside quoted text in `cmd`."""
    # Strip single-quoted, double-quoted, and backtick-quoted spans.
    # Doesn't handle nested or escaped quotes perfectly, but covers the
    # 99% case where prose / commit messages are the only `cd` sources.
    stripped = re.sub(r"'[^']*'", "''", cmd)
    stripped = re.sub(r'"[^"]*"', '""', stripped)
    stripped = re.sub(r"`[^`]*`", "``", stripped)
    # Match `cd` as a directive: start of string / after `;` / `&` / `|` /
    # newline, followed by whitespace and at least one more char.
    pattern = re.compile(r"(?:^|[;&|\n])\s*cd\s+\S", re.MULTILINE)
    return bool(pattern.search(stripped))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # malformed input — don't block
    tool_input = payload.get("tool_input", {}) if isinstance(payload, dict) else {}
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        return 0
    if not cd_outside_quotes(command):
        return 0
    print(
        "blocked: shell command contains `cd`; the working dir is already the "
        "project root and `cd` persists across calls, breaking subsequent commands. "
        "Use absolute paths or pass the working dir to the inner tool instead. "
        "(hook: block-cd-in-bash.py)",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
