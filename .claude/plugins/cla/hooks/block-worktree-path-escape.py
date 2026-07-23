#!/usr/bin/env python3
"""PreToolUse hook: block Write/Edit calls that escape the current worktree.

Problem this solves
--------------------
`EnterWorktree` switches the session's cwd into an isolated linked worktree,
but nothing stops a subsequent `Write`/`Edit` call from targeting an absolute
path back in the primary clone (or another linked worktree) instead of the
current one. That silently defeats isolation: the file lands in a directory
another concurrent session may be using, and `guard-worktree-isolation.py`
does NOT catch it — that hook only intercepts `git checkout`/`switch`/
`commit`, never plain file writes.

Observed live: a session inside a worktree wrote new skill files via a
hardcoded absolute path back into the primary clone (e.g.
`C:\\Code\\<repo>\\.claude\\...`, copy-pasted from before the worktree
switch). The mistake was only caught because the OTHER session noticed the
new file. "Fixing" it by committing in the primary clone too then nearly lost
a commit to garbage collection when that clone's branch got switched/deleted
by the other session mid-flight.

Detection
---------
- Only acts when cwd is inside a LINKED worktree (`git rev-parse
  --absolute-git-dir` != `git rev-parse --git-common-dir` — the same test
  `guard-worktree-isolation.py` uses). A solo/primary-clone session is
  unaffected.
- Resolves the target `file_path` to a realpath and blocks only when it
  falls inside the PRIMARY CLONE's root (parent of `--git-common-dir`) but
  OUTSIDE the current worktree's own root (`--show-toplevel`). This also
  covers accidentally targeting a *different* linked worktree.
- Deliberately does NOT block paths outside the whole repo family entirely
  (e.g. a memory directory under the user's home, or a different repo like an
  update-cla source) — those are a different, legitimate pattern,
  not this bug.

Escape hatch: set `ALLOW_WORKTREE_PATH_ESCAPE=1` for a deliberate exception.

Exit codes:
  0 — allow (primary clone, non-worktree repo, target inside current
      worktree, target outside the repo family entirely, or any git/FS error)
  2 — block with stderr explaining how to fix the path

Best-effort: any parse/git/FS error exits 0 (fail-open) — a guard must never
break normal work.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys


def _run_git(cwd: str, args: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True,
        )
    except (OSError, FileNotFoundError):
        return None


def _clone_paths(cwd: str) -> tuple[str, str] | None:
    """Return (git_dir, git_common_dir) as realpaths, or None on failure."""
    gd = _run_git(cwd, ["rev-parse", "--absolute-git-dir"])
    gc = _run_git(cwd, ["rev-parse", "--git-common-dir"])
    if not gd or gd.returncode != 0 or not gc or gc.returncode != 0:
        return None
    git_dir = os.path.realpath(gd.stdout.strip())
    common = gc.stdout.strip()
    if not os.path.isabs(common):
        common = os.path.join(cwd, common)
    return git_dir, os.path.realpath(common)


def _worktree_root(cwd: str) -> str | None:
    tl = _run_git(cwd, ["rev-parse", "--show-toplevel"])
    if not tl or tl.returncode != 0:
        return None
    return os.path.realpath(tl.stdout.strip())


def _is_inside(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        # Different drives on Windows, etc. — definitely not inside.
        return False


def main() -> int:
    if os.environ.get("ALLOW_WORKTREE_PATH_ESCAPE") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    tool_input = payload.get("tool_input", {}) if isinstance(payload, dict) else {}
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not isinstance(file_path, str) or not file_path:
        return 0

    cwd = os.getcwd()
    clone_paths = _clone_paths(cwd)
    if clone_paths is None:
        return 0
    git_dir, git_common_dir = clone_paths
    if git_dir == git_common_dir:
        # Primary clone (or a non-worktree repo) — nothing to protect here.
        return 0

    worktree_root = _worktree_root(cwd)
    if worktree_root is None:
        return 0
    primary_clone_root = os.path.dirname(git_common_dir)

    target = os.path.realpath(
        file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path)
    )

    if not _is_inside(target, primary_clone_root):
        # Outside the whole repo family — e.g. a memory dir, a different
        # repo entirely. Different, legitimate pattern; not this bug.
        return 0
    if _is_inside(target, worktree_root):
        return 0

    print(
        f"blocked: this session is in worktree '{worktree_root}', but the write "
        f"target '{target}' resolves outside it (into the primary clone or "
        "another worktree). Once EnterWorktree has run, every Write/Edit for the "
        "rest of the task must target a path inside the current worktree, never "
        "a hardcoded path back to the primary clone. See memory "
        "'worktree-isolation-file-paths' for the incident this rule came from. "
        "Override for a deliberate exception by setting "
        "ALLOW_WORKTREE_PATH_ESCAPE=1 in the environment. "
        "(hook: block-worktree-path-escape.py)",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
