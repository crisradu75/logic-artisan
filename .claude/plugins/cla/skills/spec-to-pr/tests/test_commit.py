"""commit.py tests."""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pytest

import commit


@pytest.fixture(autouse=True)
def _repo_root(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(commit, "REPO_ROOT", tmp_repo)


def test_missing_message_file(tmp_repo: Path, capsys):
    rc = commit.main(["--message-file", "nonexistent.txt", "README.md"])
    assert rc == 2
    assert "does not exist" in capsys.readouterr().err


def test_no_changes_refuses(tmp_repo: Path, capsys):
    msg = tmp_repo / "msg.txt"
    msg.write_text("noop\n", encoding="utf-8")
    rc = commit.main(["--message-file", str(msg), "README.md"])
    assert rc == 3
    assert "no staged changes" in capsys.readouterr().err


def test_happy_path(tmp_repo: Path):
    msg = tmp_repo / "msg.txt"
    msg.write_text("feat: a thing\n", encoding="utf-8")
    target = tmp_repo / "newfile.txt"
    target.write_text("hello\n", encoding="utf-8")
    rc = commit.main(["--message-file", str(msg), "newfile.txt"])
    assert rc == 0
    log = subprocess.run(["git", "log", "--oneline", "-1"],
                         cwd=tmp_repo, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    assert "feat: a thing" in log


def test_inline_message_with_multiple_paths(tmp_repo: Path):
    """Regression: previously `commit.py --message <subj> <p1> <p2>` exited 4
    because argparse's optional positional message_file consumed <p1>, then the
    mutex check rejected `--message` + message_file. Two-positional-path call
    must succeed cleanly."""
    a = tmp_repo / "a.txt"
    b = tmp_repo / "b.txt"
    a.write_text("a\n", encoding="utf-8")
    b.write_text("b\n", encoding="utf-8")
    rc = commit.main(["--message", "fix: review round 1", "a.txt", "b.txt"])
    assert rc == 0, "two positional paths after --message must succeed"
    log = subprocess.run(["git", "log", "--oneline", "-1"],
                         cwd=tmp_repo, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    assert "fix: review round 1" in log


def test_inline_message_happy_path(tmp_repo: Path):
    target = tmp_repo / "newfile.txt"
    target.write_text("hello\n", encoding="utf-8")
    rc = commit.main(["--message", "fix: review round 1", "newfile.txt"])
    assert rc == 0
    log = subprocess.run(["git", "log", "--oneline", "-1"],
                         cwd=tmp_repo, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    assert "fix: review round 1" in log


def test_inline_message_short_flag(tmp_repo: Path):
    target = tmp_repo / "newfile.txt"
    target.write_text("hello\n", encoding="utf-8")
    rc = commit.main(["-m", "chore: archive my-change", "newfile.txt"])
    assert rc == 0
    log = subprocess.run(["git", "log", "--oneline", "-1"],
                         cwd=tmp_repo, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    assert "chore: archive my-change" in log


def test_neither_message_source_rejected(tmp_repo: Path, capsys):
    """Argparse mutually-exclusive group exits 2 with its own error text."""
    with pytest.raises(SystemExit) as exc:
        commit.main(["README.md"])
    assert exc.value.code == 2
    assert "one of the arguments" in capsys.readouterr().err.lower()


def test_inline_message_no_changes_refuses(tmp_repo: Path, capsys):
    rc = commit.main(["--message", "noop", "README.md"])
    assert rc == 3
    assert "no staged changes" in capsys.readouterr().err


def test_non_ascii_message_does_not_crash_on_cp1252_stdout(tmp_repo: Path, monkeypatch):
    """Regression: commit.py echoed git's stdout (the commit subject) to stdout
    via print(). On Windows' cp1252 console a non-ASCII subject char (e.g. `→`)
    raised UnicodeEncodeError — the commit landed but the script crashed echoing
    it. main() must reconfigure stdout to UTF-8 first. Simulate a cp1252 stdout
    backed by a byte buffer and assert no crash + the glyph round-trips."""
    buf = io.BytesIO()
    cp1252_stdout = io.TextIOWrapper(buf, encoding="cp1252", line_buffering=True)
    monkeypatch.setattr(sys, "stdout", cp1252_stdout)

    target = tmp_repo / "arrow.txt"
    target.write_text("x\n", encoding="utf-8")
    rc = commit.main(["-m", "fix: TD1/TD3 → TD1", "arrow.txt"])
    cp1252_stdout.flush()

    assert rc == 0
    assert "→" in buf.getvalue().decode("utf-8")


def test_non_ascii_stderr_does_not_crash_on_cp1252(tmp_repo: Path, monkeypatch):
    """Regression: _force_utf8_stdout() reconfigures stderr too, not just stdout.
    commit.py echoes git's stderr (e.g. a rejecting hook's message) via print(...,
    file=sys.stderr). A non-ASCII char on a cp1252 stderr raised UnicodeEncodeError
    the same way stdout did. A hook that prints `→` to stderr must surface as a
    forwarded non-zero rc, not a crash."""
    buf = io.BytesIO()
    cp1252_stderr = io.TextIOWrapper(buf, encoding="cp1252", line_buffering=True)
    monkeypatch.setattr(sys, "stderr", cp1252_stderr)

    hook = tmp_repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'rejected → retry' >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    target = tmp_repo / "blocked.txt"
    target.write_text("content\n", encoding="utf-8")
    rc = commit.main(["--message", "feat: blocked", "blocked.txt"])
    cp1252_stderr.flush()

    assert rc != 0
    assert rc != 3  # the hook's non-zero code is forwarded, not masked
    assert "→" in buf.getvalue().decode("utf-8")


def test_pre_commit_hook_rejection_surfaces(tmp_repo: Path, capsys):
    """Regression: a pre-commit hook that exits non-zero must propagate
    git's exit code and emit the hook's stderr to the user — not be silently
    treated as success or as a "no staged changes" error. Root CLAUDE.md
    explicitly warns against masking hook failures with --amend, so the
    orchestrator MUST see the rejection clearly."""
    hooks_dir = tmp_repo / ".git" / "hooks"
    hook = hooks_dir / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'hook says no' >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    target = tmp_repo / "blocked.txt"
    target.write_text("content\n", encoding="utf-8")
    rc = commit.main(["--message", "feat: blocked", "blocked.txt"])
    # git commit returns 1 when a pre-commit hook rejects; commit.py forwards it.
    assert rc != 0
    assert rc != 3  # not the "no staged changes" code — that would mask the real reason
