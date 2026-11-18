"""chain_check.py tests: real repos with a local bare `origin`, a fake `gh` on PATH, one test per exit path.

Layout: `<tmp>/origin.git` (bare) and `<tmp>/work`, a checkout on `feature/a` with one commit past
`main`, both pushed, `origin` set to the RELATIVE url `../origin.git` so a copy of the cached
template pushes to its own copy of the remote. The run notes sit in `work/cla.io/retro/`,
untracked, as a chain keeps them: the clean-tree check must not count them.

The fake `gh` is a small script in `<tmp>/bin`, first on PATH. It logs its arguments and prints
the canned response the test wrote; it never reaches the network, and the real `gh` is shadowed.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).resolve().parents[4]
    / ".claude" / "plugins" / "cla" / "skills" / "_shared" / "scripts" / "chain_check.py"
)
_LITE = "id | status | branch | pr_number | head_sha | deferred | review | merge_commit"
_PR = "change | branch | pr_number | head_sha | status | merge_commit | notes"

_BEFORE = "change-chains / A chain checks a pull request's head before it merges it"
_AFTER = "change-chains / A chain counts a merge only when the host reports it merged"
_FIX = "change-chains / A chain's own fix becomes the recorded head only once it is committed and pushed"
_RESUME = "change-chains / A resumed chain acts only on its own pull request at the recorded head"
_DEPS = "small-change-chains / A small change runs only after the changes it depends on merged"


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
    _git(work, "checkout", "-q", "-b", "feature/a")
    (work / "a.txt").write_text("a\n", encoding="utf-8")
    _git(work, "add", "a.txt")
    _git(work, "commit", "-q", "-m", "a")
    _git(work, "push", "-q", "-u", "origin", "feature/a")


class Chain:
    """One test's repo, notes file and fake gh."""

    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.work = tmp / "work"
        self.notes = self.work / "cla.io" / "retro" / "multi-lite-run-notes-2026-11-18.md"
        self.bin = tmp / "bin"
        self.bin.mkdir()
        self.head = _git(self.work, "rev-parse", "HEAD").stdout.strip()
        self.write_notes([("a", "open", "feature/a", "7", self.head, "0", "clean", "")])
        self.gh_pr()

    # -- the run notes

    def write_notes(self, rows, header: str = _LITE, raw: str | None = None, to: Path | None = None) -> None:
        target = to or self.notes
        target.parent.mkdir(parents=True, exist_ok=True)
        if raw is None:
            lines = ["docs/decisions/x.md", "policy: merge-each-clean", "", f"| {header} |",
                     "|" + "---|" * len(header.split("|"))]
            lines += ["| " + " | ".join(r) + " |" for r in rows]
            raw = "\n".join(lines) + "\n\n## Deferred findings\n"
        target.write_text(raw, encoding="utf-8")

    # -- the fake gh

    def gh(self, stdout: str = "", stderr: str = "", code: int = 0) -> None:
        (self.bin / "gh-response.json").write_text(
            json.dumps({"stdout": stdout, "stderr": stderr, "code": code}), encoding="utf-8",
        )
        stub = self.bin / "gh"
        stub.write_text(
            f"#!{sys.executable}\n"
            "import json, pathlib, sys\n"
            "here = pathlib.Path(__file__).resolve().parent\n"
            "with open(here / 'gh-args.log', 'a', encoding='utf-8') as log:\n"
            "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "r = json.loads((here / 'gh-response.json').read_text(encoding='utf-8'))\n"
            "r = r['by_number'][sys.argv[3]] if 'by_number' in r else r\n"
            "sys.stdout.write(r['stdout']); sys.stderr.write(r['stderr']); sys.exit(r['code'])\n",
            encoding="utf-8",
        )
        stub.chmod(0o755)
        (self.bin / "gh.cmd").write_text(f'@"{sys.executable}" "%~dp0gh" %*\r\n', encoding="utf-8")

    def gh_pr(self, **fields) -> None:
        pr = {
            "number": 7, "state": "OPEN", "headRefOid": self.head, "headRefName": "feature/a",
            "baseRefName": "main", "isCrossRepository": False, "mergeCommit": None, "autoMergeRequest": None,
        }
        pr.update(fields)
        self.gh(json.dumps(pr))

    def gh_prs(self, prs: dict[int, dict]) -> None:
        """Answer `gh pr view <n>` per number: an old chain's PR and this one's can both exist."""
        self.gh()
        base = {"headRefName": "feature/a", "baseRefName": "main", "isCrossRepository": False,
                "mergeCommit": None, "autoMergeRequest": None}
        answers = {str(n): {"stdout": json.dumps({**base, "number": n, **pr}), "stderr": "", "code": 0}
                   for n, pr in prs.items()}
        (self.bin / "gh-response.json").write_text(json.dumps({"by_number": answers}), encoding="utf-8")

    def gh_calls(self) -> list[list[str]]:
        log = self.bin / "gh-args.log"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]

    # -- running the script

    def run(self, *args: str, path: str | None = None) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["PATH"] = path if path is not None else str(self.bin) + os.pathsep + env.get("PATH", "")
        # A neutral cwd: the script must check --root, not wherever it was started.
        return subprocess.run(
            [sys.executable, str(_SCRIPT), *args, "--root", str(self.work)],
            cwd=Path(__file__).parent, capture_output=True, text=True, encoding="utf-8",
            errors="replace", env=env,
        )

    def check(self, cmd: str, *extra: str, item: str = "a", **kw) -> subprocess.CompletedProcess[str]:
        if cmd == "deps":
            return self.run(cmd, "--notes", str(self.notes), *extra, **kw)
        base = ("--base", "main") if cmd in ("before-merge", "after-merge", "resume") else ()
        return self.run(cmd, "--notes", str(self.notes), "--id", item, *base, *extra, **kw)

    def commit(self, name: str = "b.txt", msg: str = "b") -> str:
        (self.work / name).write_text(msg + "\n", encoding="utf-8")
        _git(self.work, "add", name)
        _git(self.work, "commit", "-q", "-m", msg)
        return _git(self.work, "rev-parse", "HEAD").stdout.strip()

    def unreachable(self) -> None:
        _git(self.work, "remote", "set-url", "origin", "../no-such-remote.git")


