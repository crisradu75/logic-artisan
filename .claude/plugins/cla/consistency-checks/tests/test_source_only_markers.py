"""The source-repo-only contract stays wired at both ends.

`run_tests.py` skips a marker-carrying scope outside the canonical repo. Two
failure shapes would silently undo that: a marker file renamed or deleted (the
scope re-arms in every consumer), and the runner's marker constant or detection
drifting (every marker becomes inert). Both are one-line mistakes; both ship a
consumer failures it cannot fix. This file pins the pairing.
"""

from __future__ import annotations

from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]

MARKER = "SOURCE-REPO-ONLY.md"
EXPECTED_MARKED_SCOPES = ("consistency-checks", "launcher-checks")


def test_every_expected_source_only_scope_carries_the_marker():
    missing = [
        name
        for name in EXPECTED_MARKED_SCOPES
        if not (_PLUGIN_ROOT / name / MARKER).is_file()
    ]
    assert not missing, (
        f"scope(s) {missing} lost their {MARKER}; a consuming repo will run "
        "their source-repo assertions and fail on facts it cannot fix"
    )


def test_no_portable_scope_carries_the_marker():
    """The marker disables a scope everywhere but here — a stray copy in a
    portable scope silently turns real consumer coverage off."""
    stray = [
        p.parent.name
        for p in _PLUGIN_ROOT.glob(f"*/{MARKER}")
        if p.parent.name not in EXPECTED_MARKED_SCOPES
    ] + [
        f"skills/{p.parent.name}"
        for p in _PLUGIN_ROOT.glob(f"skills/*/{MARKER}")
    ]
    assert not stray, f"unexpected {MARKER} in portable scope(s): {stray}"


def test_the_runner_still_honours_the_marker():
    runner = (_PLUGIN_ROOT / "run_tests.py").read_text(encoding="utf-8")
    assert f'SOURCE_ONLY_MARKER = "{MARKER}"' in runner, (
        "run_tests.py renamed or dropped its marker constant; every "
        f"{MARKER} file is now inert"
    )
    assert "_is_source_repo" in runner, (
        "run_tests.py dropped its source-repo detection; marked scopes either "
        "always run or never run"
    )
