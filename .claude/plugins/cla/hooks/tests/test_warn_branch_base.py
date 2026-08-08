"""Tests for the warn-branch-base PreToolUse hook.

Unit-tests `main()`'s detection + fail-safe behavior via a monkeypatched
`subprocess.run` (no real git dependency). Did not previously exist at all —
added alongside the `_dispatch_lib`-shared `GIT_GLOBAL_OPTS`/
`strip_quoted_spans` hardening, found via code review to have zero coverage
of its own before this — including the branch-name-extraction correctness
that motivated making `strip_quoted_spans` length-preserving in the first
place (a quoted branch name must still print as its real text, not the
scan-time placeholder).
"""

import importlib.util
import io
import json
import subprocess
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parent.parent / "warn-branch-base.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("warn_branch_base", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load_module()


class _FakeHead:
    def __init__(self, branch: str, returncode: int = 0):
        self.stdout = branch
        self.returncode = returncode


def _run_with_head(branch: str, returncode: int = 0):
    def _fake_run(*args, **kwargs):
        return _FakeHead(branch, returncode)

    return _fake_run


# --------------------------------------------------------------------------- #
# main() -- fail-safe on odd payloads
# --------------------------------------------------------------------------- #


def test_main_exits_zero_on_non_object_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("42"))
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


def test_main_exits_zero_on_malformed_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("{not json"))
    assert hook.main() == 0


def test_main_exits_zero_on_non_dict_tool_input(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('{"tool_input": "git checkout -b x"}'))
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


def test_main_no_op_on_unrelated_command(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('{"tool_input": {"command": "git status"}}'))
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


# --------------------------------------------------------------------------- #
# main() -- branch-create detection + base-branch warning
# --------------------------------------------------------------------------- #


def test_main_warns_when_branching_off_a_non_master_base(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.stdin", io.StringIO('{"tool_input": {"command": "git checkout -b feature/new"}}')
    )
    monkeypatch.setattr(hook.subprocess, "run", _run_with_head("feature/old"))
    assert hook.main() == 0  # warn-only, never blocks
    err = capsys.readouterr().err
    assert "feature/new" in err
    assert "feature/old" in err


@pytest.mark.parametrize("base", ["master", "main", "trunk"])
def test_main_silent_when_branching_off_the_repos_own_base_branch(monkeypatch, capsys, base):
    # Parametrized over the base-branch NAME because the hook no longer assumes
    # `master`: it asks `default_base_branch()`. The bug this covers is a
    # `main`-default repo, where the old hardcoded comparison warned on every
    # single branch creation — including the correct `main` -> `feature/x` —
    # which trains the reader to ignore the hook.
    monkeypatch.setattr(hook, "default_base_branch", lambda: base)
    monkeypatch.setattr(
        "sys.stdin", io.StringIO('{"tool_input": {"command": "git checkout -b feature/new"}}')
    )
    monkeypatch.setattr(hook.subprocess, "run", _run_with_head(base))
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


def test_main_names_the_repos_actual_base_branch_in_the_warning(monkeypatch, capsys):
    # The remediation the message suggests must be runnable in THIS repo — a
    # `git switch master` hint in a repo with no `master` ref is worse than no
    # hint at all.
    monkeypatch.setattr(hook, "default_base_branch", lambda: "main")
    monkeypatch.setattr(
        "sys.stdin", io.StringIO('{"tool_input": {"command": "git checkout -b feature/new"}}')
    )
    monkeypatch.setattr(hook.subprocess, "run", _run_with_head("feature/old"))
    assert hook.main() == 0
    err = capsys.readouterr().err
    assert "git switch main" in err
    assert "master" not in err


def test_main_silent_on_detached_head(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.stdin", io.StringIO('{"tool_input": {"command": "git checkout -b feature/new"}}')
    )
    monkeypatch.setattr(hook.subprocess, "run", _run_with_head("HEAD"))
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


def test_main_warns_on_git_switch_create_form(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.stdin", io.StringIO('{"tool_input": {"command": "git switch -c feature/new"}}')
    )
    monkeypatch.setattr(hook.subprocess, "run", _run_with_head("feature/old"))
    assert hook.main() == 0
    assert "feature/new" in capsys.readouterr().err


