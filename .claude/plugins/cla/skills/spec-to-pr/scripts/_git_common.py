"""Shared repo-root and branch-name resolution for spec-to-pr's scripts.

Extracted when five call sites each carried a byte-identical copy of the
repo-root resolver; the script audit deleted four of them, so `probe_state.py`
is the sole remaining consumer. Safe to share here (unlike a cross-skill
helper) because both live in this one skill's pytest scope (`pythonpath =
["scripts"]` in this skill's own `pyproject.toml`) — importing a sibling
module within that scope crosses no isolation boundary.
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
# `feature/<change-name>` was hardcoded in the script that CREATED the branch
# (since deleted — Ship now runs plain git) and three times in `probe_state.py`
# (which LOOKS IT UP). `feature/` is a default, not a universal.
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
_BRANCH_PREFIX_KEY = "branch_prefix"
DEFAULT_BRANCH_PREFIX = "feature/"


def _warn(message: str) -> None:
    print(f"[_git_common] {message}", file=sys.stderr)


def prefix_from_text(text: str) -> str | None:
    """Parse the overlay's flat `key: value` frontmatter, or None if unusable.

    FORMAT. Flat `key: value` between `---` fences, matching
    `hooks/warn-smoke-test-drift.py` and `hooks/warn-lint-on-edit.py` — every
    other overlay in the plugin. This one originally read "the first non-comment
    line", a third syntax for the third overlay, which is a needless thing to
    learn and gave the value no name at the point of use.

    DIAGNOSTICS. Every degraded case says so. The split that matters is
    absent-vs-broken: a missing overlay is the ordinary un-configured state and
    is silent (handled by the caller), while an overlay that EXISTS and cannot
    be used is a typo someone needs to hear about. Falling back silently there
    made a misconfiguration indistinguishable from never having opted in — the
    exact distinction the two hook overlays already draw correctly.

    Split out from file reading so it is testable without a real file at a
    `__file__`-relative path.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        _warn(f"{_BRANCH_PREFIX_OVERLAY} does not start with a `---` frontmatter "
              "line; ignoring it and using the default branch prefix")
        return None
    body: list[str] | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            body = lines[1:i]
            break
    if body is None:
        _warn(f"{_BRANCH_PREFIX_OVERLAY} frontmatter has no closing `---` line; "
              "ignoring it and using the default branch prefix")
        return None
    for line in body:
        key, sep, value = line.partition(":")
        if sep and key.strip() == _BRANCH_PREFIX_KEY:
            value = value.strip()
            if value:
                return value
            break
    _warn(f"{_BRANCH_PREFIX_OVERLAY} has no usable `{_BRANCH_PREFIX_KEY}:` value; "
          "using the default branch prefix")
    return None


def overlay_path() -> Path:
    """Where `branch_prefix()` looks for the overlay.

    Split out so the path is testable on its own. It has to be: an overlay this
    function cannot find is not an error, it is the ordinary un-configured state,
    so a wrong path here returns `feature/` for every repo and says nothing.
    Mutation confirmed no test noticed the path being broken until a check
    asserted on this function directly.
    """
    return repo_root() / "cla.io" / "overlays" / _BRANCH_PREFIX_OVERLAY


def branch_prefix() -> str:
    """This repo's branch prefix: env override, else overlay, else the default.

    The overlay lives in the REPO (`cla.io/overlays/`), not in the plugin. Under
    a marketplace install the plugin tree is a read-only cache that no repo can
    write to, so a per-repo fact stored beside the code that reads it would be
    unreachable — and, worse, silently unreachable: a missing overlay is the
    ordinary un-configured state, so the repo would just get `feature/` back.

    The value is used VERBATIM — no trailing `/` is appended. Forcing one ruled
    out a flat prefix like `wip-`, which a repo may legitimately want, and the
    default (`feature/`) carries its own slash, so nothing is lost by leaving
    the choice to whoever writes the overlay.
    """
    env = os.environ.get("CLA_BRANCH_PREFIX")
    if env:
        return env
    overlay = overlay_path()
    if not overlay.is_file():
        # The ONLY legitimately silent case: no overlay means not configured,
        # which is the ordinary state of every repo on the default convention.
        return DEFAULT_BRANCH_PREFIX
    try:
        text = overlay.read_text(encoding="utf-8")
    except OSError as exc:
        _warn(f"{_BRANCH_PREFIX_OVERLAY} exists but could not be read ({exc}); "
              "using the default branch prefix")
        return DEFAULT_BRANCH_PREFIX
    return prefix_from_text(text) or DEFAULT_BRANCH_PREFIX


def branch_name(change_name: str) -> str:
    return f"{branch_prefix()}{change_name}"
