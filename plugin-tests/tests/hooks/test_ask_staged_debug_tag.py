"""Tests for `ask-staged-debug-tag.py`: ask before a commit adds a `/cla:diagnose` debug tag.

The hook asks git what the commit would add, so every case runs on a real temp
repo (built once per session by `cached_git_repo`, copied per test). The tag is
assembled from two halves here, as in the hook, so this file's own lines never
hold it and committing it never trips the guard.
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

_PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
_HOOKS_DIR = _PLUGIN / "hooks"

TAG = "[" + "DEBUG-"
LINE = f"print('{TAG}a3f1] value')\n"


def _load():
    spec = importlib.util.spec_from_file_location("ask_staged_debug_tag", _HOOKS_DIR / "ask-staged-debug-tag.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load()


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def _build(root: Path) -> None:
    """A committed tree: `app.py` (two lines), `sub/kept.py` and a `.gitignore`
    naming `ignored.py`."""
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "commit.gpgsign", "false")
    (root / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
    (root / "app.py").write_text("one\ntwo\n", encoding="utf-8")
    (root / "sub").mkdir()
    (root / "sub" / "kept.py").write_text("one\n", encoding="utf-8")
    _git(root, "add", ".gitignore", "app.py", "sub/kept.py")
    _git(root, "commit", "-qm", "baseline")


@pytest.fixture
def repo(cached_git_repo, tmp_path) -> Path:
    return cached_git_repo("ask-staged-debug-tag", _build, tmp_path / "repo")


def _tag_app(repo: Path) -> None:
    """`app.py` gains a tagged line between its two lines, unstaged."""
    (repo / "app.py").write_text("one\n" + LINE + "two\n", encoding="utf-8")


def _run(command: str, monkeypatch, capsys, cwd: Path | str | None) -> dict | None:
    payload: dict = {"tool_input": {"command": command}}
    if cwd is not None:
        payload["cwd"] = str(cwd)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert hook.main() == 0, "this hook must never block"
    captured = capsys.readouterr()
    assert captured.err == ""
    out = captured.out.strip()
    return json.loads(out) if out else None


def _reason(payload: dict | None) -> str:
    assert payload is not None, "expected an ask"
    nested = payload["hookSpecificOutput"]
    assert nested["permissionDecision"] == "ask"
    assert "(hook: ask-staged-debug-tag.py)" in nested["permissionDecisionReason"]
    return nested["permissionDecisionReason"]


# --------------------------------------------------------------------------- #
# What the commit would add
# --------------------------------------------------------------------------- #


# requirement: git-guards / A commit that would add a debug tag asks first
def test_a_staged_tag_asks_and_names_the_line(repo, monkeypatch, capsys):
    _tag_app(repo)
    _git(repo, "add", "app.py")
    reason = _reason(_run("git commit -m 'fix: x'", monkeypatch, capsys, repo))
    assert "1 line(s)" in reason
    assert "`app.py:2`" in reason
    assert "a3f1] value" in reason


# requirement: git-guards / A commit that would add a debug tag asks first
@pytest.mark.parametrize("command", [
    "git commit -am x",
    "git commit --all -m x",
    "git commit app.py -m x",
    "git commit -m x -- app.py",
    "git add app.py && git commit -m x",
    "git add -u\ngit commit -m x",
    "git add -A; git commit -m x",
    "git add . && git commit -m x",
])
def test_a_tag_the_commit_takes_from_the_working_tree_asks(command, repo, monkeypatch, capsys):
    """The hook runs before any of the command, so a stage in the same command
    has not happened yet: the guard reads what it would stage."""
    _tag_app(repo)
    assert "`app.py:2`" in _reason(_run(command, monkeypatch, capsys, repo))


# requirement: git-guards / A commit that would add a debug tag asks first
@pytest.mark.parametrize("command", [
    "git add new.py && git commit -m x",
    "git add -A && git commit -m x",
    "git add sub && git commit -m x",
    "git add ':!app.py' && git commit -m x",
])
def test_a_new_file_added_in_the_same_command_is_read_whole(command, repo, monkeypatch, capsys):
    target = "new.py" if "new.py" in command else "sub/new.py"
    (repo / target).write_text("ok\n" + LINE, encoding="utf-8")
    assert f"`{target}:2`" in _reason(_run(command, monkeypatch, capsys, repo))


def test_a_staged_new_file_and_a_path_with_a_space_are_named(repo, monkeypatch, capsys):
    (repo / "a b.py").write_text(LINE, encoding="utf-8")
    _git(repo, "add", "a b.py")
    assert "`a b.py:1`" in _reason(_run("git commit -m x", monkeypatch, capsys, repo))


def test_every_hit_is_counted_and_ten_are_named(repo, monkeypatch, capsys):
    (repo / "many.py").write_text(LINE * 12, encoding="utf-8")
    _git(repo, "add", "many.py")
    reason = _reason(_run("git commit -m x", monkeypatch, capsys, repo))
    assert "12 line(s)" in reason
    assert "`many.py:10`" in reason and "`many.py:11`" not in reason
    assert "and 2 more" in reason


@pytest.mark.parametrize("command", [
    "git -C repo commit -am x",
    "git -C repo -c core.pager=cat commit -am x",
    "echo start && git -C repo commit -am x | tail -1",
    "(git -C repo commit -am x)",
    "env A=1 git -C repo commit -am x",
    "command git -C repo commit -am x",
    "sudo git -C repo commit -am x",
    'git -C "repo" commit -am "msg with spaces"',
])
def test_the_commit_is_found_in_every_command_position(command, repo, monkeypatch, capsys):
    _tag_app(repo)
    assert "`app.py:2`" in _reason(_run(command, monkeypatch, capsys, repo.parent))


# --------------------------------------------------------------------------- #
# Silence
# --------------------------------------------------------------------------- #


def test_a_tag_left_unstaged_is_not_this_commits(repo, monkeypatch, capsys):
    _tag_app(repo)
    (repo / "sub" / "kept.py").write_text("two\n", encoding="utf-8")
    _git(repo, "add", "sub/kept.py")
    assert _run("git commit -m x", monkeypatch, capsys, repo) is None
    assert _run("git add sub/kept.py && git commit -m x", monkeypatch, capsys, repo) is None
    assert _run("git commit sub/kept.py -m x", monkeypatch, capsys, repo) is None


def test_a_tag_the_commit_only_keeps_or_removes_is_silent(repo, monkeypatch, capsys):
    (repo / "app.py").write_text("one\n" + LINE + "two\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "tagged before this run")
    (repo / "app.py").write_text("one\n" + LINE + "two\nthree\n", encoding="utf-8")
    assert _run("git commit -am x", monkeypatch, capsys, repo) is None
    (repo / "app.py").write_text("one\ntwo\n", encoding="utf-8")
    assert _run("git commit -am x", monkeypatch, capsys, repo) is None


def test_the_commit_message_is_not_read(repo, monkeypatch, capsys):
    """`/cla:diagnose`'s commit message quotes the tag on purpose."""
    (repo / "sub" / "kept.py").write_text("two\n", encoding="utf-8")
    _git(repo, "add", "sub/kept.py")
    command = f"git commit -m 'fix: x' -m 'Confirmed by {TAG}a3f1] logging both sides.'"
    assert _run(command, monkeypatch, capsys, repo) is None


