"""Tests for warn-wholesale-rewrite.py.

The hook is deliberately quiet: it fires only for a `Write` that replaces a
tracked, non-trivial file with a materially shorter one. Most of these tests
therefore assert SILENCE, because a warn hook that fires on ordinary work gets
tuned out and then the one real warning is missed too.

`_committed_line_count` runs real `git` against a throwaway repo built per test
— never the repo under development, which would make the tests depend on this
repo's own history and (worse) let a test write into a live working tree.
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parents[1] / "warn-wholesale-rewrite.py"
_spec = importlib.util.spec_from_file_location("warn_wholesale_rewrite", HOOK_PATH)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A throwaway git repo with one committed 100-line file."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "config", "user.name", "T")
    (tmp_path / "doc.md").write_text("\n".join(f"line {i}" for i in range(100)) + "\n", encoding="utf-8")
    _git(tmp_path, "add", "doc.md")
    _git(tmp_path, "commit", "-qm", "add doc")
    return tmp_path


def _run(monkeypatch, repo: Path, payload: dict) -> str:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert hook.main() == 0
    return ""


def _write_payload(path: str = "doc.md", tool: str = "Write") -> dict:
    return {"tool_name": tool, "tool_input": {"file_path": path}}


# --------------------------------------------------------------------------- #
# Fires
# --------------------------------------------------------------------------- #


def test_warns_when_a_write_materially_shrinks_a_tracked_file(monkeypatch, capsys, repo):
    """The incident this hook exists for: 100 committed lines -> 70 (30% gone)."""
    (repo / "doc.md").write_text("\n".join(f"line {i}" for i in range(70)) + "\n", encoding="utf-8")
    _run(monkeypatch, repo, _write_payload())
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "doc.md" in ctx
    assert "100" in ctx and "70" in ctx
    assert "30%" in ctx


def test_the_message_asks_for_the_dropped_content_not_just_the_number(monkeypatch, capsys, repo):
    """A bare percentage is ignorable. The ask ('say what you dropped') is the
    whole mechanism — the hook cannot judge the cut, only force it to be named."""
    (repo / "doc.md").write_text("x\n" * 50, encoding="utf-8")
    _run(monkeypatch, repo, _write_payload())
    ctx = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert "what you dropped" in ctx


# --------------------------------------------------------------------------- #
# Stays silent
# --------------------------------------------------------------------------- #


def test_silent_for_edit_even_on_a_huge_shrink(monkeypatch, capsys, repo):
    """Edit keeps whatever it does not name; only Write can drop content
    silently. This is the hook's central scoping decision, so it is pinned."""
    (repo / "doc.md").write_text("x\n", encoding="utf-8")
    _run(monkeypatch, repo, _write_payload(tool="Edit"))
    assert capsys.readouterr().out == ""


def test_silent_when_the_file_grew(monkeypatch, capsys, repo):
    (repo / "doc.md").write_text("\n".join(f"line {i}" for i in range(150)) + "\n", encoding="utf-8")
    _run(monkeypatch, repo, _write_payload())
    assert capsys.readouterr().out == ""


def test_silent_on_a_shrink_under_the_threshold(monkeypatch, capsys, repo):
    """90 of 100 lines survive — a 10% trim is ordinary editing, not a rewrite."""
    (repo / "doc.md").write_text("\n".join(f"line {i}" for i in range(90)) + "\n", encoding="utf-8")
    _run(monkeypatch, repo, _write_payload())
    assert capsys.readouterr().out == ""


def test_silent_for_an_untracked_file(monkeypatch, capsys, repo):
    """Nothing was replaced, so nothing can have been lost."""
    (repo / "new.md").write_text("x\n", encoding="utf-8")
    _run(monkeypatch, repo, _write_payload("new.md"))
    assert capsys.readouterr().out == ""


def test_silent_for_a_short_baseline(monkeypatch, capsys, repo):
    """A 10-line stub cut to 2 is noise, not a lost rule."""
    (repo / "stub.md").write_text("s\n" * 10, encoding="utf-8")
    _git(repo, "add", "stub.md")
    _git(repo, "commit", "-qm", "stub")
    (repo / "stub.md").write_text("s\n" * 2, encoding="utf-8")
    _run(monkeypatch, repo, _write_payload("stub.md"))
    assert capsys.readouterr().out == ""


def test_silent_outside_the_project_root(monkeypatch, capsys, repo, tmp_path):
    outside = tmp_path.parent / "elsewhere.md"
    outside.write_text("x\n", encoding="utf-8")
    _run(monkeypatch, repo, _write_payload(str(outside)))
    assert capsys.readouterr().out == ""


def test_silent_when_not_a_git_repo(monkeypatch, capsys, tmp_path):
    """`_committed_line_count` returns None and the hook must degrade quietly —
    a guard that errors on a non-repo would break every scratch directory."""
    (tmp_path / "doc.md").write_text("x\n" * 5, encoding="utf-8")
    _run(monkeypatch, tmp_path, _write_payload())
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "payload",
    [
        "not json at all",
        "[]",
        '{"tool_name": "Write"}',
        '{"tool_name": "Write", "tool_input": null}',
        '{"tool_name": "Write", "tool_input": {"file_path": ""}}',
        '{"tool_name": "Write", "tool_input": {"file_path": 42}}',
        '{"tool_name": "Write", "tool_input": {"file_path": "does-not-exist.md"}}',
    ],
)
def test_malformed_input_never_raises(monkeypatch, capsys, repo, payload):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


# --------------------------------------------------------------------------- #
# _committed_line_count
# --------------------------------------------------------------------------- #


def test_committed_line_count_reads_head_not_the_working_tree(repo):
    """The baseline must be the COMMITTED file. If it read the working tree it
    would compare the new content against itself and never fire."""
    (repo / "doc.md").write_text("x\n", encoding="utf-8")
    assert hook._committed_line_count(repo, "doc.md") == 100


def test_committed_line_count_reads_head_not_the_index(repo):
    """HEAD, not the staging area — and the distinction is load-bearing.

    Reading the index (`git show :path`) passes every other test here, because a
    fresh commit leaves index == HEAD. It breaks on the case that matters: a
    shrink already staged, then shrunk again. Against the index each write is
    measured from the previous one, so a file cut 100 -> 85 -> 72 never trips
    the threshold and the cumulative 28% loss is never reported.
    """
    (repo / "doc.md").write_text("\n".join(f"line {i}" for i in range(85)) + "\n", encoding="utf-8")
    _git(repo, "add", "doc.md")
    assert hook._committed_line_count(repo, "doc.md") == 100


def test_a_second_shrink_is_measured_from_the_commit_not_the_staged_version(monkeypatch, capsys, repo):
    """End-to-end form of the above: two staged cuts, each under the threshold,
    together over it. The hook must still fire."""
    (repo / "doc.md").write_text("\n".join(f"line {i}" for i in range(85)) + "\n", encoding="utf-8")
    _git(repo, "add", "doc.md")
    (repo / "doc.md").write_text("\n".join(f"line {i}" for i in range(72)) + "\n", encoding="utf-8")
    _run(monkeypatch, repo, _write_payload())
    ctx = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert "100" in ctx and "72" in ctx


def test_committed_line_count_is_none_for_unknown_path(repo):
    assert hook._committed_line_count(repo, "nope.md") is None


def test_committed_line_count_is_none_on_binary(repo):
    (repo / "blob.bin").write_bytes(b"\xff\xfe\x00\x01")
    _git(repo, "add", "blob.bin")
    _git(repo, "commit", "-qm", "blob")
    assert hook._committed_line_count(repo, "blob.bin") is None
