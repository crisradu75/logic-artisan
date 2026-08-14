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

SHADOWING IS ALSO BLOCKED, and for a different reason than the rest of this
hook. `cd() { :; }` and `alias cd=true` do not change any working directory —
they change what the WORD `cd` means, so a later `cd foo && cmd` in the same
command is a no-op and sails past the matcher above. That is not a mistake a
user makes by accident; it is the shape of deliberately routing around this
guard, which happened once in this repo's own development. A guard that can be
switched off by the thing it guards is not a guard, so the redefinition itself
is the offense — blocked whether or not a `cd` follows it.

Scope note: `git`, `rm` and `gh` are policed by sibling hooks and are shadowable
the same way. That is deliberately NOT covered here — this hook owns `cd`, and a
general "no shadowing any guarded command" check belongs in the dispatcher if the
evasion ever recurs against another guard. One real offense, one narrow fix.

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

# `cd() {`, `cd ()  {`, `function cd {`, `function cd() {`, `alias cd=...`.
# Anchored the same way as the directive matcher — start of string or after a
# shell separator — so `echo foo | grep cd()` in prose does not trip it.
_SHADOW = re.compile(
    r"(?:^|[;&|\n])\s*(?:"
    r"function\s+cd\b(?:\s*\(\s*\))?\s*\{"   # function cd {   /  function cd() {
    r"|cd\s*\(\s*\)\s*\{"                    # cd() {          /  cd ()  {
    r"|alias\s+cd="                          # alias cd=...
    r")",
    re.MULTILINE,
)


def _strip_quoted(cmd: str) -> str:
    """Blank out single-, double-, and backtick-quoted spans.

    Doesn't handle nested or escaped quotes perfectly, but covers the 99% case
    where prose / commit messages are the only `cd` sources.
    """
    stripped = re.sub(r"'[^']*'", "''", cmd)
    stripped = re.sub(r'"[^"]*"', '""', stripped)
    return re.sub(r"`[^`]*`", "``", stripped)


def shadows_cd(cmd: str) -> bool:
    """Return True iff `cmd` redefines `cd` as a function or alias."""
    return bool(_SHADOW.search(_strip_quoted(cmd)))


def cd_outside_quotes(cmd: str) -> bool:
    """Return True iff `cd ` appears outside quoted text in `cmd`."""
    stripped = _strip_quoted(cmd)
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
    if shadows_cd(command):
        print(
            "blocked: this command redefines `cd` as a shell function or alias. "
            "Redefining a command that a guard hook polices disables the guard for "
            "the rest of the call — if `cd` is in your way, use absolute paths or "
            "pass the working dir to the inner tool. If the guard is genuinely wrong "
            "here, say so and let the user decide; do not route around it. "
            "(hook: block-cd-in-bash.py)",
            file=sys.stderr,
        )
        return 2
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