@pytest.fixture
def chain(tmp_path: Path, cached_git_repo) -> Chain:
    cached_git_repo("_shared/chain_check", _build, tmp_path)
    return Chain(tmp_path)


def _first(r: subprocess.CompletedProcess[str]) -> str:
    return r.stdout.splitlines()[0]


def _problems(r: subprocess.CompletedProcess[str]) -> list[str]:
    return [line.split(":", 1)[0] for line in r.stdout.splitlines() if line.startswith("PROBLEM ")]


def _path_without_gh(tmp: Path) -> str:
    """A PATH that still finds git but finds no gh."""
    git_dir = os.path.dirname(shutil.which("git") or "")
    if git_dir and shutil.which("gh", path=git_dir) is None:
        return git_dir
    only_git = tmp / "only-git"
    only_git.mkdir()
    try:
        (only_git / Path(shutil.which("git")).name).symlink_to(shutil.which("git"))
    except OSError:
        pytest.skip("git and gh share a directory and symlinks are not permitted here")
    return str(only_git)


# ---------------------------------------------------------------- before-merge


# requirement: change-chains / A chain checks a pull request's head before it merges it
def test_before_merge_passes_on_the_recorded_head(chain: Chain):
    r = chain.check("before-merge")
    assert r.returncode == 0, r.stdout
    assert _first(r) == f"OK before-merge: #7 open on feature/a at {chain.head}, checkout clean"
    # The PR number comes from the row, never from the caller.
    assert chain.gh_calls()[0][:3] == ["pr", "view", "7"]


def test_before_merge_reads_a_multi_pr_row_with_backticks_and_a_hash(chain: Chain):
    chain.write_notes([("`add-x`", "`feature/a`", "#7", f"`{chain.head}`", "enforced", "", "")], header=_PR)
    r = chain.check("before-merge", item="add-x")
    assert r.returncode == 0, r.stdout


# requirement: change-chains / A chain checks a pull request's head before it merges it
def test_before_merge_fails_on_a_head_moved_on_the_pr(chain: Chain):
    chain.gh_pr(headRefOid="b" * 40)
    r = chain.check("before-merge")
    assert r.returncode == 1
    assert _first(r) == "FAIL before-merge: head moved"
    assert _problems(r) == ["PROBLEM pr-head"]


# requirement: change-chains / A chain checks a pull request's head before it merges it
def test_before_merge_fails_on_a_head_moved_on_the_remote(chain: Chain):
    chain.commit()
    _git(chain.work, "push", "-q", "origin", "feature/a")
    _git(chain.work, "reset", "-q", "--hard", chain.head)
    r = chain.check("before-merge")
    assert r.returncode == 1
    assert _first(r) == "FAIL before-merge: head moved"
    assert _problems(r) == ["PROBLEM remote-head"]


def test_before_merge_fails_when_the_remote_branch_is_gone(chain: Chain):
    _git(chain.work, "push", "-q", "origin", "--delete", "feature/a")
    r = chain.check("before-merge")
    assert r.returncode == 1
    assert "PROBLEM remote-head: origin has no refs/heads/feature/a" in r.stdout


