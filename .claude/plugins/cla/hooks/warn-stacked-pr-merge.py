#!/usr/bin/env python3
"""PreToolUse hook: WARN (never block) when `gh pr merge --delete-branch` would
auto-close an open stacked child PR.

Deleting a base PR's branch on merge auto-closes any PR whose *base* is that
branch, and GitHub refuses to reopen a PR whose base branch is gone ("Cannot
change the base branch of a closed pull request").

Detection: the Bash command runs `gh pr merge ... --delete-branch` (or `-d`).
Resolve the merged PR's head branch, then query `gh pr list --base <head>
--state open` for stacked children; warn only if any exist.

This hook only WARNS (exit 0). Stacked PRs are a legitimate flow and the fix
(`gh pr edit <child> --base <base-branch>`, or dropping `--delete-branch`) is the user's
call, so a hard block would over-fire.

Best-effort: any parse / missing-gh / offline / non-zero-`gh` failure exits 0
silently — a warning hook must never disrupt the workflow or stall on network.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# See the sibling git hooks: the `_dispatch_lib` import resolves through
# `sys.path`, which standalone runs populate only via `sys.path[0]`.
_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from _dispatch_lib import default_base_branch  # noqa: E402

_GH_MERGE = re.compile(r"\bgh\s+pr\s+merge\b")
_DELETE_BRANCH = re.compile(r"(?:^|\s)(?:--delete-branch|-d)(?:\s|=|$)")
# A standalone PR-number token after `gh pr merge` (whitespace-bounded so a branch
# name like `feature/foo-2` is not misread as PR "2"). Absent → current-branch PR.
_PR_NUMBER = re.compile(r"(?:^|\s)(\d+)(?:\s|$)")


def _gh(args: list[str]) -> str | None:
    """Run a gh subcommand; return stripped stdout, or None on any failure."""
    try:
        r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _current_branch() -> str | None:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _wants_stacked_check(cmd: str) -> bool:
    """True iff `cmd` is a `gh pr merge … --delete-branch` with deletion NOT disabled.

    `--delete-branch=false` / `=0` / `=no` explicitly keeps the branch, so it is not
    a stacked-child hazard and must not warn.
    """
    if not _GH_MERGE.search(cmd) or not _DELETE_BRANCH.search(cmd):
        return False
    if re.search(r"--delete-branch=(?:false|0|no)\b", cmd):
        return False
    return True


def _target_pr_number(cmd: str) -> str | None:
    """The explicit PR number in the `gh pr merge` sub-command, or None.

    Scoped to the merge sub-command (cut at the first shell operator) so a bare
    integer in a chained `&& …` / `; …` command is not misread as the merge target.
    Branch-name and URL targets carry no whitespace-bounded bare integer and yield
    None — best-effort: the caller then checks the CURRENT branch, which may differ
    from a URL/branch target (a missed or mis-aimed warning, never a block).
    """
    m = _GH_MERGE.search(cmd)
    if not m:
        return None
    sub = re.split(r"\s*(?:&&|\|\||;|\|)\s*", cmd[m.end():], maxsplit=1)[0]
    num = _PR_NUMBER.search(sub)
    return num.group(1) if num else None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    cmd = (payload.get("tool_input") or {}).get("command", "")
    if not isinstance(cmd, str) or not cmd:
        return 0

    if not _wants_stacked_check(cmd):
        return 0
    if shutil.which("gh") is None:
        return 0

    # Resolve the head branch of the PR being merged (explicit number → that PR;
    # no target → the current branch's PR).
    number = _target_pr_number(cmd)
    if number:
        head = _gh(["pr", "view", number, "--json", "headRefName", "-q", ".headRefName"])
    else:
        head = _current_branch()
    if not head or head == "HEAD":
        return 0

    raw = _gh(["pr", "list", "--base", head, "--state", "open", "--json", "number,title"])
    if not raw:
        return 0
    try:
        children = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(children, list) or not children:
        return 0

    listed = ", ".join(f"#{c.get('number')}" for c in children if c.get("number"))
    print(
        f"[warn-stacked-pr-merge] '{head}' is the base of open PR(s) {listed}. "
        f"Merging with --delete-branch auto-closes them and GitHub refuses to reopen. "
        f"Retarget first: gh pr edit <child> --base {default_base_branch()} "
        f"(or drop --delete-branch).",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
