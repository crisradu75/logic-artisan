"""multi-spec's Phase 2 maps `ship_check.py preflight`'s answer to one action, and the map holds.

Phase 2 finds an existing `docs/propose-<slug>` branch through `ship_check.py preflight`, which
compares exact ref names (`git ls-remote --heads origin <name>` also matched a longer branch ending
in the name). The action for each answer lives in the prose of step 2. These tests run preflight
on a real repo for each case, pick the step-2 bullet the prose says applies to that answer, and
check the bullet's action, then carry the action out where it matters:

- a stale `refs/remotes/origin/<branch>` left by a deleted branch is not a branch to resume: the
  bullet prunes and asks again, and the second answer creates a fresh branch;
- a branch only the local repo has is resumed, and the resume push gives it the upstream the
  persist step's bare pushes need.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[4]
_PHASES = _ROOT / ".claude" / "plugins" / "cla" / "skills" / "multi-spec" / "references" / "phases.md"
_SHIP = _ROOT / ".claude" / "plugins" / "cla" / "skills" / "_shared" / "scripts" / "ship_check.py"
_BRANCH = "docs/propose-x"
_COLLISIONS = {"local-branch", "remote-tracking", "remote-branch"}


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=check)


def _ship(work: Path, *args: str) -> tuple[int, set[str]]:
    r = subprocess.run([sys.executable, str(_SHIP), *args, "--root", str(work)], cwd=_ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    kinds = {m.group(1) for m in re.finditer(r"^PROBLEM ([\w-]+):", r.stdout, re.M)}
    return r.returncode, kinds


def _preflight(work: Path) -> tuple[int, set[str]]:
    return _ship(work, "preflight", "--branch", _BRANCH, "--base", "main")


def _step_2() -> str:
    text = _PHASES.read_text(encoding="utf-8")
    match = re.search(r"^## Phase 2 .*?^(2\. .*?)^3\. ", text, re.S | re.M)
    assert match, "phases.md: no step 2 under Phase 2"
    return match.group(1)


def _bullets() -> list[str]:
    return [line.strip()[2:] for line in _step_2().splitlines() if line.strip().startswith("- Exit ")]


def _bullet_for(code: int, kinds: set[str]) -> str:
    """The step-2 bullet the prose says applies to preflight's answer."""
    found = kinds & _COLLISIONS
    if code == 0:
        want = ["Exit 0 "]
    elif code == 2:
        want = ["Exit 2 "]
    elif found & {"local-branch", "remote-branch"}:
        want = ["Exit 1 with a `PROBLEM local-branch` or `PROBLEM remote-branch` line"]
    elif found == {"remote-tracking"}:
        want = ["Exit 1 with `PROBLEM remote-tracking` as the only one of those three lines"]
    else:
        want = ["Exit 1 with none of those three lines"]
    hits = [b for b in _bullets() if any(b.startswith(w) for w in want)]
    assert len(hits) == 1, f"phase 2 step 2 has {len(hits)} bullets for exit {code} {sorted(kinds)}: {_bullets()}"
    return hits[0]


@pytest.fixture
def work(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", "origin.git")
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "T")
    (work / "README.md").write_text("# tmp\n", encoding="utf-8")
    _git(work, "add", "README.md")
    _git(work, "commit", "-q", "-m", "initial")
    _git(work, "remote", "add", "origin", "../origin.git")
    _git(work, "push", "-q", "-u", "origin", "main")
    return work


def test_step_2_has_one_bullet_per_answer():
    assert _bullets() == [
        "Exit 0 → the branch exists nowhere: `git checkout -b docs/propose-<batch-slug>`.",
        "Exit 1 with a `PROBLEM local-branch` or `PROBLEM remote-branch` line → the branch exists: resume. "
        "When only the remote has it, `git fetch origin docs/propose-<batch-slug>` first; then "
        "`git checkout docs/propose-<batch-slug>`, then the resume push.",
        "Exit 1 with `PROBLEM remote-tracking` as the only one of those three lines → a stale ref left by "
        "a deleted branch: `git fetch --prune origin`, then run preflight again.",
        "Exit 1 with none of those three lines (for example, not on `<base-branch>`) → stop and report.",
        "Exit 2 → it could not ask the remote: stop and report, since a new branch could then fork an existing one.",
    ]
    assert "ship_check.py\" preflight --branch docs/propose-<batch-slug> --base <base-branch>" in _step_2()
    assert "ls-remote --exit-code --heads" not in _PHASES.read_text(encoding="utf-8")


