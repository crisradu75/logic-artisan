"""Derive feature branch name and create it (or print the date-suffixed alternative on collision)."""

# Spec: spec-to-pr-orchestration#three-commit-branch-convention

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    """Repo root via git (location-independent — works from the plugin, unlike a
    fixed `parents[N]` depth). Falls back to cwd if git is unavailable; tests
    monkeypatch REPO_ROOT directly."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.cwd()


REPO_ROOT = _repo_root()


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    # encoding="utf-8" is explicit so Windows doesn't decode git output as cp1252
    # and corrupt non-ASCII branch names, commit messages, or paths.
    return subprocess.run(cmd, cwd=cwd if cwd is not None else REPO_ROOT,
                          capture_output=True, text=True, encoding="utf-8")


def _branch_name(change_name: str) -> str:
    return f"feature/{change_name}"


def _exists_locally(branch: str) -> bool:
    return _run(["git", "rev-parse", "--verify", branch]).returncode == 0


def _exists_on_remote(branch: str) -> bool | None:
    """Return True if branch exists on origin, False if confirmed absent,
    None if remote could not be reached (network/auth/missing-remote)."""
    res = _run(["git", "ls-remote", "--exit-code", "--heads", "origin", branch])
    if res.returncode == 0:
        return True
    if res.returncode == 2:  # --exit-code: ref not found
        return False
    # Any other rc (auth failure, malformed ref, transport error, missing remote)
    # collapses to "could not be reached". Surface stderr so the orchestrator
    # can show the user *why* — without this, a 403 looks identical to "no network".
    if res.stderr:
        print(f"git ls-remote (rc={res.returncode}): {res.stderr.strip()}", file=sys.stderr)
    return None


def _date_suffix() -> str:
    return dt.date.today().isoformat()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="branch")
    parser.add_argument("change_name")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    branch = _branch_name(args.change_name)
    alternative = f"{branch}-{_date_suffix()}"

    if _exists_locally(branch):
        print(f"branch {branch} already exists locally; rerun with: {alternative}", file=sys.stderr)
        return 3
    remote = _exists_on_remote(branch)
    if remote is True:
        print(f"branch {branch} already exists on origin; rerun with: {alternative}", file=sys.stderr)
        return 3
    if remote is None:
        print(f"could not determine remote state of {branch} (network/auth/missing-remote); refusing to create local branch",
              file=sys.stderr)
        return 5

    if args.dry_run:
        print(f"would create branch {branch}")
        return 0

    res = _run(["git", "checkout", "-b", branch])
    if res.returncode != 0:
        print(res.stderr.strip(), file=sys.stderr)
        return 4
    print(branch)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
