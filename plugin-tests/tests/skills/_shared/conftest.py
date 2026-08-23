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


@pytest.fixture
def tmp_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A git repo with identity configured and exactly one commit."""
    monkeypatch.chdir(tmp_path)
    _git("init", "-q", "-b", "master", cwd=tmp_path)
    _git("config", "user.email", "test@example.com", cwd=tmp_path)
    _git("config", "user.name", "Test", cwd=tmp_path)
    (tmp_path / "README.md").write_text("# tmp repo\n", encoding="utf-8")
    _git("add", "README.md", cwd=tmp_path)
    _git("commit", "-q", "-m", "initial", cwd=tmp_path)
    return tmp_path
