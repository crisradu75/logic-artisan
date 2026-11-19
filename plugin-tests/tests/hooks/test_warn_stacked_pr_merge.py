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
import json
import subprocess
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "hooks" / "warn-stacked-pr-merge.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("warn_stacked_pr_merge", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load_module()


# --------------------------------------------------------------------------- #
# _wants_stacked_check
# --------------------------------------------------------------------------- #

# requirement: guard-warnings / Deleting the base of a stacked pull request warns
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


@pytest.mark.parametrize("exe", ["gh", "gh.exe", "gh.cmd", "GH", "GH.EXE", "Gh.Cmd"])
def test_wants_check_covers_every_runnable_gh_spelling(exe):
    """`_GH_MERGE` was the last bare command-token regex in the tree.

    `ask-destructive-git._GH_PR_MERGE` already carried the extension forms for
    the Windows reason `GIT_CMD` was introduced, so `gh.exe pr merge
    --delete-branch` prompted there and was invisible here — in the tool this
    plugin uses for every PR operation.
    """
    assert hook._wants_stacked_check(f"{exe} pr merge 305 --squash --delete-branch")


def test_wants_check_gh_spelling_does_not_over_match():
    """The allow half: a longer name must not satisfy the widened token."""
    assert not hook._wants_stacked_check("mygh pr merge 305 --delete-branch")
    assert not hook._wants_stacked_check("gh.py pr merge 305 --delete-branch")


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


# --------------------------------------------------------------------------- #
# `gh pr list` output is untrusted the same way `tool_input` is
# --------------------------------------------------------------------------- #


def test_a_non_dict_element_in_gh_output_does_not_crash(monkeypatch, capsys):
    # `children` was isinstance-checked as a list, but never its ELEMENTS —
    # `c.get('number')` on a non-dict element raises AttributeError, the exact
    # crash class this file was just fixed for the `tool_input` check, one call
    # away. `gh`'s stdout crosses a version/config/alias boundary this hook
    # doesn't control, so it must be treated as untrusted too.
    def fake_gh(args):
        if args[:2] == ["pr", "view"]:
            return "feature/base"
        return '[1, "not-a-dict", {"number": 42, "title": "child"}]'

    monkeypatch.setattr(hook, "_gh", fake_gh)
    monkeypatch.setattr(hook.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO('{"tool_input": {"command": "gh pr merge 305 --squash --delete-branch"}}'),
    )
    assert hook.main() == 0
    err = capsys.readouterr().err
    assert "#42" in err


def test_all_non_dict_elements_yields_no_warning_not_a_crash(monkeypatch, capsys):
    # No usable PR number anywhere in the list — a warning naming no PRs would
    # help nobody, so this must be a clean no-op, not an empty-subject message.
    def fake_gh(args):
        if args[:2] == ["pr", "view"]:
            return "feature/base"
        return '[1, "not-a-dict"]'

    monkeypatch.setattr(hook, "_gh", fake_gh)
    monkeypatch.setattr(hook.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO('{"tool_input": {"command": "gh pr merge 305 --squash --delete-branch"}}'),
    )
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


# --------------------------------------------------------------------------- #
# The command parsing, edge by edge
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "cmd",
    [
        "gh pr merge 3 --foo-d",              # `-d` inside another flag
        "gh pr merge 3 -bd",                  # `-b` takes a value: a body of "d", not a delete
        "gh pr merge 3 -td",                  # `-t` takes a value: a subject of "d"
        "gh pr merge 3 --delete-branches",
        "gh pr merge 3 --delete-branchx",
    ],
)
def test_wants_check_does_not_match_lookalike_flags(cmd):
    assert not hook._wants_stacked_check(cmd)


# gh's flag parser clusters short boolean flags, so these all delete the branch (review of #554).
@pytest.mark.parametrize("flags", ["-sd", "-ds", "-md", "-rd", "-dd", "-d -s"])
def test_wants_check_clustered_short_delete_flags(flags):
    assert hook._wants_stacked_check(f"gh pr merge 3 {flags}")


def test_wants_check_delete_branch_flag_at_the_very_start_or_end():
    assert hook._wants_stacked_check("gh pr merge 3 -d")
    assert hook._wants_stacked_check("gh pr merge -d 3")
    assert hook._wants_stacked_check("gh pr merge 3 --delete-branch")


def test_wants_check_gh_must_start_a_word_and_pr_merge_must_end_one():
    assert not hook._wants_stacked_check("xgh pr merge 3 -d")
    assert not hook._wants_stacked_check("gh pr mergeall 3 -d")
    assert not hook._wants_stacked_check("gh pr  3 merge -d")


def test_wants_check_needs_both_halves_not_either():
    assert not hook._wants_stacked_check("gh pr merge 3 --squash")        # no delete flag
    assert not hook._wants_stacked_check("gh pr view 3 --delete-branch")  # not a merge


