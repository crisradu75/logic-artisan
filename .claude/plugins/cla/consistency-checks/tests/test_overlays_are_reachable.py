"""This repo's overlays must actually be reached by the code that reads them.

Every overlay reader in the plugin treats an absent overlay as the ordinary
un-configured state and falls back to a default. That is correct behaviour — a
fresh consuming repo has no overlays and must not be punished for it — but it
means a WRONG PATH is indistinguishable from a repo that simply hasn't
configured anything. The reader returns its default, the suite stays green, and
the overlay silently stops mattering.

Measured, not assumed: when the overlays moved from `skills/*/references/` into
`cla.io/overlays/`, two mutants — the staleness guard pointed at a non-existent
overlay dir, and the branch-prefix reader pointed at a non-existent path — both
SURVIVED the whole suite.

These checks live in `consistency-checks/`, which holds this repo's own
source-repo assertions, so the portable readers keep their lenient behaviour
while this repo gets the strict one. Each
asks the READER where it looks rather than recomputing the path here — the same
lesson as `test_token_list_is_curated_here.py`, where a check that computed its
own path passed while the guard it was vouching for was looking elsewhere.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = _PLUGIN_ROOT.parents[2]
_OVERLAYS = _REPO_ROOT / "cla.io" / "overlays"


def _import_from(directory: Path, module: str):
    sys.path.insert(0, str(directory))
    try:
        return __import__(module)
    finally:
        sys.path.pop(0)


def test_this_repo_actually_has_overlays_to_reach():
    """Non-vacuity partner. Every check below is trivially satisfiable in a repo
    with no overlays at all, so pin that this one has them."""
    assert _OVERLAYS.is_dir(), f"{_OVERLAYS} is missing"
    found = sorted(p.name for p in _OVERLAYS.glob("*.md"))
    assert len(found) >= 8, f"expected this repo's overlay set, found {found}"


def test_the_staleness_guard_scans_this_repos_overlays():
    guard = _import_from(
        _PLUGIN_ROOT / "conformance-checks" / "tests", "test_project_facts_paths"
    )
    scanned = {p.resolve() for p in guard._iter_scanned_files(_REPO_ROOT)}
    missing = [
        p.name for p in sorted(_OVERLAYS.glob("*.md")) if p.resolve() not in scanned
    ]
    assert not missing, (
        f"the staleness guard does not scan {missing} — it is looking somewhere "
        f"other than {_OVERLAYS}, so those overlays are unchecked and the guard "
        "still reports success"
    )
    # Opening the files is not the same as extracting anything from them. The
    # guard's own `checked > 0` assert is gated on `cla.io/project-facts.md`
    # existing, and this repo has none — so a regression in candidate extraction
    # would leave `checked == 0`, `stale == []`, and a green guard. Pin the floor
    # here, where the overlays are known to exist.
    checked, _stale = guard.scan(_REPO_ROOT)
    assert checked > 0, (
        "the staleness guard extracted zero path candidates from this repo's "
        "overlays — it scanned files but checked nothing, which passes green"
    )


def test_the_branch_prefix_reader_resolves_this_repos_overlay():
    gc = _import_from(
        _PLUGIN_ROOT / "skills" / "spec-to-pr" / "scripts", "_git_common"
    )
    resolved = gc.overlay_path()
    assert resolved.is_file(), (
        f"branch_prefix() looks for its overlay at {resolved}, which does not "
        "exist — every repo silently gets the default prefix, and a resume probe "
        "then reports finished work as not started"
    )
    assert resolved.resolve() == (_OVERLAYS / "branch-prefix.local.md").resolve()


def test_the_branch_prefix_overlay_parses_rather_than_warning():
    """A file that EXISTS but yields no value degrades to the default with a
    warning on every run — the state this repo's stub was actually in before the
    overlay format was unified."""
    gc = _import_from(
        _PLUGIN_ROOT / "skills" / "spec-to-pr" / "scripts", "_git_common"
    )
    text = gc.overlay_path().read_text(encoding="utf-8")
    assert gc.prefix_from_text(text), (
        "the branch-prefix overlay does not parse to a usable value; the reader "
        "warns and falls back on every single run"
    )
