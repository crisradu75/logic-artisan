#!/usr/bin/env python3
"""Create an isolation worktree with plain git, bypassing the `EnterWorktree` tool.

Why this exists
---------------
On Windows, `EnterWorktree` can refuse to run with:

    Refusing to use <path> as an isolation worktree: git resolves its working
    tree to <same path, different letter case> ...

The two paths name the SAME directory. The harness compares the session's
launch-time project path against git's own resolution of it as literal strings,
and on a case-insensitive filesystem those can differ purely in casing — a repo
whose real directory name is capitalised, reached through an all-lowercase path,
produces one spelling of each. `core.ignorecase` being correctly `true` does not
help: the comparison never asks git.

Nothing in the repo can fix that; it is harness-side. But plain `git worktree`
is entirely unaffected — git resolves the paths properly — so the fallback is to
do the same work directly, which is what this script does.

What it does NOT do
-------------------
Dependency installs, env-file copying, and any other per-repo setup are
deliberately absent. Those differ per repo and belong in the calling skill plus
its `references/project-context.md` overlay, not in portable core.

The isolation guarantee is different too, and the caller must know it: a session
that entered via `EnterWorktree` has its file operations redirected into the
worktree automatically. A manually created worktree gets none of that — the
session is still rooted in the primary clone, so every subsequent path must
target the worktree explicitly. `block-worktree-path-escape.py` cannot help
either: it only fires for a session whose cwd IS the worktree.

Exit codes: 0 on success, 1 on failure (with a JSON `error` on stdout).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Bounded like every other subprocess in this plugin. `git worktree add` copies a
# checkout, so it gets materially longer than the `rev-parse` calls elsewhere.
GIT_TIMEOUT_SECONDS = 120
DEFAULT_WORKTREE_DIR = ".claude/worktrees"
DEFAULT_BRANCH_PREFIX = "worktree-"


class GitError(RuntimeError):
    """A git invocation failed; the message carries git's own stderr."""


def run_git(repo: Path, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:  # git not installed / not on PATH
        raise GitError(f"git is not available: {exc}") from exc
    except subprocess.SubprocessError as exc:  # includes TimeoutExpired
        raise GitError(f"git {' '.join(args)} did not complete: {exc}") from exc
    if check and proc.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed ({proc.returncode}): "
            f"{(proc.stderr or proc.stdout).strip()}"
        )
    return proc


def casing_mismatch(repo: Path) -> dict | None:
    """Report a case-only difference between `repo` as given and its real name.

    This is the exact condition that makes `EnterWorktree` refuse, so surfacing
    it turns a confusing tool error into a one-line diagnosis. Returns None when
    the paths agree, or when they differ by more than case (a genuinely
    different directory, which is not this bug).
    """
    as_given = os.path.abspath(str(repo))
    resolved = os.path.realpath(str(repo))
    if as_given == resolved:
        return None
    if as_given.lower() != resolved.lower():
        return None  # different directory entirely — not a casing issue
    return {
        "as_given": as_given,
        "on_disk": resolved,
        "explanation": (
            "These name the same directory but differ in letter case. "
            "EnterWorktree compares such paths as literal strings, so it refuses. "
            "Plain `git worktree` is unaffected; this script uses it directly."
        ),
    }


def _registered_worktrees(repo: Path) -> set[str]:
    """Absolute paths git currently has registered, realpath-normalised.

    Normalised because the whole point here is that the same directory can be
    spelled two ways; comparing raw strings would reintroduce the bug this
    script exists to route around.
    """
    out = run_git(repo, ["worktree", "list", "--porcelain"]).stdout
    found: set[str] = set()
    for line in out.splitlines():
        if line.startswith("worktree "):
            found.add(os.path.realpath(line[len("worktree "):].strip()))
    return found


