"""Tests for multi-pr's check_cite_drift.py (GitHub #272).

A five-change chain's last change was written before the first four merged; every
`file:line` it cited had moved, and Review spent its budget rediscovering that.
These tests build a real repo, record a chain-start commit, move lines the way a
sibling merge would, then check a change's cites against the result.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import check_cite_drift

SCRIPT = Path(check_cite_drift.__file__)
SRC = [f"line {i}" for i in range(1, 11)]  # src/app.py lines 1..10


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace"
    ).stdout.strip()


def _write(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def chain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A repo at its chain-start commit, with `src/app.py`, `src/other.py`,
    `src/stay.py` and an empty change directory. Returns (repo, start_sha, change_dir)."""
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    _write(tmp_path / "src" / "app.py", SRC)
    _write(tmp_path / "src" / "other.py", ["alpha", "beta"])
    _write(tmp_path / "src" / "stay.py", ["kept"])
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "start")
    change = tmp_path / "openspec" / "changes" / "later"
    change.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path, _git(tmp_path, "rev-parse", "HEAD"), change


def _merge_sibling(repo: Path, app: list[str] | None, other: bool = True) -> None:
    """Commit what an earlier change in the chain did to the tree."""
    if app is None:
        _git(repo, "rm", "-q", "src/app.py")
    else:
        _write(repo / "src" / "app.py", app)
    if not other:
        _git(repo, "rm", "-q", "src/other.py")
    _git(repo, "add", "-A", "src")
    _git(repo, "commit", "-q", "-m", "sibling merge")


