"""Tests for the block-direct-push-to-main PreToolUse hook.

Unit-tests `_is_direct_push_to_main` directly (no subprocess/git dependency
for the shape-detection cases) and `main()`'s fail-safe behavior on odd
payloads. `_current_branch`'s bare-push branch check is exercised via a
monkeypatch.

Did not previously exist at all — added alongside the `_dispatch_lib`-shared
`GIT_GLOBAL_OPTS`/`strip_quoted_spans` hardening, found via code review to
have zero coverage of its own before this.
"""

import importlib.util
import io
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parent.parent / "block-direct-push-to-main.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("block_direct_push_to_main", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load_module()


# --------------------------------------------------------------------------- #
# _is_direct_push_to_main -- shape detection, no git dependency
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "command",
    [
        "git push origin main",
        "git push origin master",
        "git push origin HEAD:main",
        "git push origin feature/x:main",
        "git push --force origin main",
        "git push -f origin main",
        "git -c core.x=y push origin main",
        "git -C /some/path push origin main",
        "git --work-tree /some/path push origin main",  # regression: space-separated long opt
        "git --git-dir /some/path push origin main",  # regression: space-separated long opt
    ],
)
def test_blocks_every_documented_direct_push_shape(command):
    assert hook._is_direct_push_to_main(command) is True


def test_blocks_a_quoted_c_value_with_a_space(monkeypatch):
    # A checkout path with a space in it is a real, not-exotic shape — a
    # quoted -C value containing one used to break the match entirely before
    # this hook's `_strip_quoted_spans` call was wired to the shared,
    # length-preserving implementation.
    command = 'git -C "/some/checkout path/with a space" push origin main'
    assert hook._is_direct_push_to_main(command) is True


@pytest.mark.parametrize(
    "command",
    [
        "git push origin feature/x",
        "git push -u origin feature/x",
        "git status",
    ],
)
def test_allows_non_main_pushes_and_unrelated_commands(command):
    assert hook._is_direct_push_to_main(command) is False


@pytest.mark.parametrize(
    "command",
    [
        "git push origin refs/heads/main",  # fully-qualified destination
        "git push origin HEAD:refs/heads/master",
        "git push origin +main",  # force refspec
        'git push origin "main"',  # quoted destination
        "git push origin 'master'",
        "git push origin :main",  # DELETING the remote default branch
        "git push origin main:feature/x",  # pushing main's content out
        "git push --force-with-lease origin main",
    ],
)
def test_blocks_refspec_shapes_that_used_to_slip_past(command):
    # Every one of these was ALLOWED before the refspec parser replaced the
    # old substring pattern: it required a literal `main`/`master` immediately
    # after an optional `<src>:` prefix, so a `refs/heads/` qualification, a
    # `+` force marker, or quotes around the target all defeated it.
    assert hook._is_direct_push_to_main(command) is True


@pytest.mark.parametrize(
    "command",
    [
        "git push origin main-refactor",
        "git push origin master-list",
        "git push origin main.old",
        "git push origin maintenance",
        "git push origin mainline",
        "git push origin release/main-ui",
        "git push origin feature/x:main-thing",
        # A flag VALUE that merely mentions main is not a push destination.
        "git push --force-with-lease=origin/main origin feature/x",
    ],
)
def test_does_not_block_branches_that_merely_start_with_main_or_master(command):
    # This hook BLOCKS, so a false positive wedges the workflow with a
    # misleading message. The old `(?:main|master)\b` treated `-` and `.` as
    # word boundaries, so `main-refactor` and `main.old` were both blocked.
    # Refspecs are now compared as whole normalized refs.
    assert hook._is_direct_push_to_main(command) is False


def test_ignores_a_push_belonging_to_a_later_chained_command(monkeypatch):
    # Argument collection stops at a shell separator, so the refspecs of a
    # SUBSEQUENT command are never attributed to this push.
    monkeypatch.setattr(hook, "_current_branch", lambda: "feature/x")
    assert hook._is_direct_push_to_main("git push origin feature/x && echo main") is False


def test_push_with_remote_but_no_refspec_checks_the_current_branch(monkeypatch):
    # `git push origin` on main pushes main. The old bare-push pattern required
    # end-of-string after the flags, so the remote token defeated it entirely.
    monkeypatch.setattr(hook, "_current_branch", lambda: "main")
    assert hook._is_direct_push_to_main("git push origin") is True
    monkeypatch.setattr(hook, "_current_branch", lambda: "feature/x")
    assert hook._is_direct_push_to_main("git push origin") is False


def test_current_branch_passes_a_timeout_and_warns_when_git_is_unusable(monkeypatch, capsys):
    # Without a timeout a hung `git rev-parse` burns the dispatcher's whole
    # budget and takes every other guard down with it. And when the branch
    # can't be resolved the hook allows — that degradation must be visible,
    # not silent, since it is exactly when it cannot vouch for the push.
    captured = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        raise OSError("git not found")

    monkeypatch.setattr(hook.subprocess, "run", fake_run)
    assert hook._current_branch() is None
    assert captured.get("timeout"), "_current_branch must pass a subprocess timeout"
    assert "warn" in capsys.readouterr().err.lower()


def test_bare_push_checks_current_branch(monkeypatch):
    monkeypatch.setattr(hook, "_current_branch", lambda: "main")
    assert hook._is_direct_push_to_main("git push") is True


def test_bare_push_on_feature_branch_is_allowed(monkeypatch):
    monkeypatch.setattr(hook, "_current_branch", lambda: "feature/x")
    assert hook._is_direct_push_to_main("git push") is False


# --------------------------------------------------------------------------- #
# main() -- fail-safe on odd payloads, escape hatch, exit codes
# --------------------------------------------------------------------------- #


def test_main_exits_zero_on_non_object_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("42"))
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


def test_main_exits_zero_on_malformed_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("{not json"))
    assert hook.main() == 0


def test_main_allows_unrelated_command(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('{"tool_input": {"command": "ls"}}'))
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


def test_main_blocks_direct_push_to_main(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.stdin", io.StringIO('{"tool_input": {"command": "git push origin main"}}')
    )
    assert hook.main() == 2
    err = capsys.readouterr().err
    assert "main" in err.lower()


def test_main_respects_allow_push_to_main_escape_hatch(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.stdin", io.StringIO('{"tool_input": {"command": "git push origin main"}}')
    )
    monkeypatch.setattr(hook.os, "environ", {"ALLOW_PUSH_TO_MAIN": "1"})
    assert hook.main() == 0
