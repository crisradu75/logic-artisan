"""Tests for warn-wholesale-rewrite.py.

The hook is deliberately quiet: it fires only for a `Write` that replaces a
tracked, non-trivial file with a materially shorter one. Most of these tests
therefore assert SILENCE, because a warn hook that fires on ordinary work gets
tuned out and then the one real warning is missed too.

`_committed_word_count` runs real `git` against a throwaway repo built per test
— never the repo under development, which would make the tests depend on this
repo's own history and (worse) let a test write into a live working tree.

**The fixture file lives in a subdirectory on purpose.** With everything at the
repo root, `HEAD:<path>` and `HEAD:./<path>` are indistinguishable and so are
`as_posix()` and `str()` — a suite built on root-level files passes while the
hook is a no-op for every nested file on Windows. Both bugs shipped in the first
version of this hook and neither was catchable until the fixture moved.
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
HOOK_PATH = HOOKS_DIR / "warn-wholesale-rewrite.py"
_spec = importlib.util.spec_from_file_location("warn_wholesale_rewrite", HOOK_PATH)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

REL = "docs/guide.md"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _words(n: int) -> str:
    """`n` whitespace-delimited words, wrapped 8 per line."""
    return "\n".join(" ".join(f"w{i + j}" for j in range(8)) for i in range(0, n, 8)) + "\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Throwaway repo with one committed 400-word file, nested under docs/."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "config", "user.name", "T")
    (tmp_path / "docs").mkdir()
    (tmp_path / REL).write_text(_words(400), encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "add guide")
    return tmp_path


def _payload(path: str = REL, tool: str = "Write") -> dict:
    return {"tool_name": tool, "tool_input": {"file_path": path}}


def _run(monkeypatch, capsys, root: Path, payload: dict) -> str:
    """Run main() with `root` as the project dir; return captured stdout."""
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert hook.main() == 0
    return capsys.readouterr().out


def _context(out: str) -> str:
    parsed = json.loads(out)
    assert parsed["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    return parsed["hookSpecificOutput"]["additionalContext"]


# --------------------------------------------------------------------------- #
# Fires
# --------------------------------------------------------------------------- #


def test_warns_when_a_write_materially_shrinks_a_tracked_file(monkeypatch, capsys, repo):
    (repo / REL).write_text(_words(200), encoding="utf-8")
    ctx = _context(_run(monkeypatch, capsys, repo, _payload()))
    assert REL in ctx
    # Whole rendered line, not substrings: reversing `dropped` or swapping the
    # two counts leaves every individual number present and passed silently.
    assert "replaced 400 committed words with 200 (50% shorter, 200 words gone)" in ctx


def test_the_message_asks_for_the_dropped_content_not_just_the_number(monkeypatch, capsys, repo):
    """A bare percentage is ignorable. The ask ('say what you dropped') is the
    whole mechanism — the hook cannot judge the cut, only force it to be named."""
    (repo / REL).write_text(_words(160), encoding="utf-8")
    assert "what you dropped" in _context(_run(monkeypatch, capsys, repo, _payload()))


def test_fires_when_the_project_dir_is_below_the_repo_root(monkeypatch, capsys, repo):
    """The bug that shipped in v1. `git show HEAD:<path>` resolves from the
    repository TOP LEVEL and ignores `-C`, so with a project dir inside the repo
    every lookup missed and the hook was silently dead. `HEAD:./<path>` fixes it.
    Verified against real git: from `-C docs`, `HEAD:guide.md` reads a root-level
    `guide.md` if one exists and otherwise fails."""
    (repo / REL).write_text(_words(200), encoding="utf-8")
    ctx = _context(_run(monkeypatch, capsys, repo / "docs", _payload("guide.md")))
    assert "replaced 400 committed words with 200" in ctx


def test_a_root_level_namesake_is_not_mistaken_for_the_nested_file(monkeypatch, capsys, repo):
    """The nastier half of the same bug: a same-named file at the repo root made
    the wrong baseline resolve, so the hook reported a loss that never happened."""
    (repo / "guide.md").write_text(_words(4000), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "root namesake")
    (repo / REL).write_text(_words(200), encoding="utf-8")
    ctx = _context(_run(monkeypatch, capsys, repo / "docs", _payload("guide.md")))
    assert "replaced 400 committed words" in ctx  # the nested file, not the 4000-word root one


def test_a_second_shrink_is_measured_from_the_commit_not_the_staged_version(monkeypatch, capsys, repo):
    """Two staged cuts, each under the threshold, together over it."""
    (repo / REL).write_text(_words(340), encoding="utf-8")
    _git(repo, "add", "-A")
    (repo / REL).write_text(_words(288), encoding="utf-8")
    assert "replaced 400 committed words with 288" in _context(_run(monkeypatch, capsys, repo, _payload()))


# --------------------------------------------------------------------------- #
# Stays silent
# --------------------------------------------------------------------------- #


def test_silent_for_edit_even_on_a_huge_shrink(monkeypatch, capsys, repo):
    """Edit keeps whatever it does not name; only Write can drop content
    silently. This is the hook's central scoping decision, so it is pinned."""
    (repo / REL).write_text(_words(8), encoding="utf-8")
    assert _run(monkeypatch, capsys, repo, _payload(tool="Edit")) == ""


