"""Tests for `warn-lossy-merge-resolution.py`: warn before a merge commit whose
result lacks lines the merged-in side added.

Every case runs on a real temp repo, built once per session by `cached_git_repo`
and copied per test. The template is already MID-MERGE: `main` merged `other`
and stopped on a conflict in `f.txt`, so each test starts with `MERGE_HEAD`
present and resolves `f.txt` its own way.

    base  f.txt: a / b / c                       clean.txt: x
    other f.txt: a / b_theirs / theirs_line() / c  clean.txt: x / y_theirs
    main  f.txt: a / b_ours / c                  clean.txt: x

`clean.txt` merges cleanly to `other`'s version, so it is staged equal to
`MERGE_HEAD` and is never a candidate.

THE DELIBERATE-REPLACEMENT CASE. A resolver who replaces the other side's line
with a different one on purpose gets the warning too. The hook cannot tell a
deliberate replacement from an accidental drop: both leave the result without
a line the other side added. Staying silent would need intent the hook cannot
read, and the cost of a warning on a deliberate drop is one read and a line in
the commit message, which is what the message asks for. So the right
behaviour is to warn, and to say what to do when the drop was meant.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
_HOOKS_DIR = _PLUGIN / "hooks"
_HOOK_FILE = "warn-lossy-merge-resolution.py"

BOTH = "a\nb_ours\nb_theirs\ntheirs_line()\nc\n"
OURS = "a\nb_ours\nc\n"


def _load():
    spec = importlib.util.spec_from_file_location("warn_lossy_merge_resolution", _HOOKS_DIR / _HOOK_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load()


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=check, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def _write(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def _build(root: Path) -> None:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "commit.gpgsign", "false")
    _git(root, "config", "core.autocrlf", "false")
    _write(root / "f.txt", "a\nb\nc\n")
    _write(root / "clean.txt", "x\n")
    _git(root, "add", "f.txt", "clean.txt")
    _git(root, "commit", "-qm", "base")
    _git(root, "branch", "-M", "main")
    _git(root, "checkout", "-qb", "other")
    _write(root / "f.txt", "a\nb_theirs\ntheirs_line()\nc\n")
    _write(root / "clean.txt", "x\ny_theirs\n")
    _git(root, "commit", "-qam", "theirs")
    _git(root, "checkout", "-q", "main")
    _write(root / "f.txt", OURS)
    _git(root, "commit", "-qam", "ours")
    merge = _git(root, "merge", "other", check=False)
    assert merge.returncode != 0, "the template must stop on a conflict"


@pytest.fixture
def repo(cached_git_repo, tmp_path) -> Path:
    dest = cached_git_repo("warn-lossy-merge-resolution", _build, tmp_path / "repo")
    # A copied work tree keeps the template's index stat data (inode, ctime), which
    # a copy cannot preserve on Windows, so `git merge --abort` there refuses with
    # "Entry ... not uptodate". Refreshing re-reads the stat data and changes no
    # content. It exits 1 for the unmerged path (still conflicted), so 0 and 1 are
    # both fine; anything else (128: not a repo, a lock) is a real failure.
    refreshed = _git(dest, "update-index", "-q", "--refresh", check=False)
    assert refreshed.returncode in (0, 1), refreshed.stderr
    return dest


def _resolve(repo: Path, text: str) -> None:
    _write(repo / "f.txt", text)
    _git(repo, "add", "f.txt")


def _run(command: str, monkeypatch, capsys, cwd: Path | str | None) -> str:
    payload: dict = {"tool_input": {"command": command}}
    if cwd is not None:
        payload["cwd"] = str(cwd)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert hook.main() == 0, "a warn hook exits 0"
    captured = capsys.readouterr()
    assert captured.out == "", "a warn hook decides nothing: no JSON on stdout"
    return captured.err


# --------------------------------------------------------------------------- #
# The four behaviours the brief names
# --------------------------------------------------------------------------- #


# requirement: guard-warnings / A merge commit that drops lines the other side added warns
def test_taking_our_side_whole_warns_and_names_the_lost_lines(repo, monkeypatch, capsys):
    _git(repo, "checkout", "--ours", "f.txt")
    _git(repo, "add", "f.txt")
    err = _run("git commit --no-edit", monkeypatch, capsys, repo)
    assert "[warn-lossy-merge-resolution]" in err
    assert "`f.txt` (2 line(s): 'b_theirs'; 'theirs_line()')" in err
    assert "clean.txt" not in err, "a file merged cleanly to their side lost nothing"


# requirement: guard-warnings / A merge commit that drops lines the other side added warns
def test_a_resolution_that_keeps_both_sides_is_silent(repo, monkeypatch, capsys):
    _resolve(repo, BOTH)
    assert _run("git commit --no-edit", monkeypatch, capsys, repo) == ""


def test_no_merge_in_progress_is_silent(repo, monkeypatch, capsys):
    _git(repo, "merge", "--abort")
    _write(repo / "f.txt", "a\n")  # a commit that drops lines, but no merge
    _git(repo, "add", "f.txt")
    assert _run("git commit -m x", monkeypatch, capsys, repo) == ""


# requirement: guard-warnings / A merge commit that drops lines the other side added warns
def test_a_line_replaced_on_purpose_still_warns_and_says_what_to_do(repo, monkeypatch, capsys):
    """See the module docstring: the hook cannot read intent, so it warns, and
    the message says to state a deliberate drop in the commit message."""
    _resolve(repo, "a\nb_ours\ntheirs_line()\nc\n")  # b_theirs replaced by b_ours on purpose
    err = _run("git commit --no-edit", monkeypatch, capsys, repo)
    assert "`f.txt` (1 line(s): 'b_theirs')" in err
    assert "theirs_line()" not in err, "a kept line is not reported"
    assert "on purpose, say so in the commit message" in err


def test_a_broken_repository_is_silent(repo, monkeypatch, capsys):
    _resolve(repo, OURS)
    (repo / ".git" / "HEAD").write_text("not a ref\n", encoding="utf-8")
    assert _run("git commit --no-edit", monkeypatch, capsys, repo) == ""


def test_no_git_on_path_is_silent(repo, monkeypatch, capsys, tmp_path):
    _resolve(repo, OURS)
    empty = tmp_path / "empty-path"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    assert _run("git commit --no-edit", monkeypatch, capsys, repo) == ""


@pytest.mark.skipif(sys.platform == "win32", reason="a shell-script git stand-in is POSIX-only")
def test_a_git_that_prints_garbage_is_silent(repo, monkeypatch, capsys, tmp_path):
    _resolve(repo, OURS)
    fake = tmp_path / "fake-bin"
    fake.mkdir()
    script = fake / "git"
    script.write_text("#!/bin/sh\nprintf 'garbage\\0more garbage\\n12 blob x\\n'\n", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake}{os.pathsep}{os.environ.get('PATH', '')}")
    assert _run("git commit --no-edit", monkeypatch, capsys, repo) == ""


def test_a_git_call_that_raises_is_silent(repo, monkeypatch, capsys):
    _resolve(repo, OURS)

    def boom(*_a, **_k):
        raise subprocess.TimeoutExpired("git", 1)

    monkeypatch.setattr(hook.subprocess, "run", boom)
    assert _run("git commit --no-edit", monkeypatch, capsys, repo) == ""


def test_bad_input_is_silent(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


# --------------------------------------------------------------------------- #
# Which commands it reads
# --------------------------------------------------------------------------- #


# requirement: guard-warnings / A merge commit that drops lines the other side added warns
def test_merge_continue_warns(repo, monkeypatch, capsys):
    _resolve(repo, OURS)
    assert "f.txt" in _run("git merge --continue", monkeypatch, capsys, repo)


@pytest.mark.parametrize("command", [
    "git merge --abort",
    "git merge other",
    "git commit --dry-run",
    "echo 'git commit'",
    "git status",
    "GIT_DIR=.git git commit --no-edit",
])
def test_commands_that_conclude_no_merge_are_silent(repo, monkeypatch, capsys, command):
    _resolve(repo, OURS)
    assert _run(command, monkeypatch, capsys, repo) == ""


def test_a_commit_inside_a_heredoc_body_is_data(repo, monkeypatch, capsys):
    _resolve(repo, OURS)
    command = "cat > notes.txt <<'EOF'\ngit commit --no-edit\nEOF"
    assert _run(command, monkeypatch, capsys, repo) == ""


def test_a_commit_inside_a_shell_wrapper_is_read(repo, monkeypatch, capsys):
    _resolve(repo, OURS)
    assert "f.txt" in _run("bash -c 'git commit --no-edit'", monkeypatch, capsys, repo)


def test_git_dash_c_names_the_repository(repo, monkeypatch, capsys, tmp_path):
    _resolve(repo, OURS)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    assert "f.txt" in _run(f"git -C {repo.as_posix()} commit --no-edit", monkeypatch, capsys, elsewhere)
    assert _run("git commit --no-edit", monkeypatch, capsys, elsewhere) == ""


def test_git_calls_run_once_per_directory_not_once_per_commit(repo, monkeypatch, capsys):
    """Two wrapped commits in one directory: one set of git calls, on one deadline."""
    _resolve(repo, OURS)
    calls: list[list[str]] = []
    real = subprocess.run

    def counting(args, *a, **k):
        calls.append(list(args))
        return real(args, *a, **k)

    monkeypatch.setattr(hook.subprocess, "run", counting)
    err = _run("bash -c 'git commit --no-edit'; sh -c 'git commit --no-edit'; git commit",
               monkeypatch, capsys, repo)
    assert "f.txt" in err
    assert len(calls) == 5, [c[4:6] for c in calls]


# --------------------------------------------------------------------------- #
# What it reads as the result
# --------------------------------------------------------------------------- #


def test_commit_all_reads_the_working_tree(repo, monkeypatch, capsys):
    """`-a` stages the working tree, so the working tree is the result."""
    _resolve(repo, BOTH)
    _write(repo / "f.txt", OURS)  # staged both sides, working tree back to ours
    assert "f.txt" in _run("git commit -a --no-edit", monkeypatch, capsys, repo)
    assert _run("git commit --no-edit", monkeypatch, capsys, repo) == ""


def test_an_unmerged_file_resolved_in_the_working_tree_is_read(repo, monkeypatch, capsys):
    """`git add f.txt && git commit`: the add has not run when the hook does."""
    _write(repo / "f.txt", OURS)
    assert "f.txt" in _run("git add f.txt && git commit --no-edit", monkeypatch, capsys, repo)


def test_an_unmerged_file_still_holding_markers_reports_nothing_lost(repo, monkeypatch, capsys):
    """The markers hold both sides' lines, so nothing their side added is missing."""
    assert "<<<<<<< " in (repo / "f.txt").read_text(encoding="utf-8")
    assert _run("git commit --no-edit", monkeypatch, capsys, repo) == ""


