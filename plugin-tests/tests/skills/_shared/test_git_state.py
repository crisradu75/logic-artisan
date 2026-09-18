"""git_state.py tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla" / "skills" / "_shared" / "scripts" / "git_state.py"


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the script with an explicit NEUTRAL cwd, never the repo under test.

    The `tmp_repo` fixture calls `monkeypatch.chdir(tmp_path)` and returns that
    same `tmp_path`, so without this the child inherited a cwd that WAS
    `repo_root`. That silently disarmed `test_worktree_relative_gitdir_resolves`:
    its docstring says a relative `gitdir:` pointer must be evaluated "against
    the worktree root, not the script's cwd", but with the two equal,
    `(repo_root / target).resolve()` and `target.resolve()` agree on every input
    the test supplies — the test asserted a property its own fixture removed, and
    a mutant deleting the `repo_root /` join could not be killed.

    `_current_branch` passes `cwd=repo_root` to git explicitly, so nothing else
    in the script reads the process cwd and no other test changes behaviour.
    This directory is a safe choice precisely because it is not any test's
    `repo_root`.
    """
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--repo-root", str(repo), *args],
        cwd=Path(__file__).parent,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def test_clean_tree_no_in_progress_op_exits_zero(tmp_repo: Path):
    result = _run(tmp_repo)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["no_in_progress_op"] is True
    assert payload["in_progress_op"] is None
    assert payload["current_branch"] == "master"


def test_cherry_pick_in_progress_exits_two(tmp_repo: Path):
    (tmp_repo / ".git" / "CHERRY_PICK_HEAD").write_text("deadbeef\n", encoding="utf-8")
    result = _run(tmp_repo)
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["no_in_progress_op"] is False
    assert payload["in_progress_op"] == "cherry-pick"
    assert "cherry-pick" in result.stderr


def test_merge_in_progress_exits_two(tmp_repo: Path):
    (tmp_repo / ".git" / "MERGE_HEAD").write_text("deadbeef\n", encoding="utf-8")
    result = _run(tmp_repo)
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["in_progress_op"] == "merge"


def test_rebase_merge_mode_in_progress_exits_two(tmp_repo: Path):
    (tmp_repo / ".git" / "rebase-merge").mkdir()
    result = _run(tmp_repo)
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["in_progress_op"] == "rebase (merge mode)"


def test_rebase_apply_mode_in_progress_exits_two(tmp_repo: Path):
    (tmp_repo / ".git" / "rebase-apply").mkdir()
    result = _run(tmp_repo)
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["in_progress_op"] == "rebase (apply mode)"


def test_revert_in_progress_exits_two(tmp_repo: Path):
    (tmp_repo / ".git" / "REVERT_HEAD").write_text("deadbeef\n", encoding="utf-8")
    result = _run(tmp_repo)
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["in_progress_op"] == "revert"


def test_expect_branch_match_exits_zero(tmp_repo: Path):
    result = _run(tmp_repo, "--expect-branch", "master")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["current_branch"] == "master"
    assert payload["expected_branch"] == "master"


def test_expect_branch_mismatch_exits_three(tmp_repo: Path):
    """A branch mismatch is exit 3, and `no_in_progress_op` stays TRUE.

    Being on the wrong branch is not an in-progress operation. The field
    reported False here until it was fixed, which is the same conflation that
    made the old `clean` name a defect — a run read `{"clean": true}` with 47
    files staged — pointing the other way: the field claimed an operation that
    was not mid-flight.

    THE MISMATCH IS STILL FULLY REPORTED, and this test asserts all four of the
    signals that carry it, so the correction cannot be mistaken for a loss of
    information: the exit code, both branch fields, and stderr.
    """
    result = _run(tmp_repo, "--expect-branch", "feature/nope")
    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert payload["no_in_progress_op"] is True, (
        "a branch mismatch is not an in-progress operation; the field answers "
        "one question and the exit code carries the verdict"
    )
    assert payload["in_progress_op"] is None
    assert payload["current_branch"] == "master"
    assert payload["expected_branch"] == "feature/nope"
    assert "expected" in result.stderr


