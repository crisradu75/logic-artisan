"""This repo must actually have a curated token list for the conformance guard.

The guard itself (`conformance-checks/tests/test_no_project_tokens.py`) treats an
absent `project-tokens.local.md` as a trivial pass, and that is correct FOR A
CONSUMING REPO: a fresh destination has synced the guard but not yet curated a
list, and a red suite there would teach people to ignore it.

In the SOURCE repo that leniency is a hole. The guard's whole job is to stop a
project token reaching every destination, and it does nothing at all when it
cannot find the list — so a path typo, a rename, or a move (the list travelled
from the old sync skill's `references/` to `cla.io/` when the guards were rescued
into their own scope) turns the guard off with a green suite and no signal.

This check lives in `consistency-checks/`, which is NOT synced, precisely so the
portable guard keeps its portable behaviour while this repo gets the strict one.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]
_GUARD = _PLUGIN_ROOT / "conformance-checks" / "tests" / "test_no_project_tokens.py"


def _load_guard():
    """Import the guard module for its own path resolution.

    Everything below comes from the guard — the relative path AND the root it
    resolves against. Recomputing either here would check that the file exists
    where THIS test looks, which is not the question; the question is whether
    the GUARD finds it. Measured: a version of this check that computed its own
    repo root passed happily while the guard's anchor was off by one level and
    the guard skipped.
    """
    sys.path.insert(0, str(_GUARD.parent))
    try:
        import test_no_project_tokens as guard  # noqa: PLC0415
    finally:
        sys.path.pop(0)
    return guard


def test_the_conformance_guard_is_not_silently_disabled_in_this_repo():
    guard = _load_guard()
    resolved_root = guard._repo_root()
    token_path = resolved_root / guard.TOKEN_LIST_RELPATH
    assert token_path.is_file(), (
        f"{guard.TOKEN_LIST_RELPATH.as_posix()} is missing, so the conformance "
        f"guard skips and every project token reaches consuming repos unchecked. "
        f"The guard resolved the repo root to {resolved_root}."
    )
    tokens = guard.load_tokens(token_path)
    assert tokens, (
        f"{guard.TOKEN_LIST_RELPATH.as_posix()} exists but parses to zero tokens "
        "— the guard would run against an empty list, which passes everything."
    )
