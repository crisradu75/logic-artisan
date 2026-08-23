"""Tests for the warn-stray-scratch-artifact PreToolUse hook.

Unit-tests the pure decision logic (`_stray_untracked_paths`) and `main()`'s
fail-safe behavior on odd payloads. The `git status --porcelain` call itself
is not exercised live; `main()`'s git-dependent path is covered via a
monkeypatched `_porcelain_lines`.
"""

import importlib.util
import io
import json
import subprocess
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "hooks" / "warn-stray-scratch-artifact.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("warn_stray_scratch_artifact", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load_module()


# --------------------------------------------------------------------------- #
# _stray_untracked_paths
# --------------------------------------------------------------------------- #

def test_flags_a_mangled_scratchpad_path_at_repo_root():
    lines = ['?? "C:UserssomeuserAppDataLocalTempclaudeC--Code-some-repo036dd2a0scratchpaddiff.txt"']
    assert hook._stray_untracked_paths(lines) == [
        "C:UserssomeuserAppDataLocalTempclaudeC--Code-some-repo036dd2a0scratchpaddiff.txt"
    ]


def test_case_insensitive_match():
    lines = ["?? appdata_dump.txt"]
    assert hook._stray_untracked_paths(lines) == ["appdata_dump.txt"]


def test_ignores_a_real_file_inside_a_directory():
    lines = ["?? apps/operator/src/evaluation/useDelivery.ts"]
    assert hook._stray_untracked_paths(lines) == []


def test_ignores_a_root_level_file_with_no_suspicious_name():
    lines = ["?? README.md", "?? TODO.md"]
    assert hook._stray_untracked_paths(lines) == []


def test_ignores_non_untracked_lines():
    lines = [" M apps/operator/CLAUDE.md", "A  AppDataLocalTempSomething.txt"]
    # "A " (staged-add) is not "??" (untracked) -- already staged/tracked, not a stray drop.
    assert hook._stray_untracked_paths(lines) == []


def test_empty_status_yields_no_stray_paths():
    assert hook._stray_untracked_paths([]) == []


# --------------------------------------------------------------------------- #
# main() -- fail-safe on odd payloads (no crash, no output, exit 0)
# --------------------------------------------------------------------------- #

def test_main_exits_zero_on_non_object_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("42"))
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


def test_main_exits_zero_on_malformed_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("{not json"))
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


def test_main_exits_zero_on_non_dict_tool_input(monkeypatch, capsys):
    # A malformed/unexpected PreToolUse payload shape where tool_input itself
    # isn't an object (e.g. a bare string) must not crash `.get()` on it.
    monkeypatch.setattr("sys.stdin", io.StringIO('{"tool_input": "git add foo"}'))
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


def test_main_no_op_on_unrelated_command(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('{"tool_input": {"command": "git status"}}'))
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


def test_main_warns_when_a_stray_artifact_is_present(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('{"tool_input": {"command": "git add openspec/"}}'))
    monkeypatch.setattr(hook, "_porcelain_lines", lambda cwd=None: ['?? "AppDataLocalTempscratchpaddiff.txt"'])
    assert hook.main() == 0  # warn-only, never blocks
    err = capsys.readouterr().err
    assert "warn-stray-scratch-artifact" in err
    assert "AppDataLocalTempscratchpaddiff.txt" in err


def test_main_warns_on_chained_command(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('{"tool_input": {"command": "cd repo && git add ."}}'))
    monkeypatch.setattr(hook, "_porcelain_lines", lambda cwd=None: ["?? scratchpad_dump.txt"])
    assert hook.main() == 0
    assert "scratchpad_dump.txt" in capsys.readouterr().err


def test_main_warns_on_commit_behind_a_space_separated_long_global_option(monkeypatch, capsys):
    # Regression: `--work-tree <path>` (space-separated, not `=`) used to
    # bypass the detection entirely — the hook fired exit 0 with no output.
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO('{"tool_input": {"command": "git --work-tree /some/other/repo commit -m x"}}'),
    )
    monkeypatch.setattr(hook, "_porcelain_lines", lambda cwd=None: ["?? scratchpad_dump.txt"])
    assert hook.main() == 0
    assert "scratchpad_dump.txt" in capsys.readouterr().err


def test_main_warns_on_commit_behind_a_quoted_c_value_with_a_space(monkeypatch, capsys):
    # Regression: a quoted `-c`/`-C` value containing a space (a real,
    # not-exotic shape — e.g. a checkout path with a space in it) used to
    # break the match entirely, since this hook never stripped quoted spans
    # before matching.
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(
            '{"tool_input": {"command": "git -C \\"/some/checkout path/with a space\\" commit -m x"}}'
        ),
    )
    monkeypatch.setattr(hook, "_porcelain_lines", lambda cwd=None: ["?? scratchpad_dump.txt"])
    assert hook.main() == 0
    assert "scratchpad_dump.txt" in capsys.readouterr().err


