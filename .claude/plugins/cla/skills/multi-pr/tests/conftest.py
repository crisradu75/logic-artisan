"""Shared fixtures for multi-pr helper-script tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def changes_dir(tmp_path: Path) -> Path:
    d = tmp_path / "openspec" / "changes"
    d.mkdir(parents=True)
    return d


def make_change(changes_dir: Path, name: str, *, proposal: str = "## Why\nstub\n",
                design: str | None = None, tasks: str | None = None) -> Path:
    change_dir = changes_dir / name
    change_dir.mkdir(parents=True, exist_ok=True)
    if proposal is not None:
        (change_dir / "proposal.md").write_text(proposal, encoding="utf-8")
    if design is not None:
        (change_dir / "design.md").write_text(design, encoding="utf-8")
    if tasks is not None:
        (change_dir / "tasks.md").write_text(tasks, encoding="utf-8")
    return change_dir