@pytest.mark.parametrize("command", [
    "git commit --dry-run -am x",
    "git status && git diff",
    "git add app.py",
    "echo 'git commit -am x'",
    "git commit-tree HEAD^{tree} -m x",
    "git commit --bogus -am x",
])
def test_no_commit_no_question(command, repo, monkeypatch, capsys):
    _tag_app(repo)
    assert _run(command, monkeypatch, capsys, repo) is None


def test_an_ignored_file_is_not_swept_in_by_a_broad_add(repo, monkeypatch, capsys):
    (repo / "ignored.py").write_text(LINE, encoding="utf-8")
    assert _run("git add -A && git commit -m x", monkeypatch, capsys, repo) is None


def test_best_effort_silence_when_git_cannot_answer(repo, tmp_path, monkeypatch, capsys):
    _tag_app(repo)
    _git(repo, "add", "app.py")
    # Not a repository, a directory that does not exist, a repository named
    # another way, and no git on PATH: each is silence, never an error.
    plain = tmp_path / "plain"
    plain.mkdir()
    assert _run("git commit -m x", monkeypatch, capsys, plain) is None
    assert _run("git -C nowhere commit -m x", monkeypatch, capsys, repo) is None
    assert _run("git --git-dir=.git commit -m x", monkeypatch, capsys, repo) is None
    assert _run("GIT_DIR=.git git commit -m x", monkeypatch, capsys, repo) is None
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))
    assert _run("git commit -m x", monkeypatch, capsys, repo) is None