def test_wants_check_only_the_exact_false_values_cancel_the_flag():
    assert hook._wants_stacked_check("gh pr merge 3 --delete-branch=falsey")


def test_target_number_must_stand_alone_between_spaces():
    assert hook._target_pr_number("gh pr merge 42abc -d") is None
    assert hook._target_pr_number("gh pr merge abc42 -d") is None
    assert hook._target_pr_number("gh pr merge -d 42") == "42"
    assert hook._target_pr_number("gh pr merge 42") == "42"


@pytest.mark.parametrize("op", ["&&", "||", ";", "|"])
def test_target_stops_at_every_shell_operator(op):
    assert hook._target_pr_number(f"gh pr merge -d {op} echo 99") is None
    assert hook._target_pr_number(f"gh pr merge 7 -d {op} echo 99") == "7"


def test_target_of_a_command_that_is_not_a_merge_is_none():
    assert hook._target_pr_number("git status 42") is None
    assert hook._target_pr_number("gh pr view 42") is None


# --------------------------------------------------------------------------- #
# main(): every path that resolves a branch and reads gh's answer
# --------------------------------------------------------------------------- #

MERGE = "gh pr merge 305 --squash --delete-branch"
MERGE_HERE = "gh pr merge --squash --delete-branch"


def _drive(monkeypatch, capsys, command, gh=None, branch="feature/here", which="/usr/bin/gh", cwd=None):
    """Run main() with `gh` answers from `gh(args)` and the current branch `branch`.

    Returns (exit code, stdout, stderr, gh calls, current-branch calls)."""
    gh_calls, branch_calls = [], []

    def fake_gh(args):
        gh_calls.append(list(args))
        return gh(args)

    def fake_branch(cwd_arg=None):
        branch_calls.append(cwd_arg)
        return branch

    monkeypatch.setattr(hook, "_gh", fake_gh)
    monkeypatch.setattr(hook, "_current_branch", fake_branch)
    monkeypatch.setattr(hook.shutil, "which", lambda name: which)
    payload = {"tool_input": {"command": command}}
    if cwd is not None:
        payload["cwd"] = cwd
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    code = hook.main()
    out = capsys.readouterr()
    return code, out.out, out.err, gh_calls, branch_calls


def _children(*numbers):
    return json.dumps([{"number": n, "title": f"child {n}"} for n in numbers])


def _answer(head="feature/base", listing=None):
    def gh(args):
        return head if args[:2] == ["pr", "view"] else listing
    return gh


# requirement: guard-warnings / Deleting the base of a stacked pull request warns
def test_an_explicit_number_asks_gh_for_that_prs_head_then_for_its_children(monkeypatch, capsys):
    code, out, err, calls, branch_calls = _drive(
        monkeypatch, capsys, MERGE, _answer(listing=_children(42, 43)))
    assert code == 0 and out == ""
    assert calls == [
        ["pr", "view", "305", "--json", "headRefName", "-q", ".headRefName"],
        ["pr", "list", "--base", "feature/base", "--state", "open", "--json", "number,title"],
    ]
    assert branch_calls == []                       # the number named the PR; git was not asked
    assert err.startswith("[warn-stacked-pr-merge] 'feature/base' is the base of open PR(s) #42, #43. ")
    assert "Retarget FIRST" in err


# requirement: guard-warnings / Deleting the base of a stacked pull request warns
def test_no_number_asks_git_for_the_session_branch_in_the_session_directory(monkeypatch, capsys):
    code, out, err, calls, branch_calls = _drive(
        monkeypatch, capsys, MERGE_HERE, _answer(listing=_children(7)), branch="feature/here", cwd="/work/tree")
    assert code == 0 and out == ""
    assert branch_calls == ["/work/tree"]
    assert calls == [["pr", "list", "--base", "feature/here", "--state", "open", "--json", "number,title"]]
    assert "'feature/here' is the base of open PR(s) #7." in err


@pytest.mark.parametrize("cwd", [None, "", 5, ["x"]])
def test_a_missing_or_odd_cwd_asks_git_without_a_directory(monkeypatch, capsys, cwd):
    _code, _out, err, _calls, branch_calls = _drive(
        monkeypatch, capsys, MERGE_HERE, _answer(listing=_children(7)), cwd=cwd)
    assert branch_calls == [None]
    assert "#7" in err


def test_nothing_is_asked_of_gh_for_a_command_that_is_not_a_delete_merge(monkeypatch, capsys):
    for cmd in ("git status", "gh pr merge 305 --squash", "gh pr merge 305 --delete-branch=false"):
        code, out, err, calls, branch_calls = _drive(monkeypatch, capsys, cmd, _answer(listing=_children(42)))
        assert (code, out, err, calls, branch_calls) == (0, "", "", [], []), cmd


def test_without_gh_installed_nothing_is_asked_and_nothing_is_said(monkeypatch, capsys):
    code, out, err, calls, branch_calls = _drive(
        monkeypatch, capsys, MERGE, _answer(listing=_children(42)), which=None)
    assert (code, out, err, calls, branch_calls) == (0, "", "", [], [])