# requirement: change-chains / A chain checks a pull request's head before it merges it
def test_before_merge_fails_on_a_head_moved_locally(chain: Chain):
    chain.commit()
    r = chain.check("before-merge")
    assert r.returncode == 1
    assert _first(r) == "FAIL before-merge: local head mismatch"
    assert _problems(r) == ["PROBLEM local-head"]


# requirement: change-chains / A chain checks a pull request's head before it merges it
def test_before_merge_fails_on_a_dirty_tree_but_not_on_the_run_notes(chain: Chain):
    r = chain.check("before-merge")
    assert r.returncode == 0, r.stdout  # the untracked run notes alone are not dirt
    (chain.work / "README.md").write_text("# changed\n", encoding="utf-8")
    r = chain.check("before-merge")
    assert r.returncode == 1
    assert _first(r) == "FAIL before-merge: uncommitted changes"
    assert "README.md" in r.stdout


@pytest.mark.parametrize("state", ["CLOSED", "MERGED"])
# requirement: change-chains / A chain checks a pull request's head before it merges it
def test_before_merge_fails_on_a_pr_that_is_not_open(chain: Chain, state: str):
    chain.gh_pr(state=state)
    r = chain.check("before-merge")
    assert r.returncode == 1
    assert _first(r) == f"FAIL before-merge: not open (state {state})"


@pytest.mark.parametrize("fields", [{"headRefName": "feature/other"}, {"isCrossRepository": True}])
# requirement: change-chains / A chain checks a pull request's head before it merges it
def test_before_merge_refuses_a_pr_this_chain_did_not_open(chain: Chain, fields: dict):
    chain.gh_pr(**fields)
    r = chain.check("before-merge")
    assert r.returncode == 1
    assert _first(r) == "FAIL before-merge: not opened by this chain"


def test_before_merge_fails_on_another_base(chain: Chain):
    chain.gh_pr(baseRefName="develop")
    r = chain.check("before-merge")
    assert r.returncode == 1
    assert _first(r) == "FAIL before-merge: wrong base (develop)"


# requirement: change-chains / A chain checks a pull request's head before it merges it
def test_before_merge_with_no_recorded_head_is_unverifiable(chain: Chain):
    chain.write_notes([("a", "open", "feature/a", "7", "", "0", "clean", "")])
    r = chain.check("before-merge")
    assert r.returncode == 1
    assert _first(r) == "FAIL before-merge: head unverifiable (ledger lost)"


def test_before_merge_names_the_first_reason_and_lists_every_problem(chain: Chain):
    chain.gh_pr(headRefOid="c" * 40)
    chain.commit()
    (chain.work / "README.md").write_text("# changed\n", encoding="utf-8")
    r = chain.check("before-merge")
    assert r.returncode == 1
    assert _first(r) == "FAIL before-merge: head moved"
    assert _problems(r) == ["PROBLEM pr-head", "PROBLEM local-head", "PROBLEM dirty"]


def test_before_merge_fails_on_a_recorded_pr_gh_cannot_find(chain: Chain):
    chain.gh(stderr="GraphQL: Could not resolve to a PullRequest with the number of 7. (repository.pullRequest)\n", code=1)
    r = chain.check("before-merge")
    assert r.returncode == 1
    assert _first(r) == "FAIL before-merge: recorded PR not found"


# requirement: change-chains / A chain checks a pull request's head before it merges it
def test_before_merge_cannot_check_when_gh_fails(chain: Chain):
    chain.gh(stderr="HTTP 401: Bad credentials\n", code=1)
    r = chain.check("before-merge")
    assert r.returncode == 2
    assert _first(r) == "UNCHECKED gh: 'gh pr view 7' failed: HTTP 401: Bad credentials"


# requirement: change-chains / A chain checks a pull request's head before it merges it
def test_before_merge_cannot_check_without_gh(chain: Chain):
    r = chain.check("before-merge", path=_path_without_gh(chain.tmp))
    assert r.returncode == 2
    assert _first(r) == "UNCHECKED gh: gh was not found on PATH"


def test_a_found_problem_wins_over_gh_failing(chain: Chain):
    chain.gh(stderr="HTTP 401: Bad credentials\n", code=1)
    (chain.work / "README.md").write_text("# changed\n", encoding="utf-8")
    r = chain.check("before-merge")
    assert r.returncode == 1
    assert _first(r) == "FAIL before-merge: uncommitted changes"
    assert "UNCHECKED gh:" in r.stdout


@pytest.mark.parametrize("stdout", ["not json", json.dumps({"state": "OPEN"}),
                                    json.dumps({"number": 7, "state": "WEIRD", "headRefOid": "a" * 40,
                                                "headRefName": "feature/a", "baseRefName": "main"}),
                                    json.dumps({"number": 8, "state": "OPEN", "headRefOid": "a" * 40,
                                                "headRefName": "feature/a", "baseRefName": "main"})])