def test_silent_on_reflow_that_changes_every_line_but_no_word(monkeypatch, capsys, repo):
    """Re-wrapping hard-wrapped prose drops a large fraction of the lines and
    loses nothing. Counting lines would have made this the commonest false
    warning in a plugin whose behaviour lives mostly in markdown."""
    words = (repo / REL).read_text(encoding="utf-8").split()
    (repo / REL).write_text(" ".join(words) + "\n", encoding="utf-8")  # 400 words, 1 line
    assert _run(monkeypatch, capsys, repo, _payload()) == ""


def test_silent_when_the_file_grew(monkeypatch, capsys, repo):
    (repo / REL).write_text(_words(600), encoding="utf-8")
    assert _run(monkeypatch, capsys, repo, _payload()) == ""


@pytest.mark.parametrize("surviving", [400, 344, 340, 328, 321])
def test_silent_up_to_the_binding_boundary(monkeypatch, capsys, repo, surviving):
    """Two thresholds gate a warning and BOTH must be crossed — the ratio
    (new < 85% of baseline) and the absolute floor (>= 80 words gone).

    At baseline 400 the FLOOR is the binding one: 80 words is exactly 20%, so
    nothing between 340 (the ratio boundary) and 321 can fire. Assuming the
    ratio alone decided is what made the first version of this test fail. The
    floor binds for any baseline under ~533 words, which is most files."""
    (repo / REL).write_text(_words(surviving), encoding="utf-8")
    assert _run(monkeypatch, capsys, repo, _payload()) == ""


def test_warns_one_word_past_the_binding_boundary(monkeypatch, capsys, repo):
    """320 surviving == exactly 80 dropped, and 320 < 340. Both cross."""
    (repo / REL).write_text(_words(320), encoding="utf-8")
    ctx = _context(_run(monkeypatch, capsys, repo, _payload()))
    assert "with 320 (20% shorter, 80 words gone)" in ctx


def test_the_ratio_binds_once_the_file_is_large_enough(monkeypatch, capsys, repo):
    """Above ~533 words the ratio becomes the binding rule. 0.85 of 800 is 680,
    and the comparison is `>=`, so 680 is silent and 672 warns — which is what
    pins `>=` against `>`; no other test here can tell them apart."""
    big = repo / "docs" / "big.md"
    big.write_text(_words(800), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "big")

    big.write_text(_words(680), encoding="utf-8")
    assert _run(monkeypatch, capsys, repo, _payload("docs/big.md")) == ""

    big.write_text(_words(672), encoding="utf-8")
    assert "with 672" in _context(_run(monkeypatch, capsys, repo, _payload("docs/big.md")))


def test_silent_when_the_absolute_drop_is_small_even_at_a_big_ratio(monkeypatch, capsys, repo):
    """A file barely over MIN_BASELINE_WORDS must not warn for losing a
    sentence. 160 -> 80 is 50% but only 80 words; the floor holds it."""
    (repo / "docs" / "small.md").write_text(_words(160), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "small")
    (repo / "docs" / "small.md").write_text(_words(88), encoding="utf-8")
    assert _run(monkeypatch, capsys, repo, _payload("docs/small.md")) == ""


def test_silent_for_a_short_baseline(monkeypatch, capsys, repo):
    (repo / "docs" / "stub.md").write_text(_words(40), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "stub")
    (repo / "docs" / "stub.md").write_text("x\n", encoding="utf-8")
    assert _run(monkeypatch, capsys, repo, _payload("docs/stub.md")) == ""


