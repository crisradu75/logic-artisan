"""Skip this whole scope unless we are running inside the source repo.

`launcher-checks/` guards the repo that DEVELOPS the harness: that its
overlays are reachable, that its token list is curated, that its `pre-push` hook
is installed, that its sibling scripts have not drifted. Every one of those is a
statement about this working tree.

The scope nevertheless ships inside the plugin package — `git-subdir` takes a
whole directory and offers no exclude list — so a consuming repo that runs the
plugin's own suite gets these tests too. Measured from an installed copy: 3
failures, all of them "there are no launchers here".

A failure that means "not applicable here" is worse than useless: it trains the
reader to ignore a red suite, and this suite is the only gate the project has.
So detect the situation and skip, with the reason attached.

Detection is the same one `codify-learnings/references/plugin-writability.md`
documents, and it holds for the same reason: a plugin loaded from a working tree
is inside a git repo; an installed one is a plain directory in a version-keyed
cache (verified: the cache has no `.git`).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"


def _is_the_source_working_tree() -> bool:
    try:
        out = subprocess.run(
            ["git", "-C", str(_PLUGIN_ROOT), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if out.returncode != 0 or not out.stdout.strip():
        return False
    # Inside a repo, and that repo actually contains this plugin — not a repo
    # that merely happens to be the cwd's ancestor.
    try:
        return _PLUGIN_ROOT.is_relative_to(Path(out.stdout.strip()).resolve())
    except (OSError, ValueError):
        return False


def pytest_collection_modifyitems(config, items):
    if _is_the_source_working_tree():
        return
    skip = pytest.mark.skip(
        reason=(
            "launcher-checks tests the source repo's own launchers; this is an "
            "installed copy, which has none"
        )
    )
    for item in items:
        item.add_marker(skip)