def test_before_merge_cannot_check_unreadable_gh_output(chain: Chain, stdout: str):
    chain.gh(stdout)
    r = chain.check("before-merge")
    assert r.returncode == 2
    assert _first(r).startswith("UNCHECKED gh:")


def test_before_merge_cannot_check_an_unreachable_remote(chain: Chain):
    chain.unreachable()
    r = chain.check("before-merge")
    assert r.returncode == 2
    assert _first(r).startswith("UNCHECKED remote:")


# ---------------------------------------------------------------- the run notes


@pytest.mark.parametrize("row,expected", [
    (("a", "open", "feature/a", "7", "abc1234", "0", "clean", ""), "is not a full commit id"),
    (("a", "open", "feature/a", "seven", "HEAD", "0", "clean", ""), "is not a number"),
    (("a", "open", "feature/a", "", "HEAD", "0", "clean", ""), "records no pr_number"),
    (("a", "open", "", "7", "HEAD", "0", "clean", ""), "records no branch"),
    (("a", "open", "feature/a", "7", "HEAD", "0", "clean"), "has 7 cells, the header has 8"),
    (("b", "open", "feature/a", "7", "HEAD", "0", "clean", ""), "no row for 'a'"),
])
# requirement: change-chains / A chain checks a pull request's head before it merges it
def test_a_malformed_notes_row_cannot_be_checked(chain: Chain, row, expected: str):
    chain.write_notes([tuple(chain.head if c == "HEAD" else c for c in row)])
    for cmd in ("before-merge", "after-merge", "fix-pushed", "resume"):
        r = chain.check(cmd)
        assert r.returncode == 2, (cmd, r.stdout)
        assert _first(r).startswith("UNCHECKED notes:") and expected in _first(r), (cmd, r.stdout)


def test_two_rows_for_one_item_cannot_be_checked(chain: Chain):
    row = ("a", "open", "feature/a", "7", chain.head, "0", "clean", "")
    chain.write_notes([row, row])
    r = chain.check("before-merge")
    assert r.returncode == 2
    assert "has 2 rows for 'a'" in _first(r)


@pytest.mark.parametrize("raw", [None, "no table here\n", "| id | status |\n|---|---|\n| a | open |\n"])
def test_notes_without_the_ledger_table_cannot_be_checked(chain: Chain, raw: str | None):
    if raw is None:
        chain.notes.unlink()
    else:
        chain.write_notes([], raw=raw)
    r = chain.check("before-merge")
    assert r.returncode == 2
    assert _first(r).startswith("UNCHECKED notes:")


# ---------------------------------------------------------------- after-merge


# requirement: change-chains / A chain counts a merge only when the host reports it merged
def test_after_merge_passes_on_merged_and_names_the_merge_commit(chain: Chain):
    chain.gh_pr(state="MERGED", mergeCommit={"oid": "d" * 40})
    r = chain.check("after-merge")
    assert r.returncode == 0, r.stdout
    assert _first(r) == f"OK after-merge: #7 merged as {'d' * 40}"


# requirement: change-chains / A chain counts a merge only when the host reports it merged
def test_after_merge_reports_a_queued_merge(chain: Chain):
    chain.gh_pr(autoMergeRequest={"enabledAt": "2026-11-18T00:00:00Z"})
    r = chain.check("after-merge")
    assert r.returncode == 1
    assert _first(r) == "FAIL after-merge: queued: merges later outside this run"


# requirement: change-chains / A chain counts a merge only when the host reports it merged
def test_after_merge_fails_on_a_pr_still_open(chain: Chain):
    r = chain.check("after-merge")
    assert r.returncode == 1
    assert _first(r) == "FAIL after-merge: merge not confirmed (state OPEN)"


def test_after_merge_cannot_check_when_gh_fails(chain: Chain):
    chain.gh(stderr="HTTP 502\n", code=1)
    r = chain.check("after-merge")
    assert r.returncode == 2
    assert _first(r).startswith("UNCHECKED gh:")


# ---------------------------------------------------------------- fix-pushed


# requirement: change-chains / A chain's own fix becomes the recorded head only once it is committed and pushed
def test_fix_pushed_passes_and_names_the_new_head(chain: Chain):
    new = chain.commit()
    _git(chain.work, "push", "-q", "origin", "feature/a")
    r = chain.check("fix-pushed")
    assert r.returncode == 0, r.stdout
    assert _first(r) == f"OK fix-pushed: new head_sha {new}"
    assert chain.gh_calls() == []  # it needs no gh


# requirement: change-chains / A chain's own fix becomes the recorded head only once it is committed and pushed
def test_fix_pushed_fails_when_no_commit_was_made(chain: Chain):
    r = chain.check("fix-pushed")
    assert r.returncode == 1
    assert _first(r) == "FAIL fix-pushed: fix not committed"
    assert _problems(r) == ["PROBLEM no-commit"]


