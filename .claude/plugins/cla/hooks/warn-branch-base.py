#!/usr/bin/env python3
"""PreToolUse hook: WARN (never block) when creating a feature branch off a non-master base.

Branching new, unrelated work off a still-checked-out feature branch (e.g. right
after a `/spec-to-pr` Handoff leaves you on an unmerged `feature/...`) makes the new
PR absorb the prior branch's commits and orphans the prior PR.

This hook only WARNS (exit 0). Stacked PRs off a non-master base are a legitimate flow,
so a hard block would over-fire — the warning just prompts a conscious confirm.

Detection: the Bash command creates a branch (`git checkout -b <name>` /
`git switch -c <name>` / `git switch --create <name>`) AND `git rev-parse
--abbrev-ref HEAD` is not `master`.

Exit codes:
  0 — always (allow). Prints a stderr reminder when the non-master-base case is detected.

Best-effort: any parse/git failure exits 0 silently — a warning hook must never
disrupt the workflow.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

# git checkout -b NAME   |   git switch -c NAME   |   git switch --create NAME
# Intentionally NOT matched: `git branch NAME` (creates a ref WITHOUT moving HEAD, so
# the new branch's base is whatever you later check out — the off-non-master-base hazard
# this hook guards only arises on the create-and-switch forms above).
_BRANCH_CREATE = re.compile(
    r"\bgit\s+(?:checkout\s+-b|switch\s+(?:-c|--create))\s+(\S+)"
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    cmd = (payload.get("tool_input") or {}).get("command", "")
    if not isinstance(cmd, str) or not cmd:
        return 0

    m = _BRANCH_CREATE.search(cmd)
    if not m:
        return 0
    new_branch = m.group(1).strip("'\"")

    try:
        head = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return 0
    if head.returncode != 0:
        return 0
    current = head.stdout.strip()

    # Detached HEAD reports as "HEAD" — not a named base, so the warning would be
    # misleading. Skip it (the detached state is its own signal to the user).
    if current == "HEAD":
        return 0

    if current and current != "master":
        print(
            f"[warn-branch-base] creating '{new_branch}' off '{current}', not master. "
            f"If this is a fresh, unrelated branch, `git switch master` first. "
            f"If it's an intentional stacked PR, proceed.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