def test_an_unmerged_file_missing_from_the_working_tree_is_skipped(repo, monkeypatch, capsys):
    (repo / "f.txt").unlink()
    assert _run("git commit --no-edit", monkeypatch, capsys, repo) == ""


def test_a_cleanly_merged_file_does_not_use_up_the_file_cap(repo, monkeypatch, capsys):
    """`clean.txt` sorts first and equals their side; with room for one file,
    the file a resolution touched is still the one read."""
    _resolve(repo, OURS)
    monkeypatch.setattr(hook, "MAX_FILES", 1)
    assert "f.txt" in _run("git commit --no-edit", monkeypatch, capsys, repo)


def test_a_binary_file_is_not_read_as_lines(repo, monkeypatch, capsys):
    _git(repo, "merge", "--abort")
    _git(repo, "checkout", "-q", "other")
    (repo / "bin.dat").write_bytes(b"\x00theirs\nadded\n")
    _git(repo, "add", "bin.dat")
    _git(repo, "commit", "-qm", "binary")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "other", check=False)
    _resolve(repo, BOTH)
    _git(repo, "rm", "-q", "--cached", "bin.dat")  # drop their binary file from the result
    assert _run("git commit --no-edit", monkeypatch, capsys, repo) == ""


def test_a_file_deleted_from_the_index_loses_every_added_line(repo, monkeypatch, capsys):
    _git(repo, "rm", "-q", "--cached", "f.txt")
    err = _run("git commit --no-edit", monkeypatch, capsys, repo)
    assert "`f.txt` (2 line(s)" in err


