"""branch.py tests."""

from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path

import pytest

import branch
from conftest import commit_on_branch


@pytest.fixture(autouse=True)
def _repo_root(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(branch, "REPO_ROOT", tmp_repo)


def test_branch_name_format():
    assert branch._branch_name("add-foo") == "feature/add-foo"


def test_creates_when_missing(tmp_repo: Path, monkeypatch):
    # tmp_repo has no origin remote; pretend remote check returned "branch absent".
    monkeypatch.setattr(branch, "_exists_on_remote", lambda b: False)
    rc = branch.main(["new-thing"])
    assert rc == 0
    res = subprocess.run(["git", "rev-parse", "--verify", "feature/new-thing"],
                         cwd=tmp_repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res.returncode == 0


def test_dry_run_does_not_create(tmp_repo: Path, monkeypatch, capsys):
    monkeypatch.setattr(branch, "_exists_on_remote", lambda b: False)
    rc = branch.main(["new-thing", "--dry-run"])
    assert rc == 0
    res = subprocess.run(["git", "rev-parse", "--verify", "feature/new-thing"],
                         cwd=tmp_repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res.returncode != 0
    out = capsys.readouterr().out
    assert "would create" in out


def test_local_collision_exits_3(tmp_repo: Path, capsys):
    commit_on_branch(tmp_repo, "feature/exists", "first commit")
    subprocess.run(["git", "checkout", "master"], cwd=tmp_repo, capture_output=True)
    rc = branch.main(["exists"])
    assert rc == 3
    err = capsys.readouterr().err
    assert "already exists locally" in err
    assert dt.date.today().isoformat() in err  # date-suffixed alternative is named


def test_remote_collision_exits_3(tmp_repo: Path, monkeypatch, capsys):
    # Mock _exists_on_remote to return True
    monkeypatch.setattr(branch, "_exists_on_remote", lambda b: True)
    rc = branch.main(["something"])
    assert rc == 3
    err = capsys.readouterr().err
    assert "already exists on origin" in err


def test_remote_unreachable_exits_5(tmp_repo: Path, monkeypatch, capsys):
    """Network/auth/missing-remote returns None from _exists_on_remote → exit 5
    (was previously silently treated as 'branch is free')."""
    monkeypatch.setattr(branch, "_exists_on_remote", lambda b: None)
    rc = branch.main(["something"])
    assert rc == 5
    err = capsys.readouterr().err
    assert "could not determine remote state" in err