def clean_stale_worktree(repo: Path, path: Path) -> bool:
    """Remove a half-created worktree at `path`. Returns True if anything went.

    A failed `EnterWorktree` registers the worktree with git BEFORE its safety
    check refuses, so the common state after one is a registered — often locked
    — entry that blocks the next attempt at the same path. Unlock/remove/prune
    are each best-effort: any of them legitimately fails when the corresponding
    state is absent, and that is not an error.
    """
    target = os.path.realpath(str(path))
    cleaned = False

    if target in _registered_worktrees(repo):
        run_git(repo, ["worktree", "unlock", str(path)], check=False)
        rm = run_git(repo, ["worktree", "remove", "--force", str(path)], check=False)
        cleaned = cleaned or rm.returncode == 0

    # Prunes entries whose directory is already gone — the other half of the
    # half-created state, which `remove` cannot address.
    run_git(repo, ["worktree", "prune"], check=False)

    # A leftover directory that git no longer knows about still blocks
    # `worktree add`. Only remove it when EMPTY: a non-empty unregistered
    # directory is somebody's work, and deleting it to make room would be the
    # exact "destroyed to fix a mistake" failure the skill warns about.
    if path.exists():
        try:
            path.rmdir()
            cleaned = True
        except OSError:
            pass
    return cleaned


def branch_exists(repo: Path, branch: str) -> bool:
    return run_git(
        repo, ["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], check=False
    ).returncode == 0


def create_worktree(
    repo: Path,
    name: str,
    base: str,
    worktree_dir: str = DEFAULT_WORKTREE_DIR,
    branch_prefix: str = DEFAULT_BRANCH_PREFIX,
) -> dict:
    """Create `<repo>/<worktree_dir>/<name>` on a new branch off `base`."""
    rel = f"{worktree_dir}/{name}"
    path = repo / worktree_dir / name
    branch = f"{branch_prefix}{name}"

    if branch_exists(repo, branch):
        raise GitError(
            f"branch '{branch}' already exists. Pick another name, or delete it "
            f"with `git branch -D {branch}` if it is finished with."
        )

    cleaned = clean_stale_worktree(repo, path)
    run_git(repo, ["worktree", "add", rel, "-b", branch, base])

    # Resolved from git rather than rebuilt by string-joining, so the caller gets
    # the canonical spelling instead of whichever casing happened to be typed.
    resolved = os.path.realpath(str(path))
    common = run_git(path, ["rev-parse", "--git-common-dir"]).stdout.strip()
    main_checkout = os.path.dirname(os.path.realpath(os.path.join(str(path), common)))

    return {
        "worktree_path": resolved,
        "relative_path": rel,
        "branch": branch,
        "base": base,
        "main_checkout": main_checkout,
        "cleaned_stale_entry": cleaned,
    }


def default_base(repo: Path) -> str:
    """`origin/<default>` when a remote HEAD is known, else the current branch.

    Matches what a harness-created worktree does (branch from the remote's
    default), while still working in a repo with no remote at all.
    """
    head = run_git(repo, ["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"], check=False)
    if head.returncode == 0 and head.stdout.strip():
        return head.stdout.strip().removeprefix("refs/remotes/")
    for candidate in ("origin/main", "origin/master"):
        if run_git(repo, ["rev-parse", "--verify", "--quiet", candidate],
                   check=False).returncode == 0:
            return candidate
    return "HEAD"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", help="worktree name (also the branch suffix)")
    parser.add_argument("--base", help="base ref; defaults to the remote's default branch")
    parser.add_argument("--repo", default=".", help="repo root (default: cwd)")
    parser.add_argument("--worktree-dir", default=DEFAULT_WORKTREE_DIR)
    parser.add_argument("--branch-prefix", default=DEFAULT_BRANCH_PREFIX)
    parser.add_argument(
        "--diagnose", action="store_true",
        help="only report whether this repo is exposed to the path-casing refusal",
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    try:
        mismatch = casing_mismatch(Path(args.repo))
        if args.diagnose:
            print(json.dumps({"casing_mismatch": mismatch}, indent=2))
            return 0
        if not args.name:
            parser.error("--name is required unless --diagnose is given")

        result = create_worktree(
            repo, args.name, args.base or default_base(repo),
            worktree_dir=args.worktree_dir, branch_prefix=args.branch_prefix,
        )
        result["casing_mismatch"] = mismatch
        print(json.dumps(result, indent=2))
        return 0
    except GitError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
