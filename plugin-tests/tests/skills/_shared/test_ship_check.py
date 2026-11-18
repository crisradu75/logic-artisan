"""ship_check.py tests: real repos with a local bare `origin`, one test per exit path.

Layout of every repo here: `<tmp>/origin.git` (bare) and `<tmp>/work` (the checkout), with
`origin` set to the RELATIVE url `../origin.git`. git resolves it from the checkout, so a copy
of the cached template pushes to its own copy of the remote, never into the template.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).resolve().parents[4]
    / ".claude" / "plugins" / "cla" / "skills" / "_shared" / "scripts" / "ship_check.py"
)

def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=check,
    )


def _build(root: Path) -> None:
    _git(root, "init", "-q", "--bare", "-b", "main", "origin.git")
    work = root / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    _git(work, "config", "user.email", "test@example.com")
    _git(work, "config", "user.name", "Test")
    (work / "README.md").write_text("# tmp\n", encoding="utf-8")
    _git(work, "add", "README.md")
    _git(work, "commit", "-q", "-m", "initial")
    _git(work, "remote", "add", "origin", "../origin.git")
    _git(work, "push", "-q", "-u", "origin", "main")


@pytest.fixture
def work(tmp_path: Path, cached_git_repo) -> Path:
    """A checkout on `main`, pushed, with `main` tracking `origin/main`."""
    cached_git_repo("_shared/ship_check", _build, tmp_path)
    return tmp_path / "work"


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # A neutral cwd: the script must check --root, not wherever it was started.
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args, "--root", str(root)],
        cwd=Path(__file__).parent, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def _first(r: subprocess.CompletedProcess[str]) -> str:
    return r.stdout.splitlines()[0]


def _commit(work: Path, msg: str = "change", *extra: str) -> None:
    (work / "f.txt").write_text(msg + "\n", encoding="utf-8")
    _git(work, "add", "f.txt")
    _git(work, "commit", "-q", "-m", msg, *extra)


def _single_branch_clone(tmp_path: Path) -> Path:
    """A `--single-branch` clone of `main`: its fetch refspec maps `main` only."""
    _git(tmp_path, "clone", "-q", "--single-branch", "-b", "main", "origin.git", "single")
    clone = tmp_path / "single"
    _git(clone, "config", "user.email", "s@example.com")
    _git(clone, "config", "user.name", "S")
    return clone


def _unreachable(work: Path) -> None:
    _git(work, "remote", "set-url", "origin", "../no-such-remote.git")


# ---------------------------------------------------------------- preflight


# requirement: change-workflow / A new branch is checked for collisions before it is made
def test_preflight_create_passes_when_the_branch_is_new(work: Path):
    r = _run(work, "preflight", "--branch", "feature/a-b", "--base", "main")
    assert r.returncode == 0, r.stdout
    assert _first(r) == "OK preflight create: feature/a-b"


# requirement: change-workflow / A new branch is checked for collisions before it is made
def test_preflight_create_fails_on_a_local_branch_with_a_slash(work: Path):
    _git(work, "branch", "feature/a-b")
    r = _run(work, "preflight", "--branch", "feature/a-b", "--base", "main")
    assert r.returncode == 1
    assert _first(r) == "FAIL preflight create: 1 problem(s)"
    assert "PROBLEM local-branch: refs/heads/feature/a-b exists locally" in r.stdout


# requirement: change-workflow / A new branch is checked for collisions before it is made
def test_preflight_create_fails_on_a_branch_only_the_remote_has(work: Path):
    _git(work, "push", "-q", "origin", "main:refs/heads/feature/x")
    _git(work, "update-ref", "-d", "refs/remotes/origin/feature/x")
    r = _run(work, "preflight", "--branch", "feature/x", "--base", "main")
    assert r.returncode == 1
    assert r.stdout.splitlines()[1:] == ["PROBLEM remote-branch: origin has refs/heads/feature/x"]


@pytest.mark.parametrize("longer", ["feature/feat", "refs/heads/feat"])
def test_preflight_matches_the_remote_ref_name_exactly(work: Path, longer: str):
    # `git ls-remote origin <pattern>` lists every ref whose name ENDS in the pattern. A bare `feat`
    # lists `refs/heads/feature/feat`; even the full `refs/heads/feat` lists a branch literally named
    # `refs/heads/feat`. Neither is a collision with `feat`: each case fails without the exact match.
    _git(work, "push", "-q", "origin", f"main:refs/heads/{longer}")
    _git(work, "update-ref", "-d", f"refs/remotes/origin/{longer}")
    r = _run(work, "preflight", "--branch", "feat", "--base", "main")
    assert r.returncode == 0, r.stdout


# requirement: change-workflow / A new branch is checked for collisions before it is made
def test_preflight_fails_on_a_remote_tracking_ref(work: Path):
    _git(work, "update-ref", "refs/remotes/origin/feature/x", "HEAD")
    r = _run(work, "preflight", "--branch", "feature/x", "--base", "main")
    assert r.returncode == 1
    assert r.stdout.splitlines()[1].startswith("PROBLEM remote-tracking: refs/remotes/origin/feature/x exists")


def test_preflight_on_the_branch_itself_skips_the_collision_check(work: Path):
    _git(work, "checkout", "-q", "-b", "feature/x")
    _git(work, "push", "-q", "-u", "origin", "feature/x")
    r = _run(work, "preflight", "--branch", "feature/x", "--base", "main")
    assert r.returncode == 0, r.stdout
    assert _first(r) == "OK preflight on-branch: feature/x"


# requirement: change-workflow / A new branch is checked for collisions before it is made
def test_preflight_rename_passes_on_a_fresh_branch_with_no_commits(work: Path):
    _git(work, "checkout", "-q", "-b", "worktree-abc")
    r = _run(work, "preflight", "--branch", "feature/x", "--base", "main")
    assert r.returncode == 0, r.stdout
    assert _first(r) == "OK preflight rename: feature/x"


# requirement: change-workflow / A new branch is checked for collisions before it is made
def test_preflight_rename_fails_on_commits_to_lose(work: Path):
    _git(work, "checkout", "-q", "-b", "worktree-abc")
    _commit(work)
    r = _run(work, "preflight", "--branch", "feature/x", "--base", "main")
    assert r.returncode == 1
    assert _first(r) == "FAIL preflight rename: 1 problem(s)"
    assert "PROBLEM commits-to-lose: HEAD has 1 commit(s) not on origin/main" in r.stdout


def test_preflight_rename_counts_against_the_fetched_remote_base(work: Path):
    # HEAD's commit already reached the remote base, but the local origin/main is stale. Counted
    # without a fetch it reads as one commit to lose; the script fetches first, so it is none.
    stale = _git(work, "rev-parse", "origin/main").stdout.strip()
    _git(work, "checkout", "-q", "-b", "worktree-abc")
    _commit(work)
    _git(work, "push", "-q", "origin", "HEAD:main")
    _git(work, "update-ref", "refs/remotes/origin/main", stale)
    r = _run(work, "preflight", "--branch", "feature/x", "--base", "main")
    assert r.returncode == 0, r.stdout


def test_preflight_on_a_detached_head_fails(work: Path):
    _git(work, "checkout", "-q", "--detach")
    r = _run(work, "preflight", "--branch", "feature/x", "--base", "main")
    assert r.returncode == 1
    assert _first(r) == "FAIL preflight rename: 1 problem(s)"
    assert "PROBLEM detached:" in r.stdout


# requirement: change-workflow / A new branch is checked for collisions before it is made
def test_preflight_unreachable_remote_is_unchecked_not_a_pass(work: Path):
    _unreachable(work)
    r = _run(work, "preflight", "--branch", "feature/x", "--base", "main")
    assert r.returncode == 2
    assert _first(r).startswith("UNCHECKED remote: 'git ls-remote origin refs/heads/feature/x' failed")


def test_preflight_a_found_problem_wins_over_an_unreachable_remote(work: Path):
    _git(work, "branch", "feature/x")
    _unreachable(work)
    r = _run(work, "preflight", "--branch", "feature/x", "--base", "main")
    assert r.returncode == 1
    assert "PROBLEM local-branch:" in r.stdout
    assert "UNCHECKED remote:" in r.stdout


def test_preflight_outside_a_repo_is_unchecked(tmp_path: Path):
    r = _run(tmp_path, "preflight", "--branch", "feature/x", "--base", "main")
    assert r.returncode == 2
    assert _first(r).startswith("UNCHECKED repo:")


def test_preflight_without_a_base_is_unchecked(work: Path):
    r = _run(work, "preflight", "--branch", "feature/x")
    assert r.returncode == 2
    assert _first(r).startswith("UNCHECKED preflight:")


# requirement: change-workflow / A new branch is checked for collisions before it is made
def test_preflight_pr_base_with_an_upstream_on_the_remote_passes(work: Path):
    _git(work, "checkout", "-q", "-b", "feature/parent")
    _git(work, "push", "-q", "-u", "origin", "feature/parent")
    r = _run(work, "preflight", "--branch", "feature/child", "--base", "main", "--pr-base", "feature/parent")
    assert r.returncode == 0, r.stdout
    # --pr-base stands in for --base: on the parent is the create case.
    assert _first(r) == "OK preflight create: feature/child"


# requirement: change-workflow / A new branch is checked for collisions before it is made
def test_preflight_pr_base_without_an_upstream_fails(work: Path):
    _git(work, "checkout", "-q", "-b", "feature/parent")
    r = _run(work, "preflight", "--branch", "feature/child", "--base", "main", "--pr-base", "feature/parent")
    assert r.returncode == 1
    assert "PROBLEM no-upstream: feature/parent has no upstream" in r.stdout


def test_preflight_pr_base_whose_upstream_left_the_remote_fails(work: Path):
    _git(work, "checkout", "-q", "-b", "feature/parent")
    _git(work, "push", "-q", "-u", "origin", "feature/parent")
    _git(Path(work).parent / "origin.git", "update-ref", "-d", "refs/heads/feature/parent")
    r = _run(work, "preflight", "--branch", "feature/child", "--base", "main", "--pr-base", "feature/parent")
    assert r.returncode == 1
    assert "PROBLEM upstream-missing: feature/parent's upstream refs/heads/feature/parent is not on origin" in r.stdout


def test_preflight_pr_base_tracking_a_local_branch_fails(work: Path):
    _git(work, "checkout", "-q", "-b", "feature/parent", "--track", "main")
    r = _run(work, "preflight", "--branch", "feature/child", "--base", "main", "--pr-base", "feature/parent")
    assert r.returncode == 1
    assert "PROBLEM upstream-not-remote:" in r.stdout


def _stacked_parent(work: Path) -> None:
    """`feature/parent`, pushed with an upstream and one commit ahead of `main`; back on `main`."""
    _git(work, "checkout", "-q", "-b", "feature/parent")
    _commit(work, "parent work")
    _git(work, "push", "-q", "-u", "origin", "feature/parent")
    _git(work, "checkout", "-q", "main")


# requirement: change-workflow / A new branch is checked for collisions before it is made
def test_preflight_stacked_run_on_the_default_branch_never_approves_renaming_it(work: Path):
    # The run is stacked on feature/parent but sits on main: `git branch -m` would rename main.
    _stacked_parent(work)
    r = _run(work, "preflight", "--branch", "child", "--base", "main", "--pr-base", "feature/parent")
    assert r.returncode == 1, r.stdout
    assert _first(r) == "FAIL preflight rename: 1 problem(s)"
    assert r.stdout.splitlines()[1].startswith("PROBLEM on-base: on main, which must not be renamed")


# requirement: change-workflow / A new branch is checked for collisions before it is made
def test_preflight_stacked_create_on_the_parent_passes(work: Path):
    _stacked_parent(work)
    _git(work, "checkout", "-q", "feature/parent")
    r = _run(work, "preflight", "--branch", "child", "--base", "main", "--pr-base", "feature/parent")
    assert r.returncode == 0, r.stdout
    assert _first(r) == "OK preflight create: child"


def test_preflight_stacked_rename_counts_against_the_parent(work: Path):
    # A fresh worktree branch cut from origin/feature/parent holds the parent's commit, which is
    # not on main; counted against the parent it has nothing to lose.
    _stacked_parent(work)
    _git(work, "checkout", "-q", "-b", "worktree-abc", "origin/feature/parent")
    r = _run(work, "preflight", "--branch", "child", "--base", "main", "--pr-base", "feature/parent")
    assert r.returncode == 0, r.stdout
    assert _first(r) == "OK preflight rename: child"


def test_preflight_unstacked_on_another_pushed_branch_is_a_plain_rename(work: Path):
    # Without --pr-base, feature/parent is just another branch: no `on-base` problem, and its
    # commit not on main is a commit to lose.
    _stacked_parent(work)
    _git(work, "checkout", "-q", "feature/parent")
    r = _run(work, "preflight", "--branch", "child", "--base", "main")
    assert r.returncode == 1
    assert "PROBLEM commits-to-lose: HEAD has 1 commit(s) not on origin/main" in r.stdout
    assert "PROBLEM on-base" not in r.stdout


def test_preflight_pr_base_on_an_unknown_remote_is_unchecked(work: Path):
    # The parent's upstream names a remote that does not exist: the remote cannot be asked.
    _git(work, "checkout", "-q", "-b", "feature/parent")
    _git(work, "push", "-q", "-u", "origin", "feature/parent")
    _git(work, "config", "branch.feature/parent.remote", "ghost")
    r = _run(work, "preflight", "--branch", "child", "--base", "main", "--pr-base", "feature/parent")
    assert r.returncode == 2, r.stdout
    assert _first(r).startswith("UNCHECKED remote: 'git ls-remote ghost refs/heads/feature/parent' failed")


def test_preflight_pr_base_with_the_remote_unreachable_is_unchecked(work: Path):
    _stacked_parent(work)
    _git(work, "checkout", "-q", "feature/parent")
    _unreachable(work)
    r = _run(work, "preflight", "--branch", "child", "--base", "main", "--pr-base", "feature/parent")
    assert r.returncode == 2, r.stdout
    assert all(line.startswith("UNCHECKED remote:") for line in r.stdout.splitlines())


def test_preflight_pr_base_in_a_single_branch_clone_passes(tmp_path: Path, work: Path):
    # The parent's upstream is set by `push -u`, but the clone's refspec maps only main, so
    # `feature/parent@{u}` resolves to nothing; the configured upstream still counts.
    clone = _single_branch_clone(tmp_path)
    _git(clone, "checkout", "-q", "-b", "feature/parent")
    _commit(clone, "parent work")
    _git(clone, "push", "-q", "-u", "origin", "feature/parent")
    assert _git(clone, "rev-parse", "--verify", "--quiet", "feature/parent@{u}", check=False).returncode != 0
    r = _run(clone, "preflight", "--branch", "child", "--base", "main", "--pr-base", "feature/parent")
    assert r.returncode == 0, r.stdout


def test_preflight_rename_with_a_base_the_remote_lacks_is_unchecked(work: Path):
    # ls-remote answers, but the fetch of the base fails: the commit count could not be taken.
    _git(work, "checkout", "-q", "-b", "worktree-abc")
    r = _run(work, "preflight", "--branch", "feature/x", "--base", "no-such-base")
    assert r.returncode == 2, r.stdout
    assert _first(r).startswith("UNCHECKED remote: 'git fetch origin no-such-base' failed")


# ---------------------------------------------------------------- pushed


# requirement: change-workflow / A push is verified against the remote
def test_pushed_passes_after_a_real_push_of_a_slash_branch(work: Path):
    _git(work, "checkout", "-q", "-b", "feature/a-b")
    _commit(work)
    _git(work, "push", "-q", "-u", "origin", "feature/a-b")
    head = _git(work, "rev-parse", "HEAD").stdout.strip()
    r = _run(work, "pushed", "--branch", "feature/a-b")
    assert r.returncode == 0, r.stdout
    assert _first(r) == f"OK pushed: feature/a-b at {head}"


# requirement: change-workflow / A push is verified against the remote
def test_pushed_fails_when_the_commit_did_not_reach_the_remote(work: Path):
    _commit(work)
    r = _run(work, "pushed", "--branch", "main")
    assert r.returncode == 1
    assert _first(r) == "FAIL push not verified: 2 problem(s)"
    assert "PROBLEM remote-differs:" in r.stdout
    assert "PROBLEM upstream-differs:" in r.stdout


# requirement: change-workflow / A push is verified against the remote
def test_pushed_fails_on_the_wrong_branch(work: Path):
    r = _run(work, "pushed", "--branch", "feature/x")
    assert r.returncode == 1
    assert "push not verified" in _first(r)
    assert "PROBLEM wrong-branch: on main, expected feature/x" in r.stdout


def test_pushed_fails_on_a_detached_head(work: Path):
    _git(work, "checkout", "-q", "--detach")
    r = _run(work, "pushed", "--branch", "main")
    assert r.returncode == 1
    assert "PROBLEM detached: HEAD is detached, expected branch main" in r.stdout


def test_pushed_fails_with_no_upstream_and_no_remote_branch(work: Path):
    _git(work, "checkout", "-q", "-b", "feature/x")
    r = _run(work, "pushed", "--branch", "feature/x")
    assert r.returncode == 1
    lines = r.stdout.splitlines()[1:]
    assert lines == [
        "PROBLEM remote-missing: origin has no refs/heads/feature/x",
        "PROBLEM no-upstream: no upstream is configured for feature/x",
    ]


def test_pushed_fails_when_only_the_upstream_is_unset(work: Path):
    _git(work, "branch", "--unset-upstream")
    r = _run(work, "pushed", "--branch", "main")
    assert r.returncode == 1
    assert r.stdout.splitlines()[1:] == ["PROBLEM no-upstream: no upstream is configured for main"]


# requirement: change-workflow / A push is verified against the remote
def test_pushed_passes_in_a_single_branch_clone(tmp_path: Path, work: Path):
    # No refs/remotes/origin/feat is ever made here, so `@{u}` resolves to nothing after a correct
    # `push -u`; the configured upstream and ls-remote decide.
    clone = _single_branch_clone(tmp_path)
    _git(clone, "checkout", "-q", "-b", "feat")
    _commit(clone)
    _git(clone, "push", "-q", "-u", "origin", "feat")
    assert _git(clone, "rev-parse", "--verify", "--quiet", "@{u}", check=False).returncode != 0
    r = _run(clone, "pushed", "--branch", "feat")
    assert r.returncode == 0, r.stdout


def test_pushed_fails_when_the_upstream_is_another_branch(work: Path):
    # A branch cut from origin/main tracks main; a bare push from it would not go to feature/x.
    _git(work, "checkout", "-q", "-b", "feature/x", "origin/main")
    _git(work, "push", "-q", "origin", "feature/x")
    r = _run(work, "pushed", "--branch", "feature/x")
    assert r.returncode == 1
    assert r.stdout.splitlines()[1:] == [
        "PROBLEM upstream-elsewhere: feature/x tracks refs/heads/main on origin, expected refs/heads/feature/x on origin",
    ]


def test_pushed_on_a_branch_with_no_commit_is_unchecked(work: Path):
    _git(work, "checkout", "-q", "--orphan", "fresh")
    r = _run(work, "pushed", "--branch", "fresh")
    assert r.returncode == 2
    assert _first(r) == "UNCHECKED push not verified: head: HEAD names no commit"


def test_pushed_a_problem_wins_over_an_unanswered_remote(work: Path):
    _unreachable(work)
    r = _run(work, "pushed", "--branch", "feature/x")
    assert r.returncode == 1
    assert _first(r) == "FAIL push not verified: 2 problem(s)"
    assert "PROBLEM wrong-branch: on main, expected feature/x" in r.stdout
    assert any(line.startswith("UNCHECKED remote:") for line in r.stdout.splitlines())


# requirement: change-workflow / A push is verified against the remote
def test_pushed_unreachable_remote_is_unchecked_not_a_pass(work: Path):
    _unreachable(work)
    r = _run(work, "pushed", "--branch", "main")
    assert r.returncode == 2
    assert _first(r).startswith("UNCHECKED push not verified: remote:")


def test_pushed_outside_a_repo_is_unchecked(tmp_path: Path):
    r = _run(tmp_path, "pushed", "--branch", "main")
    assert r.returncode == 2
    assert _first(r).startswith("UNCHECKED push not verified: repo:")


# ---------------------------------------------------------------- trailers

_ATTRIBUTION = "Co-Authored-By: Someone <someone@example.com>"


# requirement: change-workflow / Measurement trailers are checked before a push
def test_trailers_none_written_none_parsed_passes(work: Path):
    r = _run(work, "trailers")
    assert r.returncode == 0
    assert _first(r) == "OK trailers: 0 written as 'Measured-by:', 0 parsed by git"


# requirement: change-workflow / Measurement trailers are checked before a push
def test_trailers_a_block_git_parses_passes(work: Path):
    _commit(work, "feat: x", "-m", f"Measured-by: cmd one — a claim\nMeasured-by: cmd two — b claim\n{_ATTRIBUTION}")
    r = _run(work, "trailers")
    assert r.returncode == 0, r.stdout
    assert _first(r) == "OK trailers: 2 written as 'Measured-by:', 2 parsed by git"


# requirement: change-workflow / Measurement trailers are checked before a push
def test_trailers_split_by_a_blank_line_fails(work: Path):
    _commit(work, "feat: x", "-m", "Measured-by: cmd one — a claim\nMeasured-by: cmd two — b", "-m", _ATTRIBUTION)
    r = _run(work, "trailers")
    assert r.returncode == 1
    assert _first(r) == "FAIL trailers: 2 written as 'Measured-by:', 0 parsed by git"
    assert r.stdout.splitlines()[1].startswith("PROBLEM trailers:")


# requirement: change-workflow / Measurement trailers are checked before a push
def test_trailers_an_empty_value_fails(work: Path):
    # git parses `Measured-by:` with nothing after it, but it names no command.
    _commit(work, "feat: x", "-m", f"Measured-by:\n{_ATTRIBUTION}")
    r = _run(work, "trailers")
    assert r.returncode == 1, r.stdout
    assert _first(r) == "FAIL trailers: 1 written as 'Measured-by:', 0 parsed by git"


def test_trailers_a_bare_line_in_the_block_fails(work: Path):
    _commit(work, "feat: x", "-m", "Measured-by: cmd — a claim\nCloses #199")
    r = _run(work, "trailers")
    assert r.returncode == 1
    assert _first(r) == "FAIL trailers: 1 written as 'Measured-by:', 0 parsed by git"


def test_trailers_reads_the_rev_given_and_works_detached(work: Path):
    _commit(work, "feat: x", "-m", "Measured-by: cmd — a claim\nCloses #199")
    _commit(work, "feat: y")
    _git(work, "checkout", "-q", "--detach")
    assert _run(work, "trailers").returncode == 0
    r = _run(work, "trailers", "--rev", "HEAD~1")
    assert r.returncode == 1
    assert "1 written" in _first(r)


def test_trailers_on_a_rev_that_names_no_commit_is_unchecked(work: Path):
    r = _run(work, "trailers", "--rev", "no-such-ref")
    assert r.returncode == 2
    assert _first(r).startswith("UNCHECKED rev:")