def test_the_in_progress_paths_still_report_false(tmp_repo: Path):
    """The second branch. Correcting the exit-3 path must not weaken the field
    where it IS load-bearing — a real mid-flight operation.

    `_detect_in_progress` has six markers and one shared return, so an edit that
    stopped the field tracking it would look identical on the happy path. Pinned
    with `--expect-branch` ALSO mismatching, which is the case where the two
    rules could disagree: exit 2 wins, and the field reports the operation rather
    than the branch.
    """
    (tmp_repo / ".git" / "MERGE_HEAD").write_text("deadbeef\n", encoding="utf-8")
    result = _run(tmp_repo, "--expect-branch", "feature/nope")
    assert result.returncode == 2, "an in-progress op outranks a branch mismatch"
    payload = json.loads(result.stdout)
    assert payload["no_in_progress_op"] is False
    assert payload["in_progress_op"] == "merge"


def test_the_field_tracks_the_op_on_every_exit_code(tmp_repo: Path):
    """The invariant stated as one rule rather than three tests reading like a
    coincidence: OUTSIDE the fail-closed path, `no_in_progress_op` is exactly
    `in_progress_op is None`.

    Exit 1 is the deliberate exception — nothing could be determined, so the
    field is False with no operation named, and that asymmetry is what
    fail-closed means. It is covered by the three exit-1 tests below.
    """
    for args, expected_rc in (
        ((), 0),
        (("--expect-branch", "master"), 0),
        (("--expect-branch", "feature/nope"), 3),
    ):
        result = _run(tmp_repo, *args)
        assert result.returncode == expected_rc, (args, result.stdout)
        payload = json.loads(result.stdout)
        assert payload["no_in_progress_op"] is (payload["in_progress_op"] is None), (
            f"{args}: the field and the op it names disagree — {payload}"
        )


def test_in_progress_op_supersedes_branch_check(tmp_repo: Path):
    """Exit 2 (in-progress op) fires before exit 3 (wrong branch).

    Rationale: an in-progress op is a stronger signal — fix it first regardless
    of branch state.
    """
    (tmp_repo / ".git" / "CHERRY_PICK_HEAD").write_text("deadbeef\n", encoding="utf-8")
    result = _run(tmp_repo, "--expect-branch", "feature/anything")
    assert result.returncode == 2


def test_worktree_gitdir_file_resolves(tmp_repo: Path, tmp_path: Path):
    """When .git is a file (`gitdir: <path>`, used by `git worktree add`),
    git_state should resolve the real .git directory and still detect ops."""
    # Simulate the worktree shape by relocating .git to a sibling path.
    real_gitdir = tmp_path / "real-gitdir"
    (tmp_repo / ".git").rename(real_gitdir)
    (tmp_repo / ".git").write_text(f"gitdir: {real_gitdir}\n", encoding="utf-8")
    (real_gitdir / "CHERRY_PICK_HEAD").write_text("deadbeef\n", encoding="utf-8")

    result = _run(tmp_repo)
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["in_progress_op"] == "cherry-pick"


def test_worktree_relative_gitdir_resolves(tmp_repo: Path, tmp_path: Path):
    """When `.git` file holds a relative path (real-world `git worktree add`
    writes relative paths), the resolver should evaluate it against the
    worktree root, not the script's cwd. Production failure mode if missed:
    `Path(...).exists()` would silently be False → fail-closed exit 1 instead
    of the correct in-progress detection.
    """
    real_gitdir = tmp_path / "worktrees" / "real-gitdir"
    real_gitdir.mkdir(parents=True)
    (tmp_repo / ".git").rename(real_gitdir / "_relocated")
    # Move it back under real_gitdir so it remains a valid gitdir.
    (real_gitdir / "_relocated").rename(real_gitdir / "_inner")
    for child in (real_gitdir / "_inner").iterdir():
        child.rename(real_gitdir / child.name)
    (real_gitdir / "_inner").rmdir()
    # Relative path from tmp_repo to real_gitdir.
    import os
    rel = os.path.relpath(real_gitdir, tmp_repo)
    (tmp_repo / ".git").write_text(f"gitdir: {rel}\n", encoding="utf-8")
    (real_gitdir / "MERGE_HEAD").write_text("deadbeef\n", encoding="utf-8")

    result = _run(tmp_repo)
    assert result.returncode == 2, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    payload = json.loads(result.stdout)
    assert payload["in_progress_op"] == "merge"


