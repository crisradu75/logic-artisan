"""Shared repo-root resolution for spec-to-pr's scripts.

Extracted from five call sites (branch.py, commit.py, check_permissions.py,
discover_tests.py, probe_state.py) that each carried a byte-identical copy.
Safe to share here (unlike a cross-skill helper) because all five live in
this one skill's pytest scope (`pythonpath = ["scripts"]` in this skill's own
`pyproject.toml`) — importing a sibling module within that scope crosses no
isolation boundary.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def repo_root() -> Path:
    """Repo root via git (location-independent — works from the plugin, unlike a
    fixed `parents[N]` depth). Falls back to cwd if git is unavailable; callers'
    tests monkeypatch each module's own `REPO_ROOT` directly, not this function."""
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