def test_many_lost_lines_are_capped_per_file(repo, monkeypatch, capsys):
    many = [f"line_{i}()" for i in range(hook.MAX_LINES_SHOWN + 3)]
    _git(repo, "merge", "--abort")
    _git(repo, "checkout", "-q", "other")
    _write(repo / "f.txt", "a\nb_theirs\n" + "".join(f"{x}\n" for x in many) + "c\n")
    _git(repo, "commit", "-qam", "more")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "other", check=False)
    _resolve(repo, OURS)
    err = _run("git commit --no-edit", monkeypatch, capsys, repo)
    assert f"({len(many) + 1} line(s):" in err
    assert repr(many[hook.MAX_LINES_SHOWN - 2]) in err
    assert repr(many[-1]) not in err
    assert "; and 4 more)" in err


# --------------------------------------------------------------------------- #
# The counting rule, on its own
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("base, ours, theirs, result, lost", [
    # their new line dropped
    ("a\n", "a\n", "a\nT\n", "a\n", ["T"]),
    # kept
    ("a\n", "a\n", "a\nT\n", "a\nT\n", []),
    # both sides added the same line; git merges it into one copy
    ("a\n", "a\nT\n", "a\nT\n", "a\nT\n", []),
    # ours deleted a base copy, theirs added one: one copy is the 3-way result
    ("T\na\n", "a\n", "T\na\nT\n", "T\na\n", []),
    # a repeated line (a closing brace) their side added, dropped
    ("}\n", "}\n", "}\n}\n", "}\n", ["}"]),
    # their deletions are not this hook's subject
    ("a\nb\n", "a\nb\n", "a\n", "a\nb\n", []),
    # nor is a base line the result dropped that their side only kept
    ("a\nb\n", "a\nb\n", "a\nb\nT\n", "a\nT\n", []),
    # blank lines and trailing whitespace do not count
    ("a\n", "a\n", "a\n\n  \nT  \n", "a\nT\n", []),
    # their side's order is the report's order
    ("a\n", "a\n", "Z\na\nB\n", "a\n", ["Z", "B"]),
])
def test_the_lost_line_rule(base, ours, theirs, result, lost):
    enc = str.encode
    assert hook._lost(enc(base), enc(ours), enc(theirs), enc(result)) == lost


