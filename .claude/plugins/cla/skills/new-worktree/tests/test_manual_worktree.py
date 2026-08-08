"""Tests for manual_worktree.py — the plain-git fallback for `EnterWorktree`.

These use real `git worktree` invocations rather than mocks. The whole subject is
how git resolves paths on a case-insensitive filesystem, which is precisely the
behaviour a mock would paper over.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import manual_worktree as mw



def make_dir_alias(link: Path, real: Path) -> None:
    """Create `link` -> `real` as a directory alias, or skip if neither works.

    A real symlink where permitted, else an NTFS junction (`mklink /J`), which
    needs no elevated privileges on Windows -- unlike a symlink, which raises
    WinError 1314 for every unprivileged account. Without the fallback these
    tests skipped on the ONE platform whose path handling they exist to check,
    while the suite still reported green.

    `os.path.realpath` resolves a junction exactly like a symlink, and every
    caller here goes through `realpath`, so the substitution is exact.
    (`os.path.islink()` is False for a junction -- irrelevant here, and exactly
    why `block-unsafe-recursive-delete` does its own reparse-point check rather
    than trusting `islink`.)
    """
    try:
        link.symlink_to(real, target_is_directory=True)
        return
    except (OSError, NotImplementedError, AttributeError):
        pass
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(real)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        pytest.skip(f"neither symlink nor junction creation permitted here: {result.stderr}")

def _git(cwd, *args):
    subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True, encoding="utf-8", errors="replace"
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
    the bug this script routes around.

    Asserted against the independently-computed canonical path. The earlier
    version asserted `result == realpath(result)`, which is true of any
    already-normalised string and so held even on POSIX where the test passed
    the ordinary spelling — it proved idempotence of `realpath`, not anything
    about the feature.
    """
    result = mw.create_worktree(repo, "gamma", "origin/main")
    assert result["worktree_path"] == os.path.realpath(
        str(repo / ".claude/worktrees/gamma")
    )


def test_a_symlinked_repo_spelling_still_yields_the_canonical_worktree_path(repo, tmp_path):
    """Runs on every platform, unlike the case-only tests, so the canonicalisation
    is pinned in CI rather than only on a Windows developer machine."""
    alias = tmp_path / "alias"
    make_dir_alias(alias, Path(repo))

    result = mw.create_worktree(alias, "delta", "origin/main")
    assert result["worktree_path"] == os.path.realpath(
        str(repo / ".claude/worktrees/delta")
    )
    assert str(alias) not in result["worktree_path"]


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


def test_a_registration_whose_directory_vanished_is_pruned_and_reported(repo):
    """The other half of the half-created state, and the half `remove` cannot fix.

    `worktree prune` exits 0 whether or not it dropped anything, so the earlier
    version could not tell and returned False after genuinely cleaning — a
    result that flows to the caller as `cleaned_stale_entry` and would have said
    "nothing was stale" about a run that removed a registration.
    """
    path = repo / ".claude/worktrees/vanished"
    _git(repo, "worktree", "add", "-q", str(path), "-b", "vanished-branch", "origin/main")
    shutil.rmtree(path)  # directory gone, registration left behind

    assert os.path.realpath(str(path)) in mw._registered_worktrees(repo)
    assert mw.clean_stale_worktree(repo, path) is True
    assert os.path.realpath(str(path)) not in mw._registered_worktrees(repo)


def test_a_nonempty_unregistered_directory_is_never_deleted(repo):
    """It is somebody's work. Deleting it to make room is exactly the
    'destroyed to fix a mistake' failure the skill warns about — better to fail
    the add and let a human look."""
    path = repo / ".claude/worktrees/occupied"
    path.mkdir(parents=True)
    (path / "someones-work.txt").write_text("do not delete\n", encoding="utf-8")

    assert mw.clean_stale_worktree(repo, path) is False
    assert (path / "someones-work.txt").exists()

    # And the user-visible consequence the SKILL.md documents: the add fails
    # rather than proceeding over the top of it.
    with pytest.raises(mw.GitError):
        mw.create_worktree(repo, "occupied", "origin/main")
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


def test_a_plain_directory_reports_nothing(tmp_path):
    d = tmp_path / "real"
    d.mkdir()
    assert mw.casing_mismatch(d) is None


def test_a_symlinked_path_is_reported_as_indirection_not_as_casing(tmp_path):
    """The branch the previous version of this test never reached.

    It created a plain directory, so `casing_mismatch` returned at the first
    `as_given == resolved` check and the `.lower()` comparison was never
    exercised — deleting that guard left the suite green. It also asserted the
    result should be None, locking in a conflation: a path that resolves
    somewhere else is a real finding, and answering `null` tells a user their
    paths are clean while holding proof they are not.
    """
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    make_dir_alias(alias, Path(real))

    m = mw.casing_mismatch(alias)
    assert m is not None and m["kind"] == "path_indirection"
    assert m["as_given"].lower() != m["on_disk"].lower()


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
    # Exact, not `startswith("origin/")`: that was satisfied by either the
    # symbolic-ref branch or the candidate-probe fallback, so it could not tell
    # which path ran and neither was reliably covered.
    assert mw.default_base(repo) == "origin/main"


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


# --------------------------------------------------------------------------- #
# Refusing to destroy work
# --------------------------------------------------------------------------- #


