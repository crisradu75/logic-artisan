"""Shared repo-root resolution for spec-to-pr's scripts.

Extracted from five call sites (branch.py, commit.py, check_permissions.py,
discover_tests.py, probe_state.py) that each carried a byte-identical copy.
Safe to share here (unlike a cross-skill helper) because all five live in
this one skill's pytest scope (`pythonpath = ["scripts"]` in this skill's own
`pyproject.toml`) — importing a sibling module within that scope crosses no
isolation boundary.
"""

from __future__ import annotations

import os
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
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
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


# --------------------------------------------------------------------------- #
# Branch naming
#
# `feature/<change-name>` was hardcoded in `branch.py` (which CREATES the
# branch) and three times in `probe_state.py` (which LOOKS IT UP). `feature/` is
# a default, not a universal.
#
# What makes that worse than a naming mismatch is HOW it fails. All three probes
# use `git rev-parse --verify --quiet`, which on a miss exits 1 with EMPTY
# stderr -- and the `--quiet` is deliberate, so the "any output means anomaly"
# gate never fires. A repo on any other convention therefore reports
# `branch: false, pr: {open: false}, fix_rounds_applied: 0`: indistinguishable
# from "nothing has been done yet". The orchestrator acts on that by redoing
# completed work, and can open a duplicate branch and PR.
#
# Two live triggers, not hypotheticals: `ship.md` explicitly permits shortening
# a verbose change name, and a convention that varies its middle segment
# (`claude/fix/x` vs `claude/feature/x`) cannot be expressed by one prefix at
# all.
#
# The same sync that generalized `master` -> `<base-branch>` fixed this exact
# hardcoding in the hook MESSAGES and stopped there, leaving the scripts that
# actually create and find the branch.
# --------------------------------------------------------------------------- #

_BRANCH_PREFIX_OVERLAY = "branch-prefix.local.md"
DEFAULT_BRANCH_PREFIX = "feature/"


def prefix_from_text(text: str) -> str | None:
    """First non-comment, non-blank line of an overlay, normalized to end in `/`.

    Split out from file reading so it is testable without a real file at a
    `__file__`-relative path.
    """
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("<!--"):
            continue
        return line if line.endswith("/") else line + "/"
    return None


def branch_prefix() -> str:
    """This repo's branch prefix: env override, else overlay, else the default.

    The overlay is a `*.local.md`, so `discover.py` never syncs it and it never
    shows up as a divergence in a consuming repo.
    """
    env = os.environ.get("CLA_BRANCH_PREFIX")
    if env:
        return env if env.endswith("/") else env + "/"
    overlay = Path(__file__).resolve().parent.parent / "references" / _BRANCH_PREFIX_OVERLAY
    try:
        found = prefix_from_text(overlay.read_text(encoding="utf-8"))
    except OSError:
        return DEFAULT_BRANCH_PREFIX
    return found or DEFAULT_BRANCH_PREFIX


def branch_name(change_name: str) -> str:
    return f"{branch_prefix()}{change_name}"
