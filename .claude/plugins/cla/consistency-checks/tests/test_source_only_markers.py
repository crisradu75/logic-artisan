"""The source-repo-only contract stays wired at both ends.

`run_tests.py` skips a marker-carrying scope outside the canonical repo. Three
failure shapes would silently undo that, and each is a one-line mistake that
hands a consuming repo failures it cannot fix:

  - a marker file renamed or deleted (the scope re-arms in every consumer);
  - the runner's marker constant drifting (every marker becomes inert);
  - the runner's source-repo DETECTION drifting. This one is the subtle case:
    an earlier version of this file only grepped for the detector's name, so
    mutating it to `return True` or `return False` both survived. `return False`
    is a silent false green here — every marked scope vanishes and the summary
    still reports a clean pass. The detection tests below call the function
    against synthetic trees so both branches are exercised, not just the one
    this repo happens to be.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]

MARKER = "SOURCE-REPO-ONLY.md"
EXPECTED_MARKED_SCOPES = ("consistency-checks", "launcher-checks", "skills/release")


def _load_runner():
    """Import run_tests.py by path — it sits at the plugin root with no package."""
    spec = importlib.util.spec_from_file_location(
        "_cla_run_tests", _PLUGIN_ROOT / "run_tests.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _detect_with_root(monkeypatch, plugin_root):
    """Run the real `_is_source_repo` against a synthetic tree."""
    mod = _load_runner()
    monkeypatch.setattr(mod, "PLUGIN_ROOT", plugin_root)
    return mod._is_source_repo()


def _make_tree(base, *, catalog: bool, path_in_catalog: str = ".claude/plugins/cla"):
    plugin = base / ".claude" / "plugins" / "cla"
    plugin.mkdir(parents=True)
    if catalog:
        cat = base / ".claude-plugin"
        cat.mkdir()
        (cat / "marketplace.json").write_text(
            '{"plugins":[{"source":{"path":"%s"}}]}' % path_in_catalog,
            encoding="utf-8",
        )
    return plugin


# ---------- the marker files ----------


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
    expected = set(EXPECTED_MARKED_SCOPES)
    found = list(_PLUGIN_ROOT.glob(f"*/{MARKER}")) + list(
        _PLUGIN_ROOT.glob(f"skills/*/{MARKER}")
    )
    stray = [
        rel
        for rel in (p.parent.relative_to(_PLUGIN_ROOT).as_posix() for p in found)
        if rel not in expected
    ]
    assert not stray, f"unexpected {MARKER} in portable scope(s): {stray}"


# ---------- the runner half ----------


def test_the_runner_still_honours_the_marker():
    runner_src = (_PLUGIN_ROOT / "run_tests.py").read_text(encoding="utf-8")
    assert f'SOURCE_ONLY_MARKER = "{MARKER}"' in runner_src, (
        "run_tests.py renamed or dropped its marker constant; every "
        f"{MARKER} file is now inert"
    )


def test_source_repo_detection_actually_detects_this_repo():
    """CALL the detector, don't grep for its name. This test only ever runs in
    the canonical repo (it lives in a source-only scope), so True is an exact
    pin."""
    mod = _load_runner()
    assert mod._is_source_repo() is True, (
        "_is_source_repo() returned False in the canonical repo — every "
        "source-only scope is now silently skipped here, and the summary still "
        "reports a clean pass"
    )


def test_detection_says_no_in_a_consumer_shaped_tree(tmp_path, monkeypatch):
    """The branch this repo can never exercise on itself.

    Testing only against the real repo cannot distinguish correct detection from
    `return True` — both answer True here. A consuming repo has the plugin tree
    but no repo-root catalog publishing it; detection must say no, or every
    marked scope runs there."""
    plugin = _make_tree(tmp_path, catalog=False)
    assert _detect_with_root(monkeypatch, plugin) is False


def test_detection_says_yes_when_the_catalog_publishes_this_tree(tmp_path, monkeypatch):
    plugin = _make_tree(tmp_path, catalog=True)
    assert _detect_with_root(monkeypatch, plugin) is True


def test_detection_accepts_a_dot_slash_spelling_of_the_published_path(tmp_path, monkeypatch):
    """`./.claude/plugins/cla` names the same tree. A substring match on one
    spelling would silently flip the source repo to non-source."""
    plugin = _make_tree(tmp_path, catalog=True, path_in_catalog="./.claude/plugins/cla")
    assert _detect_with_root(monkeypatch, plugin) is True


def test_detection_says_no_from_a_marketplace_cache_layout(tmp_path, monkeypatch):
    """The real consumer shape: `.../plugins/cache/<market>/cla/<version>`. The
    version dir means the parent of `cla` is not `plugins`."""
    cached = tmp_path / ".claude" / "plugins" / "cache" / "m" / "cla" / "0.9.3"
    cached.mkdir(parents=True)
    assert _detect_with_root(monkeypatch, cached) is False


def test_detection_survives_an_unreadable_catalog(tmp_path, monkeypatch):
    """A corrupt catalog must fail closed (not source), never raise — an
    exception here takes the whole runner down at startup. `UnicodeDecodeError`
    is a ValueError, not an OSError, so the handler must cover both."""
    plugin = _make_tree(tmp_path, catalog=True)
    (tmp_path / ".claude-plugin" / "marketplace.json").write_bytes(
        bytes([255, 254, 0]) + b"bad"
    )
    assert _detect_with_root(monkeypatch, plugin) is False
