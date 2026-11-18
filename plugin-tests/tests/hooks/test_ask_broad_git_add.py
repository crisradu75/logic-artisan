"""Tests for `ask-broad-git-add.py`: ask before a broad `git add` sweeps untracked files.

The hook's value is the condition, not the shape alone. A broad add over a tree
whose only changes are tracked modifications stages nothing new and must stay
silent, or the prompt becomes routine. So every broad form is pinned twice: it
asks when an untracked file is in scope, and it is silent when none is.

Real temp repos throughout, built once per session by `cached_git_repo` and
copied per test. Nothing here mocks git except the one test that removes it.
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

_HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "hooks"


def _load():
    spec = importlib.util.spec_from_file_location(
        "ask_broad_git_add", _HOOKS_DIR / "ask-broad-git-add.py"
    )
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
    """A committed tree: a root file, a subdirectory, an `openspec/` tree, and a
    `.gitignore` naming `ignored.env`."""
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "commit.gpgsign", "false")
    (root / ".gitignore").write_text("ignored.env\n", encoding="utf-8")
    (root / "tracked.txt").write_text("one\n", encoding="utf-8")
    (root / "sub").mkdir()
    (root / "sub" / "kept.txt").write_text("one\n", encoding="utf-8")
    (root / "openspec" / "specs").mkdir(parents=True)
    (root / "openspec" / "specs" / "spec.md").write_text("one\n", encoding="utf-8")
    _git(root, "add", ".gitignore", "tracked.txt", "sub/kept.txt", "openspec/specs/spec.md")
    _git(root, "commit", "-qm", "baseline")


@pytest.fixture
def repo(cached_git_repo, tmp_path) -> Path:
    return cached_git_repo("ask-broad-git-add", _build, tmp_path / "repo")


def _run(command: str, monkeypatch, capsys, cwd: Path | str | None) -> dict | None:
    payload: dict = {"tool_input": {"command": command}}
    if cwd is not None:
        payload["cwd"] = str(cwd)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert hook.main() == 0, "this hook must never block"
    out = capsys.readouterr().out.strip()
    return json.loads(out) if out else None


def _reason(payload: dict | None) -> str:
    assert payload is not None, "expected an ask"
    nested = payload["hookSpecificOutput"]
    assert nested["permissionDecision"] == "ask"
    return nested["permissionDecisionReason"]


_BROAD_FORMS = [
    "git add -A",
    "git add --all",
    "git add --no-ignore-removal",
    "git add .",
    "git add ./",
    "git add :/",
    "git add '*'",
    "git add ':(top)'",
    "git add -A .",
    "git add -A -- .",
    "git add -Av",
    # git resolves an unambiguous abbreviation, so these stage the tree too.
    "git add --a",
    "git add --no-ignore-r",
    # Only exclusions: git reads that as "everything except these".
    "git add ':!tracked.txt'",
    "git add ':^tracked.txt'",
    "git add ':(exclude)tracked.txt'",
    # `--chmod` takes the next token as its value, not as a pathspec.
    "git add -A --chmod +x",
    "GIT.EXE add -A",
    "/usr/bin/git add .",
]


# --------------------------------------------------------------------------- #
# Broad forms
# --------------------------------------------------------------------------- #


# requirement: git-guards / A broad git add that would stage untracked files asks first
@pytest.mark.parametrize("command", _BROAD_FORMS)
def test_each_broad_form_asks_when_an_untracked_file_exists(command, repo, monkeypatch, capsys):
    (repo / "stray.txt").write_text("scratch\n", encoding="utf-8")
    reason = _reason(_run(command, monkeypatch, capsys, repo))
    assert "`stray.txt`" in reason
    assert "1 untracked file(s)" in reason
    assert "Stage named paths instead" in reason


# requirement: git-guards / A broad git add that would stage untracked files asks first
@pytest.mark.parametrize("command", _BROAD_FORMS)
def test_each_broad_form_is_silent_with_only_tracked_modifications(command, repo, monkeypatch, capsys):
    (repo / "tracked.txt").write_text("two\n", encoding="utf-8")
    (repo / "sub" / "kept.txt").write_text("two\n", encoding="utf-8")
    assert _run(command, monkeypatch, capsys, repo) is None


# --------------------------------------------------------------------------- #
# Not broad, whatever is untracked
# --------------------------------------------------------------------------- #


# requirement: git-guards / A broad git add that would stage untracked files asks first
@pytest.mark.parametrize(
    "command",
    [
        "git add -u",
        "git add --update",
        "git add -u .",
        "git add --up .",
        "git add --renormalize .",
        "git add stray.txt",
        "git add tracked.txt stray.txt",
        "git add sub/",
        # `-A <path>` is scoped to `<path>`.
        "git add -A stray.txt",
        "git add --all -- tracked.txt",
        # These stage nothing.
        "git add -n .",
        "git add --dry-run -A",
        "git add --refresh .",
        "git add -p .",
        # git refuses an ambiguous or unknown option, so nothing is staged.
        "git add --n .",
        "git add --bogus .",
        # `--ig` could be --ignore-removal, --ignore-errors or --ignore-missing.
        "git add --ig .",
        "git add -Z .",
        # `git add` with nothing names nothing.
        "git add",
        # Not `git add` at all.
        "git status .",
        "git commit -am x",
        "git addx .",
        # The paths live in a file this hook does not read.
        "git add --pathspec-from-file list.txt",
        "git add -A --pathspec-from-file list.txt",
        "git add -A --pathspec-from-file=list.txt",
    ],
)
def test_narrow_or_non_staging_adds_are_silent(command, repo, monkeypatch, capsys):
    (repo / "stray.txt").write_text("scratch\n", encoding="utf-8")
    (repo / "other.txt").write_text("scratch\n", encoding="utf-8")
    assert _run(command, monkeypatch, capsys, repo) is None


@pytest.mark.parametrize(
    "command",
    [
        'git commit -m "git add -A"',
        "echo 'git add .'",
        'echo "run git add -A later"',
    ],
)
def test_quoted_text_is_not_a_command(command, repo, monkeypatch, capsys):
    (repo / "stray.txt").write_text("scratch\n", encoding="utf-8")
    assert _run(command, monkeypatch, capsys, repo) is None


# --------------------------------------------------------------------------- #
# Where it looks
# --------------------------------------------------------------------------- #


def test_dash_c_moves_the_directory_dot_means(repo, monkeypatch, capsys, tmp_path):
    (repo / "stray.txt").write_text("scratch\n", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    # From outside the repo, `-C <repo>` points the probe at it.
    reason = _reason(_run(f"git -C {repo.as_posix()} add .", monkeypatch, capsys, elsewhere))
    assert "`stray.txt`" in reason
    # `.` in `sub` covers `sub` only: the root's untracked file is out of scope.
    assert _run("git -C sub add .", monkeypatch, capsys, repo) is None
    (repo / "sub" / "new.txt").write_text("x\n", encoding="utf-8")
    reason = _reason(_run("git -C sub add .", monkeypatch, capsys, repo))
    assert "`sub/new.txt`" in reason and "stray.txt" not in reason
    # A quoted `-C` value is still followed.
    reason = _reason(_run(f'git -C "{repo.as_posix()}" add -A', monkeypatch, capsys, elsewhere))
    assert "`stray.txt`" in reason


def test_dash_a_covers_the_whole_tree_even_from_a_subdirectory(repo, monkeypatch, capsys):
    (repo / "stray.txt").write_text("scratch\n", encoding="utf-8")
    reason = _reason(_run("git add -A", monkeypatch, capsys, repo / "sub"))
    assert "`stray.txt`" in reason


@pytest.mark.parametrize(
    "command",
    [
        "git status && git add -A",
        "echo start; git add .",
        "git diff --stat | cat\ngit add -A",
        "(git add .)",
        "x=$(git add -A)",
        "git \\\nadd -A",
        "git add \\\n  .",
        "true || git add .",
        "git -c core.quotepath=off --no-pager add .",
        # A redirection target is not a pathspec, so it does not narrow `-A`.
        "git add -A > /dev/null",
        "git add -A >/dev/null 2>&1",
        "git add -A 2> err.log",
    ],
)
def test_a_broad_add_inside_a_chain_still_asks(command, repo, monkeypatch, capsys):
    (repo / "stray.txt").write_text("scratch\n", encoding="utf-8")
    assert "`stray.txt`" in _reason(_run(command, monkeypatch, capsys, repo))


@pytest.mark.parametrize(
    "command",
    [
        # A newline ends the command, so `.` on the next line is not its operand.
        "git add tracked.txt\n.",
        # The broad operand belongs to a later, different command.
        "git add tracked.txt && ls .",
    ],
)
def test_an_operand_of_another_command_is_not_the_adds(command, repo, monkeypatch, capsys):
    (repo / "stray.txt").write_text("scratch\n", encoding="utf-8")
    assert _run(command, monkeypatch, capsys, repo) is None


# requirement: git-guards / A broad git add that would stage untracked files asks first
@pytest.mark.parametrize("operand", ["openspec", "openspec/", "./openspec/", ":/openspec", "openspec/*"])
def test_a_bare_openspec_operand_is_scoped_to_openspec(operand, repo, monkeypatch, capsys):
    (repo / "stray.txt").write_text("scratch\n", encoding="utf-8")
    command = f"git add '{operand}'"
    # An untracked file outside `openspec/` is not swept by it.
    assert _run(command, monkeypatch, capsys, repo) is None
    sibling = repo / "openspec" / "changes" / "sibling-change"
    sibling.mkdir(parents=True)
    (sibling / "proposal.md").write_text("x\n", encoding="utf-8")
    reason = _reason(_run(command, monkeypatch, capsys, repo))
    assert "`openspec/changes/sibling-change/proposal.md`" in reason
    assert "stray.txt" not in reason


def test_a_named_path_under_openspec_is_not_broad(repo, monkeypatch, capsys):
    sibling = repo / "openspec" / "changes" / "sibling-change"
    sibling.mkdir(parents=True)
    (sibling / "proposal.md").write_text("x\n", encoding="utf-8")
    assert _run("git add openspec/specs/spec.md", monkeypatch, capsys, repo) is None


def test_an_ignored_file_does_not_count(repo, monkeypatch, capsys):
    (repo / "ignored.env").write_text("TOKEN=x\n", encoding="utf-8")
    assert _run("git add -A", monkeypatch, capsys, repo) is None
    assert _run("git add .", monkeypatch, capsys, repo) is None


@pytest.mark.parametrize("command", ["git add -f .", "git add --force .", "git add -Af"])
def test_force_counts_the_ignored_files_it_would_add(command, repo, monkeypatch, capsys):
    (repo / "ignored.env").write_text("TOKEN=x\n", encoding="utf-8")
    assert "`ignored.env`" in _reason(_run(command, monkeypatch, capsys, repo))


def test_a_staged_rename_does_not_hide_the_untracked_file_after_it(repo, monkeypatch, capsys):
    """In `-z` output a rename carries its source path as a separate field."""
    _git(repo, "mv", "tracked.txt", "moved.txt")
    (repo / "stray.txt").write_text("scratch\n", encoding="utf-8")
    reason = _reason(_run("git add -A", monkeypatch, capsys, repo))
    assert "1 untracked file(s)" in reason and "`stray.txt`" in reason


def test_a_rename_source_field_is_never_read_as_an_entry(monkeypatch, tmp_path):
    """A source path is a bare path, so one that happens to begin with `?? `
    would read as an untracked entry if the parser did not skip it."""
    fake = "R  new.txt\0?? looks-untracked.txt\0?? stray.txt\0"

    def _status(args, *_a, **_k):
        return subprocess.CompletedProcess(args, 0, fake, "")

    monkeypatch.setattr(hook.subprocess, "run", _status)
    assert hook._status_entries(str(tmp_path), [], False, 1.0) == ["stray.txt"]


def test_an_exclusion_beside_a_broad_pathspec_is_respected(repo, monkeypatch, capsys):
    (repo / "stray.txt").write_text("scratch\n", encoding="utf-8")
    assert _run("git add . ':!stray.txt'", monkeypatch, capsys, repo) is None


# --------------------------------------------------------------------------- #
# The message
# --------------------------------------------------------------------------- #


def test_the_ask_names_at_most_ten_files_and_gives_the_count(repo, monkeypatch, capsys):
    names = [f"stray-{n:02d}.txt" for n in range(12)]
    for name in names:
        (repo / name).write_text("x\n", encoding="utf-8")
    reason = _reason(_run("git add -A", monkeypatch, capsys, repo))
    assert "12 untracked file(s)" in reason
    assert sum(f"`{name}`" in reason for name in names) == 10
    assert "and 2 more" in reason
    assert "(hook: ask-broad-git-add.py)" in reason


def test_two_broad_adds_in_one_command_are_reported_together(repo, monkeypatch, capsys):
    (repo / "stray.txt").write_text("scratch\n", encoding="utf-8")
    (repo / "sub" / "new.txt").write_text("x\n", encoding="utf-8")
    reason = _reason(_run("git -C sub add . && git add -A", monkeypatch, capsys, repo))
    assert "2 untracked file(s)" in reason
    assert "`stray.txt`" in reason and "`sub/new.txt`" in reason


# --------------------------------------------------------------------------- #
# Best-effort: silent whenever it cannot look
# --------------------------------------------------------------------------- #


def test_silent_outside_a_repository(monkeypatch, capsys, tmp_path):
    (tmp_path / "stray.txt").write_text("scratch\n", encoding="utf-8")
    assert _run("git add -A", monkeypatch, capsys, tmp_path) is None


def test_silent_when_the_dash_c_directory_does_not_exist(repo, monkeypatch, capsys):
    (repo / "stray.txt").write_text("scratch\n", encoding="utf-8")
    assert _run("git -C no/such/dir add .", monkeypatch, capsys, repo) is None
    assert _run("git -C $WORKTREE add .", monkeypatch, capsys, repo) is None


@pytest.mark.parametrize(
    "command",
    [
        "git --git-dir=/elsewhere/.git add -A",
        "git --work-tree /elsewhere add .",
        "GIT_DIR=/elsewhere/.git git add -A",
    ],
)
def test_silent_when_the_repository_is_named_some_other_way(command, repo, monkeypatch, capsys):
    (repo / "stray.txt").write_text("scratch\n", encoding="utf-8")
    assert _run(command, monkeypatch, capsys, repo) is None


def test_silent_when_git_cannot_be_run(repo, monkeypatch, capsys):
    (repo / "stray.txt").write_text("scratch\n", encoding="utf-8")

    def _no_git(*_args, **_kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(hook.subprocess, "run", _no_git)
    assert _run("git add -A", monkeypatch, capsys, repo) is None


def test_silent_when_git_times_out(repo, monkeypatch, capsys):
    (repo / "stray.txt").write_text("scratch\n", encoding="utf-8")

    def _hang(args, *_a, **kwargs):
        raise subprocess.TimeoutExpired(args, kwargs.get("timeout"))

    monkeypatch.setattr(hook.subprocess, "run", _hang)
    assert _run("git add -A", monkeypatch, capsys, repo) is None


def test_every_probe_shares_one_deadline(repo, monkeypatch, capsys):
    """However many broad adds a command chains, the probes together get
    `STATUS_BUDGET_SECONDS`: `HOOK_WORST_CASE_SECONDS` states that one figure."""
    timeouts: list[float] = []
    real_run = subprocess.run

    def _record(args, *a, **kwargs):
        timeouts.append(kwargs["timeout"])
        return real_run(args, *a, **kwargs)

    monkeypatch.setattr(hook.subprocess, "run", _record)
    (repo / "sub" / "new.txt").write_text("x\n", encoding="utf-8")
    _run("git add -A && git -C sub add . && git add openspec", monkeypatch, capsys, repo)
    assert len(timeouts) == 3
    assert all(t <= hook.STATUS_BUDGET_SECONDS for t in timeouts)
    assert all(a > b for a, b in zip(timeouts, timeouts[1:])), (
        f"each probe gets only what is left of one deadline: {timeouts}"
    )


@pytest.mark.parametrize("stdin_text", ["", "not json", "[]", '{"tool_input": "x"}', '{"tool_input": {"command": 7}}'])
def test_silent_on_input_it_cannot_read(stdin_text, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


# --------------------------------------------------------------------------- #
# Linear time
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "unit",
    [
        "git -c ",       # a run of option values that each read `git`: quadratic for a regex
        "git -C . ",
        "git add . ",
        "git add -A; ",
        "git ",
        "-c git ",
        "x ",
    ],
)
def test_a_long_hostile_command_stays_fast(unit, monkeypatch, capsys, tmp_path):
    # Outside a repository, so the cost measured is the parse, plus at most one
    # failing probe per distinct invocation.
    for size in (50_000, 400_000):
        command = unit * (size // len(unit)) + "add ."
        started = time.perf_counter()
        _run(command, monkeypatch, capsys, tmp_path)
        assert time.perf_counter() - started < 3.0, (unit, size)


# --------------------------------------------------------------------------- #
# Review-suggestion fixes
# --------------------------------------------------------------------------- #


def test_a_glob_directory_pathspec_asks(repo, monkeypatch, capsys):
    (repo / "sub" / "new.txt").write_text("x\n", encoding="utf-8")
    assert "`sub/new.txt`" in _reason(_run("git add */", monkeypatch, capsys, repo))


def test_a_git_dir_in_another_segment_does_not_silence_the_add(repo, monkeypatch, capsys):
    (repo / "stray.txt").write_text("x\n", encoding="utf-8")
    assert "`stray.txt`" in _reason(_run("GIT_DIR=x git status; git add -A", monkeypatch, capsys, repo))
    assert _run("GIT_DIR=x git add -A", monkeypatch, capsys, repo) is None


def test_a_worktree_side_rename_is_skipped_with_its_source(monkeypatch, tmp_path):
    fake = " R new.txt\0?? looks-untracked.txt\0?? stray.txt\0"
    monkeypatch.setattr(
        hook.subprocess, "run", lambda args, *_a, **_k: subprocess.CompletedProcess(args, 0, fake, "")
    )
    assert hook._status_entries(str(tmp_path), [], False, 1.0) == ["stray.txt"]


def test_a_parser_failure_fails_open_with_one_stderr_line(monkeypatch, capsys):
    def boom(*_a, **_k):
        raise KeyError("x")

    monkeypatch.setattr(hook, "_broad_invocations", boom)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_input": {"command": "git add -A"}})))
    assert hook.main() == 0
    out = capsys.readouterr()
    assert out.out == "" and out.err.strip().count("\n") == 0 and "KeyError" in out.err


def test_a_file_name_cannot_spell_a_failure_marker_in_the_reason(repo, monkeypatch, capsys):
    (repo / "the guard did not run.txt").write_text("x\n", encoding="utf-8")
    reason = _reason(_run("git add -A", monkeypatch, capsys, repo)).lower()
    assert "guard" in reason and "did not run" not in reason and "could not run" not in reason


def test_a_glob_directory_pathspec_names_only_files_below_its_directories(repo, monkeypatch, capsys):
    (repo / "root-stray.txt").write_text("x\n", encoding="utf-8")
    assert _run("git add */", monkeypatch, capsys, repo) is None
    (repo / "sub" / "new.txt").write_text("x\n", encoding="utf-8")
    assert "root-stray" not in _reason(_run("git add */", monkeypatch, capsys, repo))
    assert _run("git add openspec/*/", monkeypatch, capsys, repo) is None
    (repo / "openspec" / "specs" / "n.md").write_text("x\n", encoding="utf-8")
    reason = _reason(_run("git add openspec/*/", monkeypatch, capsys, repo))
    assert "openspec/specs/n.md" in reason and "sub/new.txt" not in reason