def _run(change: Path, *flags: str) -> tuple[int, list[str], str]:
    result = subprocess.run(
        ["python3", str(SCRIPT), str(change), *flags], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return result.returncode, [r for r in result.stdout.splitlines() if r], result.stderr


def test_a_cite_whose_lines_moved_is_drifted_with_the_new_number(chain):
    repo, start, change = chain
    _write(change / "tasks.md", ["- [ ] 1.1 Edit `src/app.py:4` and `src/app.py:6-7`"])
    _merge_sibling(repo, ["new a", "new b", *SRC])  # two lines inserted on top
    code, rows, _ = _run(change, "--since", start)
    assert code == check_cite_drift.EXIT_DRIFT
    assert rows == [
        "drifted\ttasks.md:1\tsrc/app.py:4\tsrc/app.py:6",
        "drifted\ttasks.md:1\tsrc/app.py:6-7\tsrc/app.py:8-9",
    ]


# requirement: change-chains / A later change's code references are rechecked after earlier merges
def test_fix_rewrites_drifted_cites_in_place_and_exits_clean(chain):
    repo, start, change = chain
    _write(change / "tasks.md", ["- [ ] 1.1 Edit `src/app.py:4`", "- [ ] 1.2 Edit `src/app.py:6-7`"])
    _write(change / "design.md", ["See src/app.py:10."])
    _merge_sibling(repo, ["new a", *SRC])
    code, rows, _ = _run(change, "--since", start, "--fix")
    assert code == check_cite_drift.EXIT_CLEAN
    assert len(rows) == 3
    assert (change / "tasks.md").read_text(encoding="utf-8") == (
        "- [ ] 1.1 Edit `src/app.py:5`\n- [ ] 1.2 Edit `src/app.py:7-8`\n"
    )
    assert (change / "design.md").read_text(encoding="utf-8") == "See src/app.py:11.\n"


def test_a_cite_whose_lines_are_still_in_place_is_not_reported(chain):
    repo, start, change = chain
    _write(change / "tasks.md", ["- [ ] Edit `src/app.py:2`"])
    _merge_sibling(repo, [*SRC, "appended"])  # a change below the cite
    code, rows, _ = _run(change, "--since", start)
    assert (code, rows) == (check_cite_drift.EXIT_CLEAN, [])


# requirement: change-chains / A later change's code references are rechecked after earlier merges
def test_a_cite_whose_lines_were_removed_is_gone_and_fix_leaves_it(chain):
    repo, start, change = chain
    original = "- [ ] Edit `src/app.py:3` and src/other.py:1\n"
    (change / "tasks.md").write_text(original, encoding="utf-8")
    _merge_sibling(repo, [line for line in SRC if line != "line 3"], other=False)
    code, rows, _ = _run(change, "--since", start, "--fix")
    assert code == check_cite_drift.EXIT_DRIFT
    assert rows == ["gone\ttasks.md:1\tsrc/app.py:3", "gone\ttasks.md:1\tsrc/other.py:1"]
    assert (change / "tasks.md").read_text(encoding="utf-8") == original


def test_a_cite_whose_lines_now_occur_twice_is_ambiguous(chain):
    repo, start, change = chain
    _write(change / "tasks.md", ["- [ ] Edit `src/app.py:5`"])
    _merge_sibling(repo, ["line 5", *[line for line in SRC if line != "line 5"], "line 5"])
    code, rows, _ = _run(change, "--since", start, "--fix")
    assert code == check_cite_drift.EXIT_DRIFT
    assert rows == ["ambiguous\ttasks.md:1\tsrc/app.py:5"]


def test_a_cite_of_a_file_no_merge_touched_is_not_read(chain, monkeypatch):
    repo, start, change = chain
    _write(change / "tasks.md", ["- [ ] Edit `src/stay.py:1`"])
    _merge_sibling(repo, ["new a", *SRC])
    read = []
    real = check_cite_drift._file_at
    monkeypatch.setattr(check_cite_drift, "_file_at", lambda r, ref, p: read.append(p) or real(r, ref, p))
    report, code = check_cite_drift.check(repo, change, start, "HEAD", fix=False)
    assert (report, code, read) == ([], check_cite_drift.EXIT_CLEAN, [])


@pytest.mark.parametrize(
    "cite",
    ["src/new.py:1", "src/app.py:99", "app.py:4"],
    ids=["file-the-change-creates", "past-the-end", "bare-filename"],
)
def test_cites_the_check_cannot_judge_are_left_alone(chain, cite):
    repo, start, change = chain
    _write(change / "tasks.md", [f"- [ ] Edit `{cite}`"])
    _write(repo / "src" / "new.py", ["created later"])
    _merge_sibling(repo, ["new a", *SRC])
    code, rows, _ = _run(change, "--since", start)
    assert (code, rows) == (check_cite_drift.EXIT_CLEAN, [])


def test_a_cite_of_blank_lines_is_not_judged(chain):
    repo, start, change = chain
    _git(repo, "checkout", "-q", "-b", "blank")
    _write(repo / "src" / "app.py", ["a", "", "b"])
    _git(repo, "commit", "-q", "-am", "blank line")
    blank_start = _git(repo, "rev-parse", "HEAD")
    _write(change / "tasks.md", ["- [ ] Edit `src/app.py:2`"])
    _write(repo / "src" / "app.py", ["x", "a", "b"])
    _git(repo, "commit", "-q", "-am", "move")
    code, rows, _ = _run(change, "--since", blank_start)
    assert (code, rows) == (check_cite_drift.EXIT_CLEAN, [])


def test_the_detector_is_not_vacuous():
    assert check_cite_drift.judge(["a", "b"], ["x", "a", "b"], 1, 2) == ("drifted", 2)
    assert check_cite_drift.judge(["a", "b"], ["a", "b"], 1, 2) == ("ok", 1)
    assert check_cite_drift.judge(["a"], ["b"], 1, 1) == ("gone", None)
    assert check_cite_drift.judge(["a"], None, 1, 1) == ("gone", None)
    assert check_cite_drift.judge(["a"], ["a", "x", "a"], 1, 1) == ("ok", 1)
    assert check_cite_drift.judge(["a"], ["x", "a", "a"], 1, 1) == ("ambiguous", None)


@pytest.mark.parametrize("since", ["0" * 40, "no-such-ref"])
def test_an_unknown_start_commit_cannot_run(chain, since):
    _, _, change = chain
    _write(change / "tasks.md", ["- [ ] Edit `src/app.py:4`"])
    code, rows, err = _run(change, "--since", since)
    assert (code, rows) == (check_cite_drift.EXIT_CANNOT_RUN, [])
    assert "unknown commit" in err


def test_a_change_with_no_artifacts_cannot_run(chain):
    _, start, change = chain
    code, _, err = _run(change, "--since", start)
    assert code == check_cite_drift.EXIT_CANNOT_RUN
    assert "no tasks.md or design.md" in err


def test_outside_a_git_repo_cannot_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tasks.md").write_text("x\n", encoding="utf-8")
    code, _, err = _run(tmp_path, "--since", "HEAD")
    assert code == check_cite_drift.EXIT_CANNOT_RUN
    assert "not inside a git repository" in err