@pytest.mark.parametrize("head", [None, "", "HEAD"])
def test_a_head_that_cannot_be_resolved_or_is_detached_is_silent_and_asks_no_more(monkeypatch, capsys, head):
    code, out, err, calls, _b = _drive(monkeypatch, capsys, MERGE, _answer(head=head, listing=_children(42)))
    assert (code, out, err) == (0, "", "")
    assert [c[1] for c in calls] == ["view"]        # no `pr list` for a branch that is not a branch


def test_a_detached_head_without_a_number_is_silent_too(monkeypatch, capsys):
    code, out, err, calls, _b = _drive(
        monkeypatch, capsys, MERGE_HERE, _answer(listing=_children(42)), branch="HEAD")
    assert (code, out, err, calls) == (0, "", "", [])


@pytest.mark.parametrize(
    "listing",
    [
        None,                                   # gh failed
        "",                                     # gh printed nothing
        "{not json",                            # not JSON
        "[]",                                   # no children
        '{"number": 42}',                       # JSON, but not a list
        '"a string"',
        "42",
        "[1, 2]",                               # elements that are not records
        '[{"title": "no number"}]',             # a record with no number
        '[{"number": 0}]',                      # a falsy number names nothing
        "[null]",
    ],
)
def test_an_answer_that_names_no_child_is_silent_and_never_crashes(monkeypatch, capsys, listing):
    code, out, err, _calls, _b = _drive(monkeypatch, capsys, MERGE, _answer(listing=listing))
    assert (code, out, err) == (0, "", "")


def test_the_warning_names_every_child_in_order_and_skips_the_unnamed(monkeypatch, capsys):
    listing = json.dumps([{"number": 9}, "junk", {"title": "x"}, {"number": 12}, {"number": 3}])
    _code, out, err, _calls, _b = _drive(monkeypatch, capsys, MERGE, _answer(listing=listing))
    assert out == ""                                # the warning is on stderr, never stdout
    assert "open PR(s) #9, #12, #3. " in err


# --------------------------------------------------------------------------- #
# The two subprocess helpers
# --------------------------------------------------------------------------- #

class _Done:
    def __init__(self, code, stdout):
        self.returncode, self.stdout = code, stdout


def _fake_run(monkeypatch, result=None, raises=None):
    seen = {}

    def run(argv, **kw):
        seen["argv"], seen["kw"] = argv, kw
        if raises is not None:
            raise raises
        return result

    monkeypatch.setattr(hook.subprocess, "run", run)
    return seen


def test_gh_returns_stripped_stdout_and_runs_gh_with_a_timeout(monkeypatch):
    seen = _fake_run(monkeypatch, _Done(0, "  hello\n"))
    assert hook._gh(["pr", "list"]) == "hello"
    assert seen["argv"] == ["gh", "pr", "list"]
    assert seen["kw"]["timeout"] == hook._GH_TIMEOUT_SECONDS
    # Two gh calls can happen in one run, inside a handler shared with other hooks.
    assert 0 < hook._GH_TIMEOUT_SECONDS * 2 <= 10


def test_gh_is_none_on_a_nonzero_exit_even_with_output(monkeypatch):
    _fake_run(monkeypatch, _Done(1, "partial"))
    assert hook._gh(["pr", "list"]) is None


@pytest.mark.parametrize("exc", [FileNotFoundError("no gh"), subprocess.TimeoutExpired("gh", 4)])
def test_gh_is_none_when_it_cannot_run_or_times_out(monkeypatch, exc):
    _fake_run(monkeypatch, raises=exc)
    assert hook._gh(["pr", "list"]) is None


def test_current_branch_asks_git_in_the_given_directory(monkeypatch):
    seen = _fake_run(monkeypatch, _Done(0, "feature/x\n"))
    assert hook._current_branch("/work/tree") == "feature/x"
    assert seen["argv"] == ["git", "-C", "/work/tree", "rev-parse", "--abbrev-ref", "HEAD"]
    assert seen["kw"]["timeout"] > 0


def test_current_branch_without_a_directory_has_no_dash_c(monkeypatch):
    seen = _fake_run(monkeypatch, _Done(0, "main\n"))
    assert hook._current_branch() == "main"
    assert seen["argv"] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]
    assert hook._current_branch("") == "main"
    assert seen["argv"] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]


def test_current_branch_is_none_on_failure_or_when_git_cannot_run(monkeypatch):
    _fake_run(monkeypatch, _Done(128, "fatal: not a git repository"))
    assert hook._current_branch("/x") is None
    _fake_run(monkeypatch, raises=OSError("no git"))
    assert hook._current_branch("/x") is None
    _fake_run(monkeypatch, raises=subprocess.TimeoutExpired("git", 3))
    assert hook._current_branch("/x") is None
