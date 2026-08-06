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


# Every sibling git-touching hook bounds its subprocesses; these calls were the
# one exception, and they run on EVERY Edit/Write. An unbounded git is a hook
# that can hang forever — and the likeliest cause is precisely the state this
# hook family exists to detect: an index lock held by a concurrent session in
# the same clone. Expiry is caught below as just another git failure, which this
# hook already fails open on.
#
# 3s, not 5s: the bound exists to catch a WEDGED git, not to accommodate a slow
# one — `rev-parse` on a healthy repo answers in milliseconds. The number has to
# be small because worst case here is (call sites) x (this timeout), and that
# product is charged against a 15s handler shared with the other Edit/Write
# hooks. `_dispatch_lib.HOOK_WORST_CASE_SECONDS` records the product and the
# wiring test fails if the enforcing hooks stop fitting.
_GIT_TIMEOUT_SECONDS = 3


def _run_git(cwd: str, args: list[str]) -> subprocess.CompletedProcess[str] | None:
    # `subprocess.SubprocessError` is what carries TimeoutExpired; FileNotFoundError
    # needs no separate arm, being an OSError subclass. Matches the sibling hooks.
    try:
        return subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _clone_paths(cwd: str) -> tuple[str, str] | None:
    """Return (git_dir, git_common_dir) as realpaths, or None on failure.

    One `rev-parse` answering both questions, not two: it prints one line per
    requested option in argument order. Halving the process count halves this
    hook's worst-case contribution to the shared handler budget, which is what
    lets the enforcing hooks fit inside it at all.
    """
    r = _run_git(cwd, ["rev-parse", "--absolute-git-dir", "--git-common-dir"])
    if not r or r.returncode != 0:
        return None
    lines = r.stdout.strip().splitlines()
    if len(lines) < 2:
        return None
    git_dir = os.path.realpath(lines[0].strip())
    common = lines[1].strip()
    if not os.path.isabs(common):
        common = os.path.join(cwd, common)
    return git_dir, os.path.realpath(common)


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