@pytest.mark.parametrize(
    "command",
    [
        "git.exe add openspec/",
        "git.cmd commit -m x",
        "GIT.EXE add .",
        "GIT commit -m x",
        "Git.Exe -C /some/worktree add .",
    ],
)
def test_main_fires_on_every_executable_spelling(command, monkeypatch, capsys):
    """The second `GIT_CMD` consumer, which the first pass at this left behind.

    `test_ask_destructive_git.py` closed the composition gap for one of the two
    hooks that build a matcher from `GIT_CMD` + `GIT_GLOBAL_OPTS` + a
    subcommand, and its docstring says "nothing proved the GUARD" as though the
    class were closed. It was closed for one guard. Every case in THIS file was
    a bare lowercase `git`, so the constant test was again the only thing
    standing behind the composition here.

    Reachable by ordinary use rather than evasion: PowerShell is a primary shell
    for this harness and its tab-completion emits `git.exe`.
    """
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps({"tool_input": {"command": command}}))
    )
    monkeypatch.setattr(hook, "_porcelain_lines", lambda cwd=None: ["?? scratchpad_dump.txt"])
    assert hook.main() == 0  # warn-only, never blocks
    assert "scratchpad_dump.txt" in capsys.readouterr().err, (
        f"an alternative executable spelling must not walk past the guard: {command!r}"
    )


def test_an_alternative_spelling_of_an_unrelated_command_stays_silent(monkeypatch, capsys):
    """Non-vacuity: the case-folded command name must not turn this into a hook
    that warns on any line containing `git`. `status` is not `add`/`commit`."""
    monkeypatch.setattr(
        "sys.stdin", io.StringIO('{"tool_input": {"command": "GIT.EXE status"}}')
    )
    monkeypatch.setattr(hook, "_porcelain_lines", lambda cwd=None: ["?? scratchpad_dump.txt"])
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


def test_main_silent_when_nothing_stray_is_present(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('{"tool_input": {"command": "git commit -m x"}}'))
    monkeypatch.setattr(hook, "_porcelain_lines", lambda cwd=None: ["?? README.md"])
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


# --------------------------------------------------------------------------- #
# _porcelain_lines -- the one function that shells out
# --------------------------------------------------------------------------- #

def test_porcelain_lines_returns_none_on_subprocess_error(monkeypatch):
    def _raise(*args, **kwargs):
        raise OSError("git not found")
    monkeypatch.setattr(hook.subprocess, "run", _raise)
    assert hook._porcelain_lines() is None


def test_porcelain_lines_returns_none_on_nonzero_exit(monkeypatch):
    class _FakeResult:
        returncode = 128
        stdout = ""
    monkeypatch.setattr(hook.subprocess, "run", lambda *a, **kw: _FakeResult())
    assert hook._porcelain_lines() is None


def test_porcelain_lines_splits_real_stdout(monkeypatch):
    class _FakeResult:
        returncode = 0
        stdout = "?? README.md\n?? scratchpad_dump.txt\n"
    monkeypatch.setattr(hook.subprocess, "run", lambda *a, **kw: _FakeResult())
    assert hook._porcelain_lines() == ["?? README.md", "?? scratchpad_dump.txt"]


# --------------------------------------------------------------------------- #
# multiple simultaneous stray matches
# --------------------------------------------------------------------------- #

def test_stray_untracked_paths_with_multiple_matches():
    lines = ["?? scratchpad_a.txt", "?? README.md", "?? appdata_b.txt"]
    assert hook._stray_untracked_paths(lines) == ["scratchpad_a.txt", "appdata_b.txt"]


def test_ignores_backslash_separated_suspicious_path():
    lines = [r"?? scratchpad\file.txt", r'?? "AppData\dump.txt"']
    assert hook._stray_untracked_paths(lines) == []


def test_git_state_is_resolved_in_the_sessions_cwd(monkeypatch):
    """Untested before — reverting the `-C` survived the whole scope. A session
    inside a worktree had its scratch artifacts checked against the primary
    clone: reporting on files it is not touching, missing the ones it is."""
    seen = {}

    def _fake(cmd, **kwargs):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", _fake)
    hook._porcelain_lines("/session/worktree")
    assert seen["cmd"][:3] == ["git", "-C", "/session/worktree"], seen["cmd"]


def test_a_missing_cwd_degrades_without_crashing(monkeypatch):
    """`payload["cwd"]` can be stale, absent, or not a string."""
    for cwd in (None, "", "/definitely/not/here"):
        assert hook._porcelain_lines(cwd) is None or isinstance(hook._porcelain_lines(cwd), list)
