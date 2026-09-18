"""Detect in-progress git operations + (optionally) verify current branch.

Called by /spec-to-pr at every commit boundary (startup precheck, Ship
preflight, Revise push-prep, Archive commit) to catch:
  - An in-progress cherry-pick/merge/rebase that an external Claude session
    left running on the repo.
  - The working directory drifting onto a non-feature branch between phases.

This script does NOT inspect the working tree for uncommitted files. The
`no_in_progress_op` field means exactly what it says — no cherry-pick / merge /
rebase / revert / bisect is mid-flight — and is true with any number of modified
files present. It was called `clean` until a run read `{"clean": true}` with 47
files staged and concluded the tree was clean. For dirty-tree state, call
`git status --porcelain` separately; the two checks answer different questions
and both are load-bearing at a commit boundary.

It is also TRUE ON A BRANCH MISMATCH (exit 3), for the same reason. Being on the
wrong branch is not an in-progress operation, and the field answers one question
only. It reported False there until this was fixed — the `clean` conflation
again, pointing the other way. Read the EXIT CODE for the verdict; the field is a
detail of one specific check, not a summary of the run. The only path on which it
is False without an operation being mid-flight is exit 1, where nothing could be
determined at all and fail-closed is the whole point.

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
            cwd=repo_root, capture_output=True, text=True, encoding="utf-8", errors="replace",
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
            "no_in_progress_op": False,
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
            "no_in_progress_op": False,
            "error": "git rev-parse --abbrev-ref HEAD failed",
            "current_branch": None,
            "expected_branch": args.expect_branch,
        }))
        print("git-state: could not resolve current branch", file=sys.stderr)
        return 1

    in_progress = _detect_in_progress(git_dir)

    out: dict[str, object] = {
        "no_in_progress_op": in_progress is None,
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
        # `no_in_progress_op` is NOT overwritten here, and that is the fix this
        # branch exists for. Reaching this line means `in_progress is None` — no
        # cherry-pick, merge, rebase, revert or bisect is mid-flight — so forcing
        # the field to False reported an operation that does not exist.
        #
        # It is the same conflation that made this field's old name a defect,
        # pointing the other way. `clean` was renamed to `no_in_progress_op`
        # because a run read `{"clean": true}` with 47 files staged and concluded
        # the tree was clean; folding branch state into it here made the field
        # answer a second question again. The module docstring says it "means
        # exactly what it says", and now it does on every path.
        #
        # THE BRANCH MISMATCH IS NOT LOST: it is carried by exit code 3, by
        # `current_branch` and `expected_branch` in this same payload, and by the
        # stderr line below — three independent signals, none of which needed
        # this field's help. The orchestrator contract every caller follows is
        # "any non-zero exit halts", so no caller has to read the field to see it.
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