def test_a_registered_worktree_with_uncommitted_work_is_never_force_removed(repo):
    """`remove --force` deletes modified and untracked files, and the `unlock`
    that precedes it is what lets that succeed on an entry somebody locked
    deliberately. "It sits at the path I want" is not evidence a worktree is
    stale — a live one from a concurrent session looks identical."""
    path = repo / ".claude/worktrees/busy"
    _git(repo, "worktree", "add", "-q", str(path), "-b", "busy-branch", "origin/main")
    (path / "seed.txt").write_text("work in progress\n", encoding="utf-8")
    (path / "untracked.txt").write_text("also mine\n", encoding="utf-8")

    with pytest.raises(mw.GitError) as exc:
        mw.clean_stale_worktree(repo, path)
    assert "uncommitted changes" in str(exc.value)
    assert f"git worktree remove {path}" in str(exc.value), "name the way out"

    assert (path / "untracked.txt").exists()
    assert (path / "seed.txt").read_text(encoding="utf-8") == "work in progress\n"


def test_a_clean_registered_worktree_is_still_cleaned(repo):
    """Non-vacuity for the guard above: if the dirty check refused everything,
    the stale-entry cleanup this script exists for would be dead."""
    path = repo / ".claude/worktrees/clean"
    _git(repo, "worktree", "add", "-q", str(path), "-b", "clean-branch", "origin/main")
    assert mw.clean_stale_worktree(repo, path) is True


# --------------------------------------------------------------------------- #
# Input validation and the base ref
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("bad", ["../escape", "a/b", "..", "", "sub" + chr(92) + "dir"])
def test_a_name_that_would_escape_the_worktree_dir_is_refused(bad):
    # Otherwise `--name ../../x` places the worktree outside .claude/worktrees
    # and points the cleanup logic at a directory nobody meant to touch.
    if chr(92) in bad and os.path.altsep is None and os.path.sep != chr(92):
        pytest.skip("backslash is a legal filename character here")
    with pytest.raises(mw.GitError):
        mw.validate_name(bad)


def test_an_ordinary_name_is_accepted():
    assert mw.validate_name("my-task") == "my-task"


def test_the_worktree_actually_lands_on_the_requested_base(repo):
    """Nothing asserted this: dropping `base` from the `worktree add` argv left
    the suite green, because in the fixture HEAD and origin/main are the same
    commit. Advancing main first makes the two distinguishable."""
    fetched = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "origin/main"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    ).stdout.strip()
    (repo / "moved-on.txt").write_text("later\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "advance main past origin/main")

    result = mw.create_worktree(repo, "based", "origin/main")
    head = subprocess.run(
        ["git", "-C", result["worktree_path"], "rev-parse", "HEAD"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    ).stdout.strip()
    assert head == fetched, "the worktree must branch from the requested base"


def test_diagnose_creates_nothing(repo, capsys):
    # The test that only checked for the key would pass even if --diagnose fell
    # through and created a worktree.
    mw.main(["--repo", str(repo), "--diagnose"])
    capsys.readouterr()
    assert not (repo / ".claude" / "worktrees").exists()


def test_a_missing_name_is_reported_as_json_not_as_an_argparse_exit(repo, capsys):
    """`parser.error` exits 2 with plain text on stderr, which breaks the
    documented contract of JSON on stdout and leaves the calling skill with
    nothing parseable."""
    rc = mw.main(["--repo", str(repo)])
    assert rc == 1
    assert "--name is required" in json.loads(capsys.readouterr().out)["error"]


# --------------------------------------------------------------------------- #
# --print-path: the contract the repo-root `claw` launcher depends on
#
# claw assigns this script's stdout to a shell variable and then `cd`s into it,
# so the shape matters more than usual: a bare path on success, NOTHING on
# stdout on failure (an error message there would be `cd`-ed into), and a
# non-zero exit so the launcher can bail before starting Claude.
# --------------------------------------------------------------------------- #


def test_print_path_emits_a_bare_usable_path_and_nothing_else(repo, capsys):
    rc = mw.main(["--repo", str(repo), "--name", "alpha", "--print-path"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.endswith("\n"), "shell $(...) strips the trailing newline; keep it"
    path = out.strip()
    assert "\n" not in path, "exactly one line, or the shell variable holds garbage"
    assert not path.startswith("{"), "must not be JSON in this mode"
    assert Path(path).is_dir(), "the launcher cd's into this; it must exist"
    assert Path(path).name == "alpha"


def test_print_path_writes_errors_to_stderr_not_stdout(repo, capsys):
    """A launcher captures stdout. An error message there would be treated as a
    path — so on failure stdout must be EMPTY, not helpful."""
    mw.main(["--repo", str(repo), "--name", "dup", "--print-path"])
    capsys.readouterr()
    rc = mw.main(["--repo", str(repo), "--name", "dup", "--print-path"])
    captured = capsys.readouterr()
    assert rc == 1
    assert captured.out.strip() == "", "stdout must be empty on failure"
    assert "manual_worktree" in captured.err


def test_print_path_rejects_a_traversal_name_without_printing_a_path(repo, capsys):
    rc = mw.main(["--repo", str(repo), "--name", "../escape", "--print-path"])
    captured = capsys.readouterr()
    assert rc == 1
    assert captured.out.strip() == ""
    assert "single path segment" in captured.err


def test_without_print_path_the_json_contract_is_unchanged(repo, capsys):
    """The new flag must not alter the existing default output shape, which the
    new-worktree skill parses."""
    rc = mw.main(["--repo", str(repo), "--name", "beta"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["worktree_path"].endswith("beta")


def test_without_print_path_errors_stay_json_on_stdout(repo, capsys):
    mw.main(["--repo", str(repo), "--name", "gamma2"])
    capsys.readouterr()
    rc = mw.main(["--repo", str(repo), "--name", "gamma2"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "error" in json.loads(captured.out)