@pytest.mark.parametrize("raw", [
    "", "{", "null", "[]", "{}", '{"tool_input": null}', '{"tool_input": {"command": 7}}',
    '{"tool_input": {"command": "git commit -am x"}, "cwd": 3}',
])
def test_malformed_input_fails_open(raw, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


# --------------------------------------------------------------------------- #
# Cost, and the git calls themselves
# --------------------------------------------------------------------------- #


def test_one_git_answer_serves_a_chain_of_commits(repo, monkeypatch):
    calls: list[list[str]] = []
    real = hook._run_git

    def counting(directory, args, timeout):
        calls.append(args)
        return real(directory, args, timeout)

    monkeypatch.setattr(hook, "_run_git", counting)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "tool_input": {"command": "git commit -m a; git commit -m b; git commit -m c"}, "cwd": str(repo),
    })))
    hook.main()
    assert calls == [[*hook._DIFF, "--cached"]]


def test_every_git_call_shares_one_deadline(repo, monkeypatch):
    timeouts: list[float] = []

    def recording(directory, args, timeout):
        timeouts.append(timeout)
        time.sleep(0.01)
        return ""

    monkeypatch.setattr(hook, "_run_git", recording)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "tool_input": {"command": "git add -A && git commit -m a && git -C sub commit -am b"}, "cwd": str(repo),
    })))
    hook.main()
    assert len(timeouts) >= 4
    assert timeouts[0] <= hook.GIT_BUDGET_SECONDS
    assert all(later < earlier for earlier, later in zip(timeouts, timeouts[1:]))


def test_an_exhausted_deadline_runs_no_git(repo, monkeypatch, capsys):
    _tag_app(repo)
    _git(repo, "add", "app.py")
    monkeypatch.setattr(hook, "GIT_BUDGET_SECONDS", 0.0)
    assert _run("git commit -m x", monkeypatch, capsys, repo) is None


def test_pathspecs_follow_a_double_dash_and_the_diff_ignores_user_config(repo, monkeypatch, capsys):
    """SECURITY: text from the command never reaches git as an option, and a
    user's diff configuration cannot change what the hook parses."""
    _git(repo, "config", "diff.noprefix", "true")
    _git(repo, "config", "diff.mnemonicPrefix", "true")
    _git(repo, "config", "color.diff", "always")
    _git(repo, "config", "diff.external", "false")
    _tag_app(repo)
    assert "`app.py:2`" in _reason(_run("git commit -am x", monkeypatch, capsys, repo))
    calls: list[list[str]] = []
    real = hook._run_git
    monkeypatch.setattr(hook, "_run_git", lambda d, a, t: calls.append(a) or real(d, a, t))
    (repo / "--output=pwned").write_text(LINE, encoding="utf-8")
    reason = _reason(_run("git add -- --output=pwned && git commit -m x", monkeypatch, capsys, repo))
    assert "`--output=pwned:1`" in reason
    for args in calls:
        if "--output=pwned" in args:
            assert args.index("--") < args.index("--output=pwned")
    assert not (repo / "pwned").exists()


def test_a_500k_hostile_command_stays_fast(repo, monkeypatch, capsys):
    for unit in ("git commit -m x; ", "git add a && ", "git commit -m \"$(cat <<'E'\nx\nE\n)\"\n"):
        command = unit * (500_000 // len(unit))
        started = time.perf_counter()
        _run(command, monkeypatch, capsys, repo)
        assert time.perf_counter() - started < hook.GIT_BUDGET_SECONDS + 3.0


def test_the_tag_matches_the_one_diagnose_writes():
    """A rename of the tag in `/cla:diagnose` that misses this hook leaves it
    searching for a string nothing writes."""
    skill = (_PLUGIN / "skills" / "diagnose" / "SKILL.md").read_text(encoding="utf-8")
    ship = (_PLUGIN / "skills" / "_shared" / "references" / "ship.md").read_text(encoding="utf-8")
    assert f"`{hook.TAG}xxxx]`" in skill
    assert "\\" + hook.TAG in ship
    assert hook.TAG not in (_HOOKS_DIR / "ask-staged-debug-tag.py").read_text(encoding="utf-8")
