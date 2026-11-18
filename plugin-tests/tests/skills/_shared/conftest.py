"""Fixtures for the `_shared` scope.

Deliberately NOT a copy of `spec-to-pr/tests/conftest.py`. That one builds an
openspec skeleton and pins a branch prefix because `probe_state.py`'s tests need
both; `git_state.py` knows nothing about openspec and only needs a real git repo
with one commit. Copying the larger fixture would import two behaviours this
scope does not exercise and create a second thing to keep in step.

`-b master` is pinned deliberately rather than inherited: without it the fixture
takes whatever `init.defaultBranch` the developer's global git config happens to
set, so the same test measures a different branch name on two machines. The name
carries no meaning here — it only has to be fixed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )


def _build_tmp_repo(root: Path) -> None:
    _git("init", "-q", "-b", "master", cwd=root)
    _git("config", "user.email", "test@example.com", cwd=root)
    _git("config", "user.name", "Test", cwd=root)
    (root / "README.md").write_text("# tmp repo\n", encoding="utf-8")
    _git("add", "README.md", cwd=root)
    _git("commit", "-q", "-m", "initial", cwd=root)


@pytest.fixture
def tmp_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cached_git_repo) -> Path:
    """A git repo with identity configured and exactly one commit."""
    monkeypatch.chdir(tmp_path)
    return cached_git_repo("_shared/tmp_repo", _build_tmp_repo, tmp_path)
