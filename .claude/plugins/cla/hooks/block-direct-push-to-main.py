#!/usr/bin/env python3
"""PreToolUse hook: block direct `git push` to main/master.

Convention: no direct commits to the default branch — use feature branches.
A retroactive paperwork-PR after the fact is structurally impossible (GitHub
refuses no-diff PRs), so the only fix is
to prevent the push at the moment it would happen.

Detection: scan the Bash command for `git push` shapes that target main/master
directly. Specifically block:
  - `git push <remote> main` / `git push <remote> master`
  - `git push <remote> HEAD:main` / `git push <remote> HEAD:master`
  - `git push <remote> <branch>:main` / `... :master`
  - Same with `--force` / `-f` / `--force-with-lease`

Allow:
  - `git push -u origin feature/...` (any non-main destination)
  - `git push` with no refspec when current branch is NOT main
  - Any push when the env var `ALLOW_PUSH_TO_MAIN=1` is set (escape hatch for
    the rare legitimate case — e.g. an admin restoring after force-push).

Exit codes:
  0 — allow
  2 — block with stderr explaining the rule

Best-effort: a `git push` invoked via a sub-shell or alias may slip past it.
The common offense (`git push origin main` from a session that drifted onto
main) is caught.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys


# git GLOBAL options that may sit between `git` and `push` — consumed so
# `git -C /path push origin main` is not a bypass. Mirrors guard-worktree-isolation.py's `_G`.
_G = r"(?:(?:-[cC]\s+\S+|-[A-Za-z]|--[A-Za-z][\w-]*(?:=\S+)?)\s+)*"
_GIT_PUSH = r"\bgit\s+" + _G + r"push\b"

# Match any `git push ... <something>:main` / `... main` / same for master.
# The push refspec is the LAST positional arg after `push` (modulo flags).
# This regex catches the most common shapes; obscure ones (e.g. via alias)
# slip past — that's accepted, the hook is advisory-strong, not adversarial.
_DIRECT_PUSH_PATTERNS = [
    # `git push <remote> main` or `git push <remote> master`
    re.compile(_GIT_PUSH + r"(?:\s+(?:-[a-zA-Z]+|--\S+))*\s+\S+\s+(?:HEAD:|[\w/.-]+:)?(?:main|master)\b"),
    # `git push origin main:something` (pushing TO main on another ref name)
    re.compile(_GIT_PUSH + r"(?:\s+(?:-[a-zA-Z]+|--\S+))*\s+\S+\s+(?:main|master):"),
]


def _current_branch() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True,
        )
    except (OSError, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    return (result.stdout or "").strip() or None


def _strip_quoted_spans(cmd: str) -> str:
    """Remove single-, double-, and backtick-quoted spans so the matcher does
    not trip on a literal `git push origin main` inside echoed prose, a
    heredoc body, or a string argument. Mirrors `block-cd-in-bash.py`'s
    `cd_outside_quotes` approach. Doesn't handle escaped or nested quotes
    perfectly — covers the 99% case where the legitimate offense is the
    command itself, not a quoted literal."""
    stripped = re.sub(r"'[^']*'", "''", cmd)
    stripped = re.sub(r'"[^"]*"', '""', stripped)
    stripped = re.sub(r"`[^`]*`", "``", stripped)
    return stripped


def _is_direct_push_to_main(command: str) -> bool:
    """Return True iff the command shape pushes to main/master directly."""
    scanned = _strip_quoted_spans(command)
    for pat in _DIRECT_PUSH_PATTERNS:
        if pat.search(scanned):
            return True
    # Bare `git push` (no refspec) → check current branch. If HEAD is main
    # and we're about to push, the upstream is almost certainly origin/main.
    bare_push = re.search(_GIT_PUSH + r"(?:\s+(?:-[a-zA-Z]+|--\S+))*\s*$", scanned)
    if bare_push:
        branch = _current_branch()
        if branch in ("main", "master"):
            return True
    return False


def main() -> int:
    if os.environ.get("ALLOW_PUSH_TO_MAIN") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    tool_input = payload.get("tool_input", {}) if isinstance(payload, dict) else {}
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        return 0
    if not _is_direct_push_to_main(command):
        return 0
    print(
        "blocked: `git push` targets main/master directly. No direct commits to "
        "the default branch — create a feature branch first: "
        "`git checkout -b feature/<name>` -> commit -> push -> "
        "open a PR via `gh pr create`. Override for a genuine emergency by "
        "setting `ALLOW_PUSH_TO_MAIN=1` in the environment. "
        "(hook: block-direct-push-to-main.py)",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
