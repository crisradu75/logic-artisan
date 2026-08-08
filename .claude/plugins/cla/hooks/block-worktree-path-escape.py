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
from pathlib import Path

# This hook runs standalone under the tests' own module loader as well as via
# the Edit/Write dispatcher, so the sys.path setup can't be assumed done by a
# caller — same defensive pattern as guard-worktree-isolation.py, which shares
# `_run_git`/`_clone_paths` with this file via `_dispatch_lib`.
_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from _dispatch_lib import run_git as _run_git  # noqa: E402
from _dispatch_lib import clone_paths as _clone_paths  # noqa: E402


def _warn(msg: str) -> None:
    """Surface a guard-disabling/degraded condition (repo policy: recoverable ->
    Warning on stderr). The hook still fails OPEN — it prints, then returns 0.

    Mirrors `guard-worktree-isolation._warn`. This file had none, so every
    degraded path returned 0 in silence — an enforcing guard that stopped
    enforcing and looked identical to one that ran and allowed.
    """
    print(f"[block-worktree-path-escape] warn: {msg}", file=sys.stderr)


def _is_work_tree(cwd: str) -> bool:
    """True when `cwd` is inside a git work tree.

    Separates "git could not answer" (degraded — worth announcing) from "there
    is no repo here" (ordinary — silent). Without this the warning fires on
    every write in a scratch directory, and a diagnostic that cries wolf takes
    the real one down with it.
    """
    r = _run_git(cwd, ["rev-parse", "--is-inside-work-tree"])
    return bool(r and r.returncode == 0 and r.stdout.strip() == "true")


def _worktree_root(cwd: str) -> str | None:
    tl = _run_git(cwd, ["rev-parse", "--show-toplevel"])
    if not tl or tl.returncode != 0:
        return None
    return os.path.realpath(tl.stdout.strip())


def _is_inside(path: str, root: str) -> bool:
    """Containment test that does not depend on the two paths being spelled alike.

    Callers realpath both sides first, which on WINDOWS also canonicalises
    letter case — that is why this guard survives the path-casing divergence
    that breaks `EnterWorktree`. On a case-insensitive POSIX filesystem (macOS
    APFS by default) `realpath` resolves symlinks but leaves case alone, so a
    plain string comparison there would answer False for a path that really is
    inside the worktree, and this guard would fail open on exactly the platform
    class it was assumed safe on.

    So: `normcase` first (a no-op off Windows, harmless on it), then an inode
    comparison as the fallback that is immune to spelling altogether.
    """
    try:
        if os.path.commonpath([os.path.normcase(path), os.path.normcase(root)]) == (
            os.path.normcase(root)
        ):
            return True
    except ValueError:
        # Different drives on Windows, etc. — definitely not inside.
        return False
    return _is_inside_by_inode(path, root)


def _is_inside_by_inode(path: str, root: str) -> bool:
    """Walk `path` upward looking for a directory that IS `root` by inode.

    `os.stat` answers "same directory?" without caring how either was spelled,
    which is what makes this correct on a case-insensitive filesystem whose
    case `realpath` did not fold. The write target itself usually does not
    exist yet (that is the point of a PreToolUse hook), so ancestors that
    cannot be stat'ed are skipped rather than treated as a miss.
    """
    try:
        root_stat = os.stat(root)
    except OSError:
        return False
    current = os.path.abspath(path)
    while True:
        try:
            if os.path.samestat(os.stat(current), root_stat):
                return True
        except OSError:
            pass  # ancestor does not exist yet — keep climbing
        parent = os.path.dirname(current)
        if parent == current:  # filesystem root; nothing above it
            return False
        current = parent


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

    # The session's directory, not this hook process's. Everything below hinges
    # on it: the git calls that decide whether we are even IN a linked worktree
    # run here, and a relative `file_path` resolves against it. Reading it from
    # the process meant that whenever the two diverged, this hook reasoned about
    # the wrong tree — and divergence is the normal state for the worktree
    # sessions it exists to protect. Falls back to the process cwd when the
    # payload omits it (the hook's own tests set the process cwd instead).
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    if not isinstance(cwd, str) or not cwd:
        cwd = os.getcwd()

    clone_paths = _clone_paths(cwd)
    if clone_paths is None:
        # This is an ENFORCING guard failing open. A wedged git or a held
        # `index.lock` is precisely the concurrent-session scenario the hook
        # exists for, so degrading there without a word means a write can escape
        # the worktree in exactly the situation it was written to prevent.
        #
        # But `_clone_paths` also returns None for the commonest and most benign
        # reason of all -- the directory is not a git repo. Warning on that fires
        # on every write in a scratch directory, which is how a diagnostic gets
        # tuned out and takes the real one with it. So ask whether this is a
        # work tree at all, and only speak up when it is. One extra subprocess,
        # on the already-failed path only.
        if _is_work_tree(cwd):
            _warn(f"could not resolve git dirs for {cwd!r}; not checking this write")
        return 0
    git_dir, git_common_dir = clone_paths
    if git_dir == git_common_dir:
        # Primary clone (or a non-worktree repo) — nothing to protect here.
        return 0

    worktree_root = _worktree_root(cwd)
    if worktree_root is None:
        # Same reasoning: we already know this IS a linked worktree (git_dir !=
        # git_common_dir), so failing to resolve its root is a degraded git, not
        # a benign shape. Silence here is the difference between "checked and
        # allowed" and "never checked".
        _warn(f"in a worktree but could not resolve its root from {cwd!r}; not checking")
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
