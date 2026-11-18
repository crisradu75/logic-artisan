"""Ship and Revise push in the background and compare the remote head (GitHub #468).

A slow pre-push hook outlasts the 120 s foreground limit and the push returns no exit code.
Only the exit code was checked, so a push that never finished looked like a push that did.

The comparison itself is `ship_check.py pushed`, tested in `tests/skills/_shared/test_ship_check.py`;
these tests pin that each push site runs it after the push and stops on anything but exit 0.
"""

from __future__ import annotations

from pathlib import Path

_REFS = (
    Path(__file__).resolve().parents[4]
    / ".claude"
    / "plugins"
    / "cla"
    / "skills"
    / "spec-to-pr"
    / "references"
)


_SHARED_REFS = _REFS.parents[1] / "_shared" / "references"
_PUSHED = '"${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/ship_check.py" pushed --branch <branch>'


def _text(name: str) -> str:
    folder = _SHARED_REFS if name == "ship.md" else _REFS
    return (folder / name).read_text(encoding="utf-8")


def test_ship_pushes_in_background_and_compares_the_remote_head():
    text = _text("ship.md")
    assert "**Run the push with `run_in_background`, once the trailer check above agrees.**" in text
    assert "report `push not verified`" in text
    assert _PUSHED in text
    assert "this check exiting anything but 0" in text
    assert "Do not retry the push blindly" in text
    # The check sits after the push and before the PR is opened.
    assert text.index("git push -u origin") < text.index(_PUSHED)
    assert text.index(_PUSHED) < text.index("## 4. Open the PR")


def test_revise_pushes_in_background_and_compares_the_remote_head():
    text = _text("revise.md")
    assert "**Run `git push` with `run_in_background`.**" in text
    assert _PUSHED in text
    assert "the check exiting anything but 0" in text
    assert "Do not retry the push blindly" in text