def test_a_missing_base_or_side_counts_as_empty():
    assert hook._lost(None, None, b"T\n", b"") == ["T"]
    assert hook._lost(None, b"T\n", b"T\n", b"T\n") == []


def test_a_cat_file_spec_whose_path_holds_spaces_reads_as_missing(repo):
    """`<spec> missing` is told from `<oid> <type> <size>` by shape, so a path
    whose name splits into three words is not read as a header."""
    clock = hook._Clock()
    got = hook._read_batch(str(repo), ["HEAD:a b c", "HEAD:f.txt"], clock)
    assert got is not None and got[0] is None
    assert got[1] == OURS.encode()


# --------------------------------------------------------------------------- #
# End to end, through the dispatcher
# --------------------------------------------------------------------------- #


# requirement: guard-warnings / A merge commit that drops lines the other side added warns
def test_the_dispatcher_delivers_the_warning_as_context(repo):
    _resolve(repo, OURS)
    payload = json.dumps({"tool_input": {"command": "git commit --no-edit"}, "cwd": str(repo)})
    result = subprocess.run(
        [sys.executable, str(_HOOKS_DIR / "dispatch-bash-pretooluse.py")],
        input=payload, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, "advisory: the call goes ahead"
    out = json.loads(result.stdout)["hookSpecificOutput"]
    assert "permissionDecision" not in out
    assert "[warn-lossy-merge-resolution]" in out["additionalContext"]
    assert "theirs_line()" in out["additionalContext"]


# --------------------------------------------------------------------------- #
# Wiring this hook's cost depends on
# --------------------------------------------------------------------------- #


def _dispatcher_set(name: str) -> set[str]:
    import ast

    tree = ast.parse((_HOOKS_DIR / "dispatch-bash-pretooluse.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            value = node.value.args[0] if isinstance(node.value, ast.Call) else node.value
            return set(ast.literal_eval(value))
    raise AssertionError(f"{name} not found")


def test_the_dispatcher_runs_it_once_per_command():
    """The hook reads wrapper bodies itself; run per part as well, it would
    spend its git calls again for every part that holds a commit."""
    assert _HOOK_FILE in _dispatcher_set("_READS_COMMAND_ONLY")


def test_its_budget_entry_is_its_shared_deadline():
    spec = importlib.util.spec_from_file_location("dispatch_lib_for_lossy", _HOOKS_DIR / "_dispatch_lib.py")
    lib = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lib)
    assert lib.HOOK_WORST_CASE_SECONDS[_HOOK_FILE] == hook.GIT_BUDGET_SECONDS
