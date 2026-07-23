"""Detect in-progress git operations + (optionally) verify current branch.

Called by /spec-to-pr at every commit boundary (startup precheck, Ship
preflight, Revise push-prep, Archive commit) to catch:
  - An in-progress cherry-pick/merge/rebase that an external Claude session
    left running on the repo.
  - The working directory drifting onto a non-feature branch between phases.

Failure mode: a parallel Claude session has an in-progress `git cherry-pick`
on another branch. Mid-run, the working tree switches to that branch
externally; an Archive-phase `git add -A` then sweeps untracked files from that
cherry-pick into the archive commit — shipping unrelated content.

Output: single-line JSON on stdout. Exit codes:
  0 = clean (no in-progress op; branch matches --expect-branch if given)
  1 = fail-closed (cannot resolve .git, malformed worktree marker, git binary
      missing, or `git rev-parse` failure) — orchestrator MUST halt and surface
      to the user, NEVER infer "probably clean"
  2 = in-progress git operation detected
  3 = wrong branch (only when --expect-branch is passed)

Orchestrator contract: any exit code != 0 halts /spec-to-pr and surfaces to
the user via AskUserQuestion. Do NOT special-case "exit 1 is probably fine".
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _git_dir(repo_root: Path) -> Path | None:
    """Resolve the .git directory (handles worktrees where .git is a file).

    Returns None when the .git pointer is malformed, the resolved gitdir is
    missing, or the file is unreadable — callers MUST treat None as fail-closed
    (the safety check cannot vouch for this repo's state, so don't proceed).

    A regular repo: `.git` is a directory; return it directly.
    A worktree: `.git` is a text file containing `gitdir: <path>` (absolute or
    relative to the worktree root). Resolve the path; verify it's a directory.
    """
    git_path = repo_root / ".git"
    if git_path.is_dir():
        return git_path
    if git_path.is_file():
        try:
            line = git_path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            return None
        if not line.startswith("gitdir: "):
            return None
        target = Path(line[len("gitdir: "):])
        if not target.is_absolute():
            target = (repo_root / target).resolve()
        return target if target.is_dir() else None
    return None


def _detect_in_progress(git_dir: Path) -> str | None:
    """Return the name of any in-progress operation, or None."""
    if (git_dir / "CHERRY_PICK_HEAD").exists():
        return "cherry-pick"
    if (git_dir / "MERGE_HEAD").exists():
        return "merge"
    if (git_dir / "REVERT_HEAD").exists():
        return "revert"
    if (git_dir / "rebase-merge").is_dir():
        return "rebase (merge mode)"
    if (git_dir / "rebase-apply").is_dir():
        return "rebase (apply mode)"
    if (git_dir / "BISECT_LOG").exists():
        return "bisect"
    return None


def _current_branch(repo_root: Path) -> str | None:
    """Resolve current branch name. Returns None when `git rev-parse` fails
    (corrupt repo, git binary missing, permission denied) — callers MUST
    treat None as fail-closed. A detached-HEAD checkout returns the string
    `"HEAD"`, which is a valid (if unusual) state, NOT a failure.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root, capture_output=True, text=True,
        )
    except (OSError, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    return (result.stdout or "").strip() or None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expect-branch",
        help="If provided, exit 3 when current branch differs from this value.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repo root (defaults to cwd).",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    git_dir = _git_dir(repo_root)
    if git_dir is None:
        print(json.dumps({
            "clean": False,
            "error": (
                f"could not resolve a valid .git directory at {repo_root} "
                f"(not a git repo, missing .git pointer, malformed worktree marker, "
                f"or unreadable .git file)"
            ),
        }))
        print(f"git-state: cannot resolve .git at {repo_root}", file=sys.stderr)
        return 1

    branch = _current_branch(repo_root)
    if branch is None:
        print(json.dumps({
            "clean": False,
            "error": "git rev-parse --abbrev-ref HEAD failed",
            "current_branch": None,
            "expected_branch": args.expect_branch,
        }))
        print("git-state: could not resolve current branch", file=sys.stderr)
        return 1

    in_progress = _detect_in_progress(git_dir)

    out: dict[str, object] = {
        "clean": in_progress is None,
        "in_progress_op": in_progress,
        "current_branch": branch,
        "expected_branch": args.expect_branch,
    }

    if in_progress is not None:
        print(json.dumps(out))
        print(
            f"git-state: in-progress {in_progress} detected at {git_dir}",
            file=sys.stderr,
        )
        return 2

    if args.expect_branch is not None and branch != args.expect_branch:
        out["clean"] = False
        print(json.dumps(out))
        print(
            f"git-state: on branch {branch!r}, expected {args.expect_branch!r}",
            file=sys.stderr,
        )
        return 3

    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
