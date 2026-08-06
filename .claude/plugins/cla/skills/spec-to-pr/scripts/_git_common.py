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
import sys
from pathlib import Path


def repo_root() -> Path:
    """Repo root via git (location-independent — works from the plugin, unlike a
    fixed `parents[N]` depth). Falls back to cwd if git is unavailable; callers'
    tests monkeypatch each module's own `REPO_ROOT` directly, not this function.

    The fallback WARNS rather than substituting cwd silently. Callers bind this
    at import time (`REPO_ROOT = _repo_root()`), and several of them resolve
    ledger and artifact paths from it — so a silent wrong root means writes land
    somewhere unexpected while the run still reports success. Fail-open is right
    for a helper script; fail-open-and-quiet is not.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
        detail = f"`git rev-parse --show-toplevel` exited {out.returncode}"
    except (OSError, subprocess.SubprocessError) as e:
        detail = f"`git rev-parse --show-toplevel` could not run ({e})"
    cwd = Path.cwd()
    print(
        f"_git_common: {detail}; falling back to the current directory ({cwd}). "
        "Paths derived from the repo root may be wrong.",
        file=sys.stderr,
    )
    return cwd