def test_silent_for_an_untracked_file(monkeypatch, capsys, repo):
    """Nothing was replaced, so nothing can have been lost — and this must not
    emit the git-could-not-resolve diagnostic either."""
    (repo / "docs" / "new.md").write_text(_words(8), encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_payload("docs/new.md"))))
    assert hook.main() == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_silent_outside_the_project_root(monkeypatch, capsys, repo, tmp_path_factory):
    outside = tmp_path_factory.mktemp("elsewhere") / "x.md"
    outside.write_text(_words(8), encoding="utf-8")
    assert _run(monkeypatch, capsys, repo, _payload(str(outside))) == ""


def test_silent_when_not_a_git_repo(monkeypatch, capsys, tmp_path):
    """Must degrade quietly — a guard that errors on a non-repo would break
    every scratch directory."""
    (tmp_path / "doc.md").write_text(_words(8), encoding="utf-8")
    assert _run(monkeypatch, capsys, tmp_path, _payload("doc.md")) == ""


@pytest.mark.parametrize(
    "payload",
    [
        "not json at all",
        "[]",
        '{"tool_name": "Write"}',
        '{"tool_name": "Write", "tool_input": {"file_path": 42}}',
        '{"tool_name": "Write", "tool_input": {"file_path": "docs/nope.md"}}',
    ],
)
def test_malformed_input_never_raises(monkeypatch, capsys, repo, payload):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


# --------------------------------------------------------------------------- #
# _committed_word_count
# --------------------------------------------------------------------------- #


def test_committed_word_count_reads_head_not_the_working_tree(repo):
    (repo / REL).write_text("x\n", encoding="utf-8")
    assert hook._committed_word_count(repo, REL) == 400


def test_committed_word_count_reads_head_not_the_index(repo):
    """Reading the index passes every other test here, because a fresh commit
    leaves index == HEAD. It breaks on a shrink already staged then shrunk
    again: each write measured from the last, so a cumulative loss never fires."""
    (repo / REL).write_text(_words(340), encoding="utf-8")
    _git(repo, "add", "-A")
    assert hook._committed_word_count(repo, REL) == 400


def test_committed_word_count_is_none_for_unknown_path(repo):
    assert hook._committed_word_count(repo, "docs/nope.md") is None


def test_committed_word_count_is_none_on_binary(repo):
    (repo / "docs" / "blob.bin").write_bytes(b"\xff\xfe\x00\x01" * 100)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "blob")
    assert hook._committed_word_count(repo, "docs/blob.bin") is None


def test_a_git_error_that_is_not_a_missing_file_is_announced_on_stderr(monkeypatch, capsys, repo):
    """The whole class of bug this hook shipped with was invisible because a
    broken lookup and an untracked file returned the same thing. A guard that is
    silently dead looks exactly like one that ran and approved."""
    def _boom(*a, **k):
        return subprocess.CompletedProcess(a, 128, b"", b"fatal: not a tree object")

    monkeypatch.setattr(subprocess, "run", _boom)
    assert hook._committed_word_count(repo, REL) is None
    assert "could not resolve" in capsys.readouterr().err


@pytest.mark.parametrize("exc", [OSError("no git"), subprocess.TimeoutExpired("git", 5)])
def test_missing_or_wedged_git_is_silent(monkeypatch, capsys, repo, exc):
    """Not worth a message: anything else the session does with git fails
    visibly in the same breath."""
    def _raise(*a, **k):
        raise exc

    monkeypatch.setattr(subprocess, "run", _raise)
    assert hook._committed_word_count(repo, REL) is None
    assert capsys.readouterr().err == ""


# --------------------------------------------------------------------------- #
# Wiring
# --------------------------------------------------------------------------- #


def test_the_hook_is_actually_wired_in_hooks_json():
    """Removing the wiring left all 520 tests in this scope green. The existing
    wiring test only checks the reverse direction — that referenced scripts
    exist — so a dropped entry (a merge conflict, a careless sync reconcile)
    would disable the guard permanently with nothing to notice."""
    config = json.loads((HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))
    commands = [
        h.get("command", "")
        for group in config["hooks"].get("PostToolUse", [])
        for h in group.get("hooks", [])
    ]
    assert any("warn-wholesale-rewrite.py" in c for c in commands)


def test_the_wiring_matcher_is_write_only():
    """Wired on `Edit|Write` it spawned an interpreter on every Edit — the
    highest-frequency tool here — to immediately return 0."""
    config = json.loads((HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))
    for group in config["hooks"].get("PostToolUse", []):
        if any("warn-wholesale-rewrite.py" in h.get("command", "") for h in group.get("hooks", [])):
            assert group["matcher"] == "Write"
            return
    pytest.fail("warn-wholesale-rewrite.py is not wired on PostToolUse")
