"""Tests for manual_worktree.py — the plain-git fallback for `EnterWorktree`.

These use real `git worktree` invocations rather than mocks. The whole subject is
how git resolves paths on a case-insensitive filesystem, which is precisely the
behaviour a mock would paper over.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

import manual_worktree as mw


def _git(cwd, *args):
    subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True
    )


@pytest.fixture
def repo(tmp_path):
    """A repo with one commit on `main` and an `origin` pointing at itself.

    Self-remote rather than a second clone: the script only needs
    `refs/remotes/origin/*` to resolve, and a fetch from itself produces that
    with far less setup than a real pair.
    """
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "a@b.c")
    _git(r, "config", "user.name", "a")
    (r / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "seed")
    _git(r, "remote", "add", "origin", str(r))
    _git(r, "fetch", "-q", "origin")
    return r


# --------------------------------------------------------------------------- #
# Creating a worktree without EnterWorktree
# --------------------------------------------------------------------------- #


def test_creates_a_worktree_on_a_new_branch(repo):
    result = mw.create_worktree(repo, "alpha", "origin/main")

    assert Path(result["worktree_path"]).is_dir()
    assert (Path(result["worktree_path"]) / "seed.txt").exists()
    assert result["branch"] == "worktree-alpha"
    assert result["relative_path"] == ".claude/worktrees/alpha"


def test_reports_the_main_checkout_so_the_caller_needs_no_extra_lookup(repo):
    """The skill copies env files from the main checkout, and its whole design
    budget goes on minimising round-trips — so resolving this here saves the
    caller a tool call it would otherwise have to spend."""
    result = mw.create_worktree(repo, "beta", "origin/main")
    assert os.path.realpath(result["main_checkout"]) == os.path.realpath(str(repo))


def test_the_returned_path_is_canonical_not_the_spelling_we_passed(repo):
    """Returning git's own resolution is the point: handing back a re-joined
    string would propagate whatever casing the caller happened to use, which is
    the bug this script routes around."""
    odd = Path(str(repo).swapcase()) if os.name == "nt" else repo
    result = mw.create_worktree(odd if odd.exists() else repo, "gamma", "origin/main")
    assert result["worktree_path"] == os.path.realpath(result["worktree_path"])


def test_a_duplicate_branch_is_refused_with_an_actionable_message(repo):
    mw.create_worktree(repo, "dup", "origin/main")
    with pytest.raises(mw.GitError) as exc:
        mw.create_worktree(repo, "dup", "origin/main")
    assert "already exists" in str(exc.value)
    assert "git branch -D worktree-dup" in str(exc.value), (
        "the error must name the way out; a bare failure makes the user go digging"
    )


# --------------------------------------------------------------------------- #
# Cleaning up after a failed EnterWorktree
# --------------------------------------------------------------------------- #


def test_a_registered_leftover_worktree_is_cleaned_before_retrying(repo):
    """The observed failure mode: EnterWorktree registers the worktree with git
    and THEN refuses, so a stale entry blocks the next attempt at that path."""
    path = repo / ".claude/worktrees/stale"
    _git(repo, "worktree", "add", "-q", str(path), "-b", "leftover", "origin/main")
    _git(repo, "worktree", "lock", str(path))

    assert mw.clean_stale_worktree(repo, path) is True
    assert os.path.realpath(str(path)) not in mw._registered_worktrees(repo)


def test_creating_over_a_stale_entry_succeeds_and_says_it_cleaned(repo):
    path = repo / ".claude/worktrees/reuse"
    _git(repo, "worktree", "add", "-q", str(path), "-b", "leftover2", "origin/main")
    _git(repo, "worktree", "lock", str(path))

    result = mw.create_worktree(repo, "reuse", "origin/main")
    assert result["cleaned_stale_entry"] is True
    assert Path(result["worktree_path"]).is_dir()


def test_cleanup_is_a_noop_when_there_is_nothing_to_clean(repo):
    assert mw.clean_stale_worktree(repo, repo / ".claude/worktrees/never-made") is False


def test_a_nonempty_unregistered_directory_is_never_deleted(repo):
    """It is somebody's work. Deleting it to make room is exactly the
    'destroyed to fix a mistake' failure the skill warns about — better to fail
    the add and let a human look."""
    path = repo / ".claude/worktrees/occupied"
    path.mkdir(parents=True)
    (path / "someones-work.txt").write_text("do not delete\n", encoding="utf-8")

    mw.clean_stale_worktree(repo, path)
    assert (path / "someones-work.txt").exists()


# --------------------------------------------------------------------------- #
# The casing diagnosis
# --------------------------------------------------------------------------- #


def test_matching_paths_report_no_mismatch(repo):
    assert mw.casing_mismatch(repo) is None


def test_a_case_only_difference_is_reported(tmp_path):
    real = tmp_path / "Code"
    real.mkdir()
    probe = tmp_path / "code"
    if not probe.exists():
        pytest.skip("filesystem is case-sensitive; this refusal cannot occur here")

    m = mw.casing_mismatch(probe)
    assert m is not None
    assert m["as_given"].lower() == m["on_disk"].lower()
    assert m["as_given"] != m["on_disk"]


def test_a_genuinely_different_directory_is_not_called_a_casing_issue(tmp_path):
    # Otherwise the diagnosis would fire on any symlinked or substituted path
    # and send someone chasing a casing bug that isn't there.
    d = tmp_path / "real"
    d.mkdir()
    assert mw.casing_mismatch(d) is None


# --------------------------------------------------------------------------- #
# CLI contract
# --------------------------------------------------------------------------- #


def test_cli_emits_json_the_skill_can_read(repo, capsys):
    rc = mw.main(["--repo", str(repo), "--name", "cli"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["branch"] == "worktree-cli"
    assert Path(payload["worktree_path"]).is_dir()


def test_cli_diagnose_needs_no_name(repo, capsys):
    rc = mw.main(["--repo", str(repo), "--diagnose"])
    assert rc == 0
    assert "casing_mismatch" in json.loads(capsys.readouterr().out)


def test_cli_reports_failure_as_json_and_exit_1(repo, capsys):
    mw.main(["--repo", str(repo), "--name", "twice"])
    capsys.readouterr()
    rc = mw.main(["--repo", str(repo), "--name", "twice"])
    assert rc == 1
    assert "error" in json.loads(capsys.readouterr().out)


def test_default_base_prefers_the_remote_default_branch(repo):
    assert mw.default_base(repo).startswith("origin/")


def test_default_base_falls_back_when_there_is_no_remote(tmp_path):
    r = tmp_path / "local-only"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "a@b.c")
    _git(r, "config", "user.name", "a")
    (r / "f.txt").write_text("x\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "c")
    assert mw.default_base(r) == "HEAD"


def test_git_failures_surface_as_giterror_not_a_traceback(tmp_path):
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    with pytest.raises(mw.GitError):
        mw.create_worktree(not_a_repo, "x", "HEAD")
