"""Tests for the warn-stacked-pr-merge PreToolUse hook.

Unit-tests the pure decision logic — does a command warrant the stacked-child
check (`_wants_stacked_check`), and which PR number does it target
(`_target_pr_number`). The gh/git network calls in `main()` are not exercised; the
value here is pinning the command-parsing gotchas the hook was written to handle:
`feature/foo-2` must not read as PR "2", a bare number in a chained `&& …` command
is not the merge target, and `--delete-branch=false` is not a hazard.
"""

import importlib.util
import io
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parent.parent / "warn-stacked-pr-merge.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("warn_stacked_pr_merge", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load_module()


# --------------------------------------------------------------------------- #
# _wants_stacked_check
# --------------------------------------------------------------------------- #

def test_wants_check_explicit_number_and_delete_branch():
    assert hook._wants_stacked_check("gh pr merge 305 --squash --delete-branch")


def test_wants_check_short_delete_flag():
    assert hook._wants_stacked_check("gh pr merge --squash -d")


def test_wants_check_requires_delete_branch():
    assert not hook._wants_stacked_check("gh pr merge 42 --squash")


def test_wants_check_requires_gh_pr_merge():
    assert not hook._wants_stacked_check("git merge 305 --delete-branch")
    assert not hook._wants_stacked_check("gh pr view 305")
    assert not hook._wants_stacked_check("echo gh pr merge is a string")  # not the command


def test_wants_check_delete_branch_false_is_not_a_hazard():
    assert not hook._wants_stacked_check("gh pr merge 305 --delete-branch=false")
    assert not hook._wants_stacked_check("gh pr merge 305 --delete-branch=0")
    assert not hook._wants_stacked_check("gh pr merge 305 --delete-branch=no")


def test_wants_check_delete_branch_true_is_a_hazard():
    assert hook._wants_stacked_check("gh pr merge 305 --delete-branch=true")


# --------------------------------------------------------------------------- #
# _target_pr_number
# --------------------------------------------------------------------------- #

def test_target_leading_number():
    assert hook._target_pr_number("gh pr merge 305 --squash --delete-branch") == "305"


def test_target_trailing_number():
    assert hook._target_pr_number("gh pr merge --delete-branch 42") == "42"


def test_target_no_positional_is_none():
    assert hook._target_pr_number("gh pr merge --squash -d") is None


def test_target_branch_name_digit_is_not_a_pr_number():
    # feature/foo-2 must NOT be read as PR "2" (the documented footgun).
    assert hook._target_pr_number("gh pr merge feature/foo-2 --delete-branch") is None


def test_target_ignores_number_in_chained_command():
    # A bare number after && / ; belongs to a different command, not the merge.
    assert hook._target_pr_number("gh pr merge --squash -d && echo 99") is None
    assert hook._target_pr_number("gh pr merge 305 --delete-branch && echo 99") == "305"
    assert hook._target_pr_number("gh pr merge --squash -d ; sleep 99") is None


# --------------------------------------------------------------------------- #
# main() — fail-safe on odd payloads (no crash, no output, exit 0)
# --------------------------------------------------------------------------- #

def test_main_exits_zero_on_non_object_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("42"))  # valid JSON, not an object
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


def test_main_exits_zero_on_malformed_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("{not json"))
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


def test_main_no_op_on_unrelated_command(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('{"tool_input": {"command": "git status"}}'))
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "payload",
    [
        '{"tool_input": "git status"}',   # a string
        '{"tool_input": ["git status"]}',  # a list
        '{"tool_input": 7}',
        '{"tool_input": null}',
        "{}",                              # absent entirely
    ],
)
def test_main_exits_zero_on_a_non_dict_tool_input(payload, monkeypatch, capsys):
    # `(payload.get("tool_input") or {}).get(...)` passed the truthiness test on
    # a non-dict and then raised AttributeError. The blast radius was far wider
    # than this hook: `run_hook` catches it, the dispatcher exits 1, and EVERY
    # Bash call in the session gets a hook-error traceback — from a hook that
    # only ever warns.
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


def test_main_exits_zero_on_a_non_string_command(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('{"tool_input": {"command": 42}}'))
    assert hook.main() == 0
    assert capsys.readouterr().err == ""
