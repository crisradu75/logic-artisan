"""_git_common.py tests.

Every consumer (branch.py, commit.py, check_permissions.py, discover_tests.py,
probe_state.py) monkeypatches its own module-level `REPO_ROOT` directly in
tests, so `repo_root()`'s actual git-invocation and fallback logic was never
exercised by any of those five test files, before or after the extraction
that consolidated five identical copies into this one function. These tests
close that gap.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import _git_common


def test_resolves_the_real_toplevel_from_a_nested_directory(
    monkeypatch, tmp_path: Path
) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    assert _git_common.repo_root().resolve() == tmp_path.resolve()


def test_falls_back_to_cwd_when_git_is_unavailable(monkeypatch, tmp_path: Path) -> None:
    def boom(*_a, **_kw):
        raise FileNotFoundError("git not on PATH")

    monkeypatch.setattr(_git_common.subprocess, "run", boom)
    monkeypatch.chdir(tmp_path)
    assert _git_common.repo_root() == tmp_path


def test_falls_back_to_cwd_on_timeout(monkeypatch, tmp_path: Path) -> None:
    def boom(*_a, **_kw):
        raise subprocess.TimeoutExpired(cmd="git", timeout=10)

    monkeypatch.setattr(_git_common.subprocess, "run", boom)
    monkeypatch.chdir(tmp_path)
    assert _git_common.repo_root() == tmp_path


def test_falls_back_to_cwd_when_git_rejects_the_directory(
    monkeypatch, tmp_path: Path
) -> None:
    # git's own "not a repository" exit: non-zero returncode, no stdout.
    def not_a_repo(*_a, **_kw):
        return subprocess.CompletedProcess(
            args=["git", "rev-parse", "--show-toplevel"],
            returncode=128, stdout="", stderr="fatal: not a git repository",
        )

    monkeypatch.setattr(_git_common.subprocess, "run", not_a_repo)
    monkeypatch.chdir(tmp_path)
    assert _git_common.repo_root() == tmp_path
