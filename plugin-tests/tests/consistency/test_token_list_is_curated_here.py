"""This repo must actually have a curated token list for the conformance guard.

The guard itself (`skills/_shared/scripts/check_no_project_tokens.py`) treats an
absent `project-tokens.local.md` as a trivial pass, and that is correct FOR A
CONSUMING REPO: a fresh destination has installed the guard but not yet curated a
list, and a red suite there would teach people to ignore it.

In the SOURCE repo that leniency is a hole. The guard's whole job is to stop a
project token reaching every destination, and it does nothing at all when it
cannot find the list — so a path typo, a rename, or a move (the list travelled
from the old sync skill's `references/` to `cla.io/` when the guards were rescued
into their own scope) turns the guard off with a green suite and no signal.

This check lives in `consistency-checks/`, which holds this repo's own
source-repo assertions, precisely so the portable guard keeps its portable
behaviour while this repo gets the strict one.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
_GUARD = _PLUGIN_ROOT / "skills" / "_shared" / "scripts" / "check_no_project_tokens.py"


def _load_guard():
    """Load the guard module for its own path resolution.

    Everything below comes from the guard — the relative path AND the root it
    resolves against. Recomputing either here would check that the file exists
    where THIS test looks, which is not the question; the question is whether
    the GUARD finds it. Measured: a version of this check that computed its own
    repo root passed happily while the guard's anchor was off by one level and
    the guard skipped.

    Loaded by explicit file path rather than by bare module name: the guard is a
    program in a skill's `scripts/` dir now, not a module on any `sys.path`, and
    a path-based load is what keeps this test pointed at the implementation
    rather than at wherever a module of that name happens to be found.
    """
    spec = importlib.util.spec_from_file_location("_cc_check_no_project_tokens", _GUARD)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load the guard at {_GUARD}")
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
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
