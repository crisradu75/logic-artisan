#!/usr/bin/env python3
"""PreToolUse hook: WARN (never block) when creating a feature branch off a non-base-branch base.

Branching new, unrelated work off a still-checked-out feature branch (e.g. right
after a `/spec-to-pr` Handoff leaves you on an unmerged `feature/...`) makes the new
PR absorb the prior branch's commits and orphans the prior PR.

This hook only WARNS (exit 0). Stacked PRs off a non-base-branch base are a legitimate flow,
so a hard block would over-fire — the warning just prompts a conscious confirm.

Detection: the Bash command creates a branch in any create-and-switch form
(`git checkout -b|-B|--orphan <name>` / `git switch -c|-C|--create <name>`),
optionally behind git global options, AND `git rev-parse --abbrev-ref HEAD`
is not the repo's base branch — resolved via `_dispatch_lib.default_base_branch()`
(origin/HEAD, else an existing `main`/`master`), NOT hardcoded, so a
`main`-default repo doesn't warn on every branch it creates. Quoted spans are
collapsed before matching, so a `git checkout -b x` inside an echoed string
does not trigger the warning.

Exit codes:
  0 — always (allow). Prints a stderr reminder when the non-base-branch case is detected.

Best-effort: any parse/git failure exits 0 silently — a warning hook must never
disrupt the workflow.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

from pathlib import Path

# The `_dispatch_lib` import below resolves through `sys.path`; running
# standalone normally puts the hooks dir at `sys.path[0]`, but that is
# suppressed under `PYTHONSAFEPATH=1` / `python -I` / `python -P`. Insert it
# explicitly so an import failure can't silently disable this hook.
_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from _dispatch_lib import GIT_GLOBAL_OPTS as _G  # noqa: E402
from _dispatch_lib import default_base_branch, strip_quoted_spans  # noqa: E402

# Every create-and-switch form: `git checkout -b|-B|--orphan NAME`,
# `git switch -c|-C|--create NAME`. The full set is deliberate — it matches
# `guard-worktree-isolation.py`'s `_BRANCH_CREATE`, so the two hooks agree on
# what "creating a branch" means. (`-B` and `--orphan` move HEAD onto a new
# branch exactly as `-b` does, so they carry the same wrong-base hazard.)
# Intentionally NOT matched: `git branch NAME` (creates a ref WITHOUT moving HEAD, so
# the new branch's base is whatever you later check out — the off-non-base-branch hazard
# this hook guards only arises on the create-and-switch forms above).
_BRANCH_CREATE = re.compile(
    r"\bgit\s+" + _G + r"(?:checkout\s+(?:-b|-B|--orphan)|switch\s+(?:-c|-C|--create))\s+(\S+)"
)


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

    # Strip quoted spans BEFORE matching: a quoted `-c`/`-C` value containing a
    # space (`git -C "/path with space" checkout -b x`, e.g. a worktree at a
    # checkout path with a space in it) otherwise breaks `_G`'s `\S+`
    # value-token match and the branch-create shape slips past undetected.
    # `strip_quoted_spans` is length-preserving specifically so group 1's
    # offsets stay valid against the ORIGINAL `cmd` below — re-slicing from
    # there (not `scanned`) is what keeps the printed branch name real when it
    # was itself quoted, instead of the scan-time placeholder text.
    scanned = strip_quoted_spans(cmd)
    m = _BRANCH_CREATE.search(scanned)
    if not m:
        return 0
    new_branch = cmd[m.start(1) : m.end(1)].strip("'\"")

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

    # Resolve the repo's ACTUAL base branch rather than assuming `master`. In a
    # `main`-default repo the old hardcoded comparison made every single branch
    # creation warn — including the correct `main` -> `feature/x` case — which
    # trains the reader to ignore the hook entirely.
    base = default_base_branch()
    if current and current != base:
        print(
            f"[warn-branch-base] creating '{new_branch}' off '{current}', not {base}. "
            f"If this is a fresh, unrelated branch, `git switch {base}` first. "
            f"If it's an intentional stacked PR, proceed.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
