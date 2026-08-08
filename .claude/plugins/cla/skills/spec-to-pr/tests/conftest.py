"""Shared fixtures for spec-to-pr helper-script tests.

`tmp_repo` provides a `tmp_path`-rooted git repository with a fake openspec/
layout, suitable for staging artifact state in subsequent tests.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def tmp_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Initialize a tmp git repo with a basic openspec/ skeleton and a master branch
    pointed at one initial commit. Sets identity locally so commits work.
    (some-repo's default branch is `master`.)"""
    monkeypatch.chdir(tmp_path)
    _git("init", "-q", "-b", "master", cwd=tmp_path)
    _git("config", "user.email", "test@example.com", cwd=tmp_path)
    _git("config", "user.name", "Test", cwd=tmp_path)

    (tmp_path / "openspec" / "changes").mkdir(parents=True)
    (tmp_path / "openspec" / "specs").mkdir(parents=True)
    (tmp_path / "README.md").write_text("# tmp repo\n", encoding="utf-8")
    _git("add", "README.md", cwd=tmp_path)
    _git("commit", "-q", "-m", "initial", cwd=tmp_path)
    return tmp_path


def make_change(repo: Path, name: str, *, with_proposal: bool = True,
                tasks: list[bool] | None = None) -> Path:
    """Create a fake openspec change directory under `repo`. `tasks` is a list of
    booleans; True → checked, False → unchecked."""
    change_dir = repo / "openspec" / "changes" / name
    change_dir.mkdir(parents=True, exist_ok=True)
    if with_proposal:
        (change_dir / "proposal.md").write_text("## Why\nstub\n", encoding="utf-8")
    if tasks is not None:
        lines = ["## 1. Stub\n"]
        for i, done in enumerate(tasks, start=1):
            lines.append(f"- [{'x' if done else ' '}] 1.{i} task {i}\n")
        (change_dir / "tasks.md").write_text("".join(lines), encoding="utf-8")
    return change_dir


def commit_on_branch(repo: Path, branch: str, message: str, file: str = "README.md") -> None:
    """Switch to `branch` (creating it from the current branch if needed) and commit a change."""
    res = subprocess.run(["git", "rev-parse", "--verify", branch], cwd=repo, capture_output=True, text=True)
    if res.returncode != 0:
        _git("checkout", "-q", "-b", branch, cwd=repo)
    else:
        _git("checkout", "-q", branch, cwd=repo)
    p = repo / file
    p.write_text((p.read_text(encoding="utf-8") if p.exists() else "") + f"\n{message}\n", encoding="utf-8")
    _git("add", file, cwd=repo)
    _git("commit", "-q", "-m", message, cwd=repo)


@pytest.fixture(autouse=True)
def _pin_branch_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the branch prefix so tests never inherit the RUNNING repo's config.

    Autouse deliberately. The dependency is invisible at the call site -- a test
    asserting `feature/my-change` reads as self-contained -- so a test added
    later would silently inherit whatever `CLA_BRANCH_PREFIX` or the
    `branch-prefix.local.md` overlay happens to say on the machine running it.
    That is the same ambient-configuration defect as the locale-dependent
    subprocess harness fixed alongside this, where both sides agreed on the
    wrong value and the test passed for the wrong reason.
    """
    monkeypatch.setenv("CLA_BRANCH_PREFIX", "feature/")