@pytest.mark.parametrize(
    "command",
    [
        "git --work-tree /some/other/repo checkout -b feature/new",  # regression: space-separated long opt
        "git --git-dir /some/other/repo/.git checkout -b feature/new",  # regression: space-separated long opt
    ],
)
def test_main_warns_behind_a_space_separated_long_global_option(monkeypatch, capsys, command):
    payload = json.dumps({"tool_input": {"command": command}})
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    monkeypatch.setattr(hook.subprocess, "run", _run_with_head("feature/old"))
    assert hook.main() == 0
    assert "feature/new" in capsys.readouterr().err


def test_main_prints_the_real_branch_name_when_it_was_quoted(monkeypatch, capsys):
    # This is the specific case that motivated making `strip_quoted_spans`
    # length-preserving: a quoted branch name must still print as its real
    # text (re-sliced from the original command), not the scan-time
    # placeholder that a naive collapse-to-`''` would have left behind.
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO("""{"tool_input": {"command": "git checkout -b 'feature/quoted'"}}"""),
    )
    monkeypatch.setattr(hook.subprocess, "run", _run_with_head("feature/old"))
    assert hook.main() == 0
    err = capsys.readouterr().err
    assert "feature/quoted" in err
    assert "#" not in err  # the placeholder character must never leak into output


def test_main_warns_behind_a_quoted_c_value_with_a_space(monkeypatch, capsys):
    # A real, not-exotic shape: a checkout path with a space in it.
    command = (
        'git -C "/some/checkout path/with a space" checkout -b feature/new'
    )
    payload = json.dumps({"tool_input": {"command": command}})
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    monkeypatch.setattr(hook.subprocess, "run", _run_with_head("feature/old"))
    assert hook.main() == 0
    assert "feature/new" in capsys.readouterr().err


def test_main_silent_when_git_rev_parse_fails(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.stdin", io.StringIO('{"tool_input": {"command": "git checkout -b feature/new"}}')
    )
    monkeypatch.setattr(hook.subprocess, "run", _run_with_head("feature/old", returncode=128))
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


def test_main_silent_on_subprocess_error(monkeypatch, capsys):
    def _raise(*args, **kwargs):
        raise OSError("git not found")

    monkeypatch.setattr(
        "sys.stdin", io.StringIO('{"tool_input": {"command": "git checkout -b feature/new"}}')
    )
    monkeypatch.setattr(hook.subprocess, "run", _raise)
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("command", [
    "git checkout -b feature/new",
    "git checkout -B feature/new",
    "git checkout --orphan feature/new",
    "git switch -c feature/new",
    "git switch -C feature/new",
    "git switch --create feature/new",
    "git -C /some/path switch -c feature/new",
    "git --work-tree /some/path checkout -b feature/new",
])
def test_warns_on_every_create_and_switch_form(monkeypatch, capsys, command):
    # The create-form set must match `guard-worktree-isolation.py`'s
    # `_BRANCH_CREATE`, so the two hooks agree on what "creating a branch"
    # means. `-B`, `--orphan` and `switch -C` were previously missed here
    # while the guard caught them — `git checkout -B feature/x` warned in one
    # hook and not the other.
    monkeypatch.setattr(
        "sys.stdin", io.StringIO('{"tool_input": {"command": %s}}' % json.dumps(command))
    )
    monkeypatch.setattr(hook.subprocess, "run", _run_with_head("feature/old"))
    assert hook.main() == 0
    assert "feature/new" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# cwd resolution (MD-6, reported by a consuming repo)
# --------------------------------------------------------------------------- #


def test_git_state_is_resolved_in_the_sessions_cwd_not_the_hook_process(monkeypatch, capsys):
    """`payload["cwd"]` is authoritative and was already parsed for the command.

    Without `-C`, a session inside `.claude/worktrees/<task>` with the hook
    process rooted in the primary clone on the base branch reads
    `current == base`, so no warning fires — in exactly the
    `/cla:new-worktree` + `claw` flow this plugin promotes. Silent and
    one-directional, which is the worst shape for an advisory hook."""
    seen = {}

    def _fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "feature/other\n", "")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    monkeypatch.setattr(hook, "default_base_branch", lambda cwd=None: "main")
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(json.dumps({
            "tool_input": {"command": "git checkout -b feature/x"},
            "cwd": "/session/worktree",
        })),
    )
    assert hook.main() == 0
    assert seen["cmd"][:3] == ["git", "-C", "/session/worktree"], seen["cmd"]