# requirement: change-chains / A chain's own fix becomes the recorded head only once it is committed and pushed
def test_fix_pushed_fails_when_part_of_the_fix_is_not_committed(chain: Chain):
    chain.commit()
    _git(chain.work, "push", "-q", "origin", "feature/a")
    (chain.work / "README.md").write_text("# half the fix\n", encoding="utf-8")
    r = chain.check("fix-pushed")
    assert r.returncode == 1
    assert _first(r) == "FAIL fix-pushed: fix not committed"
    assert _problems(r) == ["PROBLEM dirty"]


# requirement: change-chains / A chain's own fix becomes the recorded head only once it is committed and pushed
def test_fix_pushed_fails_when_the_commit_was_not_pushed(chain: Chain):
    chain.commit()
    r = chain.check("fix-pushed")
    assert r.returncode == 1
    assert _first(r) == "FAIL fix-pushed: push not verified"
    assert _problems(r) == ["PROBLEM remote-differs"]


def test_fix_pushed_fails_when_the_remote_branch_is_gone(chain: Chain):
    chain.commit()
    _git(chain.work, "push", "-q", "origin", "--delete", "feature/a")
    r = chain.check("fix-pushed")
    assert r.returncode == 1
    assert _first(r) == "FAIL fix-pushed: push not verified"
    assert _problems(r) == ["PROBLEM remote-missing"]


def test_fix_pushed_needs_a_recorded_head(chain: Chain):
    chain.write_notes([("a", "open", "feature/a", "7", "", "", "", "")])
    r = chain.check("fix-pushed")
    assert r.returncode == 2
    assert "records no head_sha" in _first(r)


def test_fix_pushed_cannot_check_an_unreachable_remote_but_still_reports_no_commit(chain: Chain):
    chain.commit()
    chain.unreachable()
    r = chain.check("fix-pushed")
    assert r.returncode == 2
    assert _first(r).startswith("UNCHECKED remote:")
    _git(chain.work, "reset", "-q", "--hard", chain.head)
    r = chain.check("fix-pushed")
    assert r.returncode == 1
    assert _first(r) == "FAIL fix-pushed: fix not committed"


# ---------------------------------------------------------------- resume


# requirement: change-chains / A resumed chain acts only on its own pull request at the recorded head
def test_resume_passes_on_an_open_pr_at_the_recorded_head(chain: Chain):
    r = chain.check("resume")
    assert r.returncode == 0, r.stdout
    assert _first(r) == f"OK resume open: #7 at {chain.head}"


# requirement: change-chains / A resumed chain acts only on its own pull request at the recorded head
def test_resume_reports_a_merged_pr_with_its_merge_commit(chain: Chain):
    chain.gh_pr(state="MERGED", mergeCommit={"oid": "f" * 40})
    r = chain.check("resume")
    assert r.returncode == 0, r.stdout
    assert _first(r) == f"OK resume merged: #7 as {'f' * 40}"


# requirement: change-chains / A resumed chain acts only on its own pull request at the recorded head
def test_resume_never_passes_a_moved_head(chain: Chain):
    chain.gh_pr(headRefOid="b" * 40)
    r = chain.check("resume")
    assert r.returncode == 1
    assert _first(r) == "FAIL resume: head moved since review"


# requirement: change-chains / A resumed chain acts only on its own pull request at the recorded head
def test_resume_without_a_recorded_head_is_unverifiable(chain: Chain):
    chain.write_notes([("a", "open", "feature/a", "7", "", "", "", "")])
    r = chain.check("resume")
    assert r.returncode == 1
    assert _first(r) == "FAIL resume: head unverifiable (ledger lost)"


def test_resume_reports_a_closed_pr(chain: Chain):
    chain.gh_pr(state="CLOSED")
    r = chain.check("resume")
    assert r.returncode == 1
    assert _first(r) == "FAIL resume: PR closed without merging"


def test_resume_reports_a_recorded_pr_gh_cannot_find(chain: Chain):
    chain.gh(stderr="GraphQL: Could not resolve to a PullRequest with the number of 7.\n", code=1)
    r = chain.check("resume")
    assert r.returncode == 1
    assert _first(r) == "FAIL resume: recorded PR not found"


# requirement: change-chains / A resumed chain acts only on its own pull request at the recorded head
def test_resume_refuses_a_pr_this_chain_did_not_open_even_when_merged(chain: Chain):
    chain.gh_pr(state="MERGED", headRefName="feature/other", mergeCommit={"oid": "f" * 40})
    r = chain.check("resume")
    assert r.returncode == 1
    assert _first(r) == "FAIL resume: not opened by this chain"