def test_bisect_in_progress_exits_two(tmp_repo: Path):
    """BISECT_LOG signals an active `git bisect`."""
    (tmp_repo / ".git" / "BISECT_LOG").write_text("git bisect start\n", encoding="utf-8")
    result = _run(tmp_repo)
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["in_progress_op"] == "bisect"


def test_no_git_directory_exits_one(tmp_path: Path):
    """Non-repo directory must fail-closed (exit 1), NOT silently report clean."""
    result = _run(tmp_path)  # tmp_path has no .git
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["no_in_progress_op"] is False
    assert "error" in payload
    assert "git-state" in result.stderr


def test_malformed_worktree_gitdir_pointer_exits_one(tmp_path: Path):
    """A `.git` file that does NOT start with `gitdir: ` must fail-closed,
    not silently fall back to treating the file path as a gitdir.

    Past risk: pre-fix, `_git_dir` would return the file path; `.exists()` is
    True for a file; `_detect_in_progress` would probe `<file>/CHERRY_PICK_HEAD`
    which silently returns False → false-clean verdict.

    Uses a fresh dir (NOT tmp_repo) — on Windows, removing a real .git tree
    trips PermissionError on pack files. A standalone dir with only the
    malformed pointer is enough to exercise the fail-closed path.
    """
    fake = tmp_path / "fake-repo"
    fake.mkdir()
    (fake / ".git").write_text("not a gitdir pointer\n", encoding="utf-8")
    result = _run(fake)
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["no_in_progress_op"] is False


def test_worktree_gitdir_pointer_to_nonexistent_dir_exits_one(tmp_path: Path):
    """A `.git` file pointing at a directory that doesn't exist must fail-closed."""
    fake = tmp_path / "fake-repo"
    fake.mkdir()
    (fake / ".git").write_text(
        f"gitdir: {tmp_path / 'does-not-exist'}\n", encoding="utf-8",
    )
    result = _run(fake)
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["no_in_progress_op"] is False


def test_detached_head_returns_HEAD_as_branch(tmp_repo: Path):
    """Detached HEAD is a valid git state — `git rev-parse --abbrev-ref HEAD`
    returns the literal `"HEAD"`. The script should NOT treat this as a failure.
    """
    # Create one extra commit then detach HEAD onto it.
    subprocess.run(["git", "commit", "--allow-empty", "-q", "-m", "extra"],
                   cwd=tmp_repo, check=True)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_repo,
                         check=True, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    subprocess.run(["git", "checkout", "-q", sha], cwd=tmp_repo, check=True)

    result = _run(tmp_repo)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["no_in_progress_op"] is True
    assert payload["current_branch"] == "HEAD"


def test_detached_head_with_expect_branch_exits_three(tmp_repo: Path):
    """Detached HEAD against `--expect-branch feature/x` should be exit 3, not 1.
    The branch IS resolvable (it's literally "HEAD"); it just doesn't match.
    """
    subprocess.run(["git", "commit", "--allow-empty", "-q", "-m", "extra"],
                   cwd=tmp_repo, check=True)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_repo,
                         check=True, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    subprocess.run(["git", "checkout", "-q", sha], cwd=tmp_repo, check=True)

    result = _run(tmp_repo, "--expect-branch", "feature/anything")
    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert payload["current_branch"] == "HEAD"
    assert payload["expected_branch"] == "feature/anything"


def test_clean_tree_json_includes_null_expected_branch(tmp_repo: Path):
    """When --expect-branch is not passed, the JSON should explicitly report
    `expected_branch: null` so consumers can distinguish "not checked" from
    a string mismatch.
    """
    result = _run(tmp_repo)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["expected_branch"] is None