def test_a_stale_remote_tracking_ref_is_pruned_not_resumed(work: Path):
    # The branch was pushed, then deleted on origin; the local remote-tracking ref was never pruned.
    _git(work, "push", "-q", "origin", f"main:refs/heads/{_BRANCH}")
    _git(work, "fetch", "-q", "origin")
    _git(work.parent / "origin.git", "update-ref", "-d", f"refs/heads/{_BRANCH}")
    code, kinds = _preflight(work)
    assert (code, kinds) == (1, {"remote-tracking"})
    bullet = _bullet_for(code, kinds)
    assert "`git fetch --prune origin`, then run preflight again" in bullet and "resume" not in bullet
    _git(work, "fetch", "-q", "--prune", "origin")
    code, kinds = _preflight(work)
    assert (code, kinds) == (0, set())
    assert "`git checkout -b docs/propose-<batch-slug>`" in _bullet_for(code, kinds)


def test_a_branch_only_the_remote_has_is_resumed_from_it(tmp_path: Path, work: Path):
    other = tmp_path / "other"
    _git(tmp_path, "clone", "-q", "origin.git", "other")
    _git(other, "push", "-q", "origin", f"main:refs/heads/{_BRANCH}")
    code, kinds = _preflight(work)
    assert (code, kinds) == (1, {"remote-branch"})
    bullet = _bullet_for(code, kinds)
    assert "resume" in bullet and "`git fetch origin docs/propose-<batch-slug>` first" in bullet
    _git(work, "fetch", "-q", "origin", _BRANCH)
    _git(work, "checkout", "-q", _BRANCH)
    _git(work, "push", "-q", "-u", "origin", _BRANCH)
    assert _ship(work, "pushed", "--branch", _BRANCH) == (0, set())


def test_a_branch_only_the_local_repo_has_gets_its_upstream_from_the_resume_push(work: Path):
    _git(work, "branch", _BRANCH)
    code, kinds = _preflight(work)
    assert (code, kinds) == (1, {"local-branch"})
    bullet = _bullet_for(code, kinds)
    assert "resume" in bullet and bullet.endswith("then the resume push.")
    _git(work, "checkout", "-q", _BRANCH)
    # Without the resume push: no upstream, so a later bare `git push` has nowhere to go.
    assert _ship(work, "pushed", "--branch", _BRANCH)[1] >= {"no-upstream"}
    push = re.search(r"\*\*The resume push\.\*\*.*", _step_2()).group(0)
    assert "`git push -u origin docs/propose-<batch-slug>`" in push
    assert "ship_check.py\" pushed --branch docs/propose-<batch-slug>`. Any exit but 0 → stop and report." in push
    _git(work, "push", "-q", "-u", "origin", _BRANCH)
    assert _ship(work, "pushed", "--branch", _BRANCH) == (0, set())


def test_step_1_on_the_branch_runs_the_resume_push_too():
    text = _PHASES.read_text(encoding="utf-8")
    assert "already on `docs/propose-<batch-slug>` → this is a resume: run the resume push (step 2)" in text


def test_off_the_base_branch_with_no_collision_stops(work: Path):
    _git(work, "checkout", "-q", "-b", "elsewhere")
    (work / "f.txt").write_text("x\n", encoding="utf-8")
    _git(work, "add", "f.txt")
    _git(work, "commit", "-q", "-m", "x")
    code, kinds = _preflight(work)
    assert code == 1 and kinds and not kinds & _COLLISIONS
    assert _bullet_for(code, kinds).endswith("→ stop and report.")


def test_an_unreachable_remote_stops(work: Path):
    _git(work, "remote", "set-url", "origin", "../no-such.git")
    code, kinds = _preflight(work)
    assert (code, kinds) == (2, set())
    assert "stop and report" in _bullet_for(code, kinds)