def test_resume_cannot_check_without_gh(chain: Chain):
    r = chain.check("resume", path=_path_without_gh(chain.tmp))
    assert r.returncode == 2
    assert _first(r) == "UNCHECKED gh: gh was not found on PATH"


# ---------------------------------------------------------------- deps


@pytest.fixture
def merged(chain: Chain) -> tuple[Chain, str, str]:
    """`main` holds a merge of `feature/a`; `other` holds a commit `main` does not."""
    _git(chain.work, "checkout", "-q", "main")
    _git(chain.work, "merge", "-q", "--no-ff", "-m", "merge a", "feature/a")
    merge = _git(chain.work, "rev-parse", "HEAD").stdout.strip()
    _git(chain.work, "push", "-q", "origin", "main")
    _git(chain.work, "checkout", "-q", "-b", "other", f"{merge}~1")
    stray = chain.commit("c.txt", "stray")
    _git(chain.work, "checkout", "-q", "main")
    return chain, merge, stray


def _ledger(chain: Chain, *rows: tuple[str, str, str]) -> None:
    chain.write_notes([(i, status, f"feature/{i}", "7", chain.head, "0", "clean", mc) for i, status, mc in rows])


# requirement: small-change-chains / A small change runs only after the changes it depends on merged
def test_deps_pass_when_every_dependency_merged_into_the_base(merged):
    chain, merge, _ = merged
    _ledger(chain, ("a", "merged", merge), ("b", "merged — base not updated", merge))
    r = chain.check("deps", "--ids", "a", "b")
    assert r.returncode == 0, r.stdout
    assert _first(r) == "OK deps: a, b merged into HEAD"
    r = chain.check("deps", "--ids", "a", "--against", "origin/main")
    assert r.returncode == 0, r.stdout


# requirement: small-change-chains / A small change runs only after the changes it depends on merged
def test_deps_fail_on_a_dependency_not_recorded_as_merged(merged):
    chain, merge, _ = merged
    _ledger(chain, ("a", "merged", merge), ("b", "open — head moved", ""), ("c", "failed-merge — conflicts", merge))
    r = chain.check("deps", "--ids", "a", "b", "c", "d")
    assert r.returncode == 1
    assert _first(r) == "FAIL deps: not merged into HEAD: b, c, d"
    assert _problems(r) == ["PROBLEM dep-not-merged", "PROBLEM dep-not-merged", "PROBLEM dep-missing"]


def test_deps_fail_on_a_merged_status_without_a_merge_commit(merged):
    chain, _, _ = merged
    _ledger(chain, ("a", "merged", ""))
    r = chain.check("deps", "--ids", "a")
    assert r.returncode == 1
    assert _problems(r) == ["PROBLEM dep-no-merge-commit"]


# requirement: small-change-chains / A small change runs only after the changes it depends on merged
def test_deps_fail_on_a_merge_commit_the_base_does_not_hold(merged):
    chain, _, stray = merged
    _ledger(chain, ("a", "merged", stray), ("b", "merged", "0" * 40))
    r = chain.check("deps", "--ids", "a", "b")
    assert r.returncode == 1
    assert _first(r) == "FAIL deps: not merged into HEAD: a, b"
    assert _problems(r) == ["PROBLEM dep-not-in-base", "PROBLEM dep-not-in-base"]


def test_deps_cannot_check_a_malformed_merge_commit_or_a_bad_ref(merged):
    chain, merge, _ = merged
    _ledger(chain, ("a", "merged", "not-a-sha"))
    r = chain.check("deps", "--ids", "a")
    assert r.returncode == 2
    assert _first(r).startswith("UNCHECKED notes:")
    _ledger(chain, ("a", "merged", merge))
    r = chain.check("deps", "--ids", "a", "--against", "origin/no-such-branch")
    assert r.returncode == 2
    assert _first(r).startswith("UNCHECKED against:")


def test_deps_need_the_status_and_merge_commit_columns(merged):
    chain, merge, _ = merged
    chain.write_notes([], raw=f"| id | branch | pr_number | head_sha |\n|---|---|---|---|\n| a | x | 7 | {merge} |\n")
    r = chain.check("deps", "--ids", "a")
    assert r.returncode == 2
    assert "no status, merge_commit column" in _first(r)


def test_a_notes_path_that_cannot_be_read_cannot_be_checked(chain: Chain, tmp_path: Path):
    # A directory raises inside read_text (IsADirectoryError on POSIX, PermissionError on Windows).
    r = chain.run("resume", "--notes", str(tmp_path), "--id", "a", "--base", "main")
    assert r.returncode == 2
    assert _first(r).startswith("UNCHECKED notes:")


# ---------------------------------------------------------------- review round 1


