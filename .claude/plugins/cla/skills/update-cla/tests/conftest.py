"""Shared test fixtures for update-cla (pull-from-destination shape).

Module imports are handled per-test by ``test_sync_claude_assets._load()``,
which puts ``update-cla/scripts`` on ``sys.path`` itself — so this conftest
carries only fixtures, no path manipulation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest


@pytest.fixture
def synthetic_repos(tmp_path: Path) -> Callable[[dict[str, dict[str, str]]], list[Path]]:
    """Build a temporary directory of fake repos with `.claude/` contents."""

    def _build(spec: dict[str, dict[str, str]]) -> list[Path]:
        root = tmp_path / "code"
        root.mkdir()
        out = []
        for repo_name, files in spec.items():
            repo = root / repo_name
            repo.mkdir()
            (repo / ".claude").mkdir()
            for rel, content in files.items():
                dst = repo / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(content.encode("utf-8"))
            out.append(repo)
        return out

    return _build


@pytest.fixture
def fake_gh(monkeypatch) -> dict:
    """Patch subprocess.run to return canned `gh` / `git` responses.

    `responses` is a list of (cmd_match_tokens, returncode, stdout, stderr) tuples;
    each subprocess.run call consumes the first match. Unmatched calls succeed silently.
    """
    import subprocess
    state = {"responses": [], "calls": []}

    def fake_run(cmd, **kwargs):
        state["calls"].append(list(cmd))
        for i, (match, rc, out, err) in enumerate(state["responses"]):
            if all(token in cmd for token in match):
                state["responses"].pop(i)
                return subprocess.CompletedProcess(
                    args=cmd, returncode=rc, stdout=out, stderr=err
                )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return state