def _pr_row(chain: Chain, change: str = "add-x", head: str | None = None) -> tuple[str, ...]:
    return (change, "feature/a", "7", chain.head if head is None else head, "enforced", "", "")


def _two_chains(chain: Chain) -> tuple[str, str]:
    """An old chain's notes with `add-x` merged as #3, and this chain's own file with `add-x` as #7.

    A change name returns in a later, unrelated chain, and old notes files stay for timing.
    """
    retro = chain.notes.parent
    chain.notes.unlink()
    old = retro / "multi-pr-run-notes-2026-03-01.md"
    mine = retro / "multi-pr-run-notes-2026-11-17.md"  # this chain started yesterday
    chain.write_notes([("add-x", "feature/a", "3", "e" * 40, "merged", "f" * 40, "")], header=_PR, to=old)
    chain.write_notes([_pr_row(chain)], header=_PR, to=mine)
    chain.gh_prs({
        3: {"state": "MERGED", "headRefOid": "e" * 40, "mergeCommit": {"oid": "f" * 40}},
        7: {"state": "OPEN", "headRefOid": chain.head},
    })
    return "cla.io/retro/" + old.name, "cla.io/retro/" + mine.name


# requirement: change-chains / A chain checks a pull request's head before it merges it
def test_an_old_chains_row_for_the_same_change_does_not_halt_this_chain(chain: Chain):
    _, mine = _two_chains(chain)
    r = chain.run("before-merge", "--notes", mine, "--id", "add-x", "--base", "main")
    assert r.returncode == 0, r.stdout
    assert [c[:3] for c in chain.gh_calls()] == [["pr", "view", "7"]]


# requirement: change-chains / A resumed chain acts only on its own pull request at the recorded head
def test_an_old_chains_merged_pr_is_never_this_chains_resume_result(chain: Chain):
    _, mine = _two_chains(chain)
    r = chain.run("resume", "--notes", mine, "--id", "add-x", "--base", "main")
    assert r.returncode == 0, r.stdout
    assert _first(r) == f"OK resume open: #7 at {chain.head}"
    assert [c[:3] for c in chain.gh_calls()] == [["pr", "view", "7"]]


def test_notes_take_one_file_and_no_glob(chain: Chain):
    _, mine = _two_chains(chain)
    r = chain.run("resume", "--notes", "cla.io/retro/multi-pr-run-notes-*.md", "--id", "add-x", "--base", "main")
    assert r.returncode == 2
    assert _first(r).startswith("UNCHECKED notes:") and "does not exist" in _first(r)
    # Two paths (an unquoted glob the shell expanded) are refused by the parser: exit 2 as well.
    r = chain.run("resume", "--notes", mine, mine, "--id", "add-x", "--base", "main")
    assert r.returncode == 2


def test_a_relative_notes_path_works_under_a_folder_with_a_bracket(chain: Chain, tmp_path: Path):
    odd = tmp_path / "re[po]"
    odd.mkdir()
    for name in ("origin.git", "work", "bin"):
        shutil.copytree(chain.tmp / name, odd / name, symlinks=True)
    env = dict(os.environ, PATH=str(odd / "bin") + os.pathsep + os.environ.get("PATH", ""))
    r = subprocess.run(
        [sys.executable, str(_SCRIPT), "before-merge", "--notes", "cla.io/retro/multi-lite-run-notes-2026-11-18.md",
         "--id", "a", "--base", "main", "--root", str(odd / "work")],
        cwd=Path(__file__).parent, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    assert r.returncode == 0, r.stdout


# requirement: change-chains / A chain checks a pull request's head before it merges it
def test_a_relative_notes_path_is_read_from_the_primary_checkout_in_a_worktree(chain: Chain):
    _git(chain.work, "checkout", "-q", "main")
    tree = chain.tmp / "wt"
    _git(chain.work, "worktree", "add", "-q", str(tree), "feature/a")
    env = dict(os.environ, PATH=str(chain.bin) + os.pathsep + os.environ.get("PATH", ""))
    r = subprocess.run(
        [sys.executable, str(_SCRIPT), "before-merge", "--notes", "cla.io/retro/multi-lite-run-notes-2026-11-18.md",
         "--id", "a", "--base", "main", "--root", str(tree)],
        cwd=Path(__file__).parent, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    assert r.returncode == 0, r.stdout
    (tree / "README.md").write_text("# dirty in the worktree\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(_SCRIPT), "fix-pushed", "--notes", "cla.io/retro/multi-lite-run-notes-2026-11-18.md",
         "--id", "a", "--root", str(tree)],
        cwd=Path(__file__).parent, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    assert r.returncode == 1 and "PROBLEM dirty" in r.stdout


# requirement: change-chains / A chain checks a pull request's head before it merges it
def test_a_root_below_the_top_still_sees_a_dirty_tree_above_it(chain: Chain):
    sub = chain.work / "sub"
    sub.mkdir()
    (sub / "s.txt").write_text("s\n", encoding="utf-8")
    _git(chain.work, "add", "sub/s.txt")
    _git(chain.work, "commit", "-q", "-m", "sub")
    _git(chain.work, "push", "-q", "origin", "feature/a")
    chain.head = _git(chain.work, "rev-parse", "HEAD").stdout.strip()
    chain.write_notes([("a", "open", "feature/a", "7", chain.head, "0", "clean", "")])
    chain.gh_pr()
    chain.work, top = sub, chain.work
    r = chain.check("before-merge")
    assert r.returncode == 0, r.stdout  # the run notes at the top are still not dirt
    (top / "README.md").write_text("# changed above the root\n", encoding="utf-8")
    r = chain.check("before-merge")
    assert r.returncode == 1
    assert _first(r) == "FAIL before-merge: uncommitted changes"


@pytest.mark.parametrize("value", ["missing", None, "false"])
def test_an_unreadable_cross_repository_flag_cannot_be_checked(chain: Chain, value):
    pr = {"number": 7, "state": "OPEN", "headRefOid": chain.head, "headRefName": "feature/a",
          "baseRefName": "main", "mergeCommit": None, "autoMergeRequest": None}
    if value != "missing":
        pr["isCrossRepository"] = value
    chain.gh(json.dumps(pr))
    r = chain.check("before-merge")
    assert r.returncode == 2
    assert _first(r).startswith("UNCHECKED gh:") and "isCrossRepository" in _first(r)


# requirement: change-chains / A chain counts a merge only when the host reports it merged
@pytest.mark.parametrize("fields,reason", [
    ({"headRefOid": "e" * 40}, "merged at a head this run did not check"),
    ({"baseRefName": "develop"}, "wrong base (develop)"),
])
def test_after_merge_refuses_a_merge_of_another_head_or_base(chain: Chain, fields: dict, reason: str):
    chain.gh_pr(state="MERGED", mergeCommit={"oid": "d" * 40}, **fields)
    r = chain.check("after-merge")
    assert r.returncode == 1
    assert _first(r) == f"FAIL after-merge: {reason}"


def test_after_merge_with_no_recorded_head_is_unverifiable(chain: Chain):
    chain.write_notes([("a", "open", "feature/a", "7", "", "0", "clean", "")])
    chain.gh_pr(state="MERGED", mergeCommit={"oid": "d" * 40})
    r = chain.check("after-merge")
    assert r.returncode == 1
    assert _first(r) == "FAIL after-merge: head unverifiable (ledger lost)"


# requirement: change-chains / A chain counts a merge only when the host reports it merged
@pytest.mark.parametrize("cmd", ["after-merge", "resume"])
def test_a_merge_with_no_merge_commit_cannot_be_recorded(chain: Chain, cmd: str):
    chain.gh_pr(state="MERGED", mergeCommit=None)
    r = chain.check(cmd)
    assert r.returncode == 2
    assert _first(r) == "UNCHECKED gh: #7 is MERGED but gh names no merge commit"


# requirement: change-chains / A resumed chain acts only on its own pull request at the recorded head
@pytest.mark.parametrize("fields,reason", [
    ({"state": "MERGED", "headRefOid": "e" * 40}, "merged at a head this run did not check"),
    ({"state": "MERGED", "baseRefName": "develop"}, "wrong base (develop)"),
    ({"baseRefName": "develop"}, "wrong base (develop)"),
])
def test_resume_passes_a_merge_only_into_the_base_at_the_recorded_head(chain: Chain, fields: dict, reason: str):
    chain.gh_pr(mergeCommit={"oid": "f" * 40}, **fields)
    r = chain.check("resume")
    assert r.returncode == 1
    assert _first(r) == f"FAIL resume: {reason}"


def test_resume_of_a_merged_pr_with_no_recorded_head_is_unverifiable(chain: Chain):
    chain.write_notes([("a", "open", "feature/a", "7", "", "", "", "")])
    chain.gh_pr(state="MERGED", mergeCommit={"oid": "f" * 40})
    r = chain.check("resume")
    assert r.returncode == 1
    assert _first(r) == "FAIL resume: head unverifiable (ledger lost)"


def test_deps_name_the_unmet_dependency_when_a_later_row_cannot_be_read(merged):
    chain, merge, _ = merged
    _ledger(chain, ("a", "open", ""), ("b", "merged", "not-a-sha"))
    r = chain.check("deps", "--ids", "a", "b")
    assert r.returncode == 1
    assert _first(r) == "FAIL deps: not merged into HEAD: a"
    assert r.stdout.splitlines()[-1].startswith("UNCHECKED notes:")
