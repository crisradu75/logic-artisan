"""Tests for `ask-destructive-git.py` — the one hook that escalates rather than
blocks.

Its whole value is the middle tier: `Bash(git *)` is allowed wholesale and the
launcher runs `--permission-mode auto`, so a force-push to a feature branch and
a `reset --hard` both run unattended today. A hard block would be wrong (both
are legitimate often enough that people would set the override permanently), so
this hook exits 0 and emits `permissionDecision: "ask"` instead.

The two properties most worth pinning are the boundaries: `--force-with-lease`
must NOT prompt (it is the guarded form; prompting on it makes the prompt
routine, which is how a checkpoint stops being read), and an ordinary push or
reset must stay silent.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "ask_destructive_git", _HOOKS_DIR / "ask-destructive-git.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load()


def _run(command: str, monkeypatch, capsys) -> dict | None:
    """Run the hook on `command`; return its parsed stdout JSON, or None."""
    monkeypatch.setattr(
        sys, "stdin", io.StringIO(json.dumps({"tool_input": {"command": command}}))
    )
    code = hook.main()
    assert code == 0, "this hook must never block — it escalates instead"
    out = capsys.readouterr().out.strip()
    return json.loads(out) if out else None


def _reason(payload: dict) -> str:
    assert payload["hookSpecificOutput"]["permissionDecision"] == "ask"
    return payload["hookSpecificOutput"]["permissionDecisionReason"]


# --------------------------------------------------------------------------- #
# Shapes that must prompt
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "command",
    [
        "git push --force origin feature/x",
        "git push -f origin feature/x",
        "git push origin feature/x --force",
        # The gap block-direct-push-to-main leaves open: a force-push to a
        # FEATURE branch is unprotected, and is the shape the unattended
        # orchestrators actually produce.
        "git -C /some/worktree push --force origin feature/x",
        "git --git-dir /x/.git push -f origin feature/x",
    ],
)
def test_force_push_shapes_prompt(command, monkeypatch, capsys):
    payload = _run(command, monkeypatch, capsys)
    assert payload is not None, f"expected an ask for: {command!r}"
    assert "force-push" in _reason(payload)


@pytest.mark.parametrize(
    "command",
    [
        "git reset --hard",
        "git reset --hard HEAD~3",
        "git -C /some/path reset --hard origin/main",
    ],
)
def test_reset_hard_shapes_prompt(command, monkeypatch, capsys):
    payload = _run(command, monkeypatch, capsys)
    assert payload is not None, f"expected an ask for: {command!r}"
    assert "reset --hard" in _reason(payload)


def test_both_shapes_in_one_line_are_reported_together(monkeypatch, capsys):
    payload = _run("git reset --hard && git push -f origin feature/x", monkeypatch, capsys)
    reason = _reason(payload)
    assert "force-push" in reason and "reset --hard" in reason


# --------------------------------------------------------------------------- #
# Shapes that must stay silent -- a prompt people learn to click through is
# worth less than no prompt at all
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "command",
    [
        # The guarded forms. These refuse to clobber an unseen remote update,
        # which is the entire reason to prefer them — prompting here would
        # punish the safer habit.
        "git push --force-with-lease origin feature/x",
        "git push --force-with-lease=feature/x origin feature/x",
        "git push --force-if-includes origin feature/x",
        # Ordinary operations.
        "git push origin feature/x",
        "git reset HEAD~1",
        "git reset --soft HEAD~1",
        "git status",
        "ls -f",
    ],
)
def test_benign_shapes_do_not_prompt(command, monkeypatch, capsys):
    assert _run(command, monkeypatch, capsys) is None, f"unexpected ask for: {command!r}"


def test_a_force_flag_belonging_to_a_later_command_is_not_attributed_to_the_push(
    monkeypatch, capsys
):
    # The `[^&|;]*` tail stops at a shell separator. Without it, the `-f` of an
    # unrelated later command would make an ordinary push look like a force-push.
    assert _run("git push origin feature/x && rm -f /tmp/scratch", monkeypatch, capsys) is None


def test_a_force_push_mentioned_inside_a_quoted_string_does_not_prompt(monkeypatch, capsys):
    # Shared `strip_quoted_spans` behavior: a command quoted inside a commit
    # message or an echoed string is not an invocation.
    assert _run('echo "never run git push --force here"', monkeypatch, capsys) is None


# --------------------------------------------------------------------------- #
# Contract
# --------------------------------------------------------------------------- #


def test_override_env_var_silences_the_prompt(monkeypatch, capsys):
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_GIT", "1")
    assert _run("git push --force origin feature/x", monkeypatch, capsys) is None


def test_the_override_announces_itself_on_a_command_it_suppressed(monkeypatch, capsys):
    # The prompt is gone — that is what the override is for. But a force-push
    # sailing through because of a switch exported weeks ago must not be
    # indistinguishable from one the guard deliberately allowed.
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_GIT", "1")
    monkeypatch.setattr(
        sys, "stdin",
        io.StringIO(json.dumps({"tool_input": {"command": "git push --force origin br"}})),
    )
    assert hook.main() == 0
    err = capsys.readouterr().err
    assert "DISABLED" in err and "ALLOW_DESTRUCTIVE_GIT" in err


def test_the_override_stays_quiet_on_an_ordinary_command(monkeypatch, capsys):
    # Otherwise every `ls` in the session carries the notice, which is how a
    # channel stops being read.
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_GIT", "1")
    monkeypatch.setattr(
        sys, "stdin", io.StringIO(json.dumps({"tool_input": {"command": "git status"}}))
    )
    assert hook.main() == 0
    assert capsys.readouterr().err.strip() == ""


def test_malformed_payload_fails_open(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json at all"))
    assert hook.main() == 0
    assert capsys.readouterr().out.strip() == ""


def test_missing_command_fails_open(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_input": {}})))
    assert hook.main() == 0
    assert capsys.readouterr().out.strip() == ""


def test_reason_names_the_override_so_the_prompt_is_actionable(monkeypatch, capsys):
    payload = _run("git push --force origin feature/x", monkeypatch, capsys)
    reason = _reason(payload)
    assert "ALLOW_DESTRUCTIVE_GIT" in reason
    assert "ask-destructive-git.py" in reason


# --------------------------------------------------------------------------- #
# `gh pr merge` — authorization, which a hook cannot read
#
# Added after two PRs in one session were merged that the user had asked to be
# BUILT, not shipped — once by carrying a "merge and clean" instruction forward
# from an earlier, unrelated task. The prompt is unconditional by design.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "command",
    [
        "gh pr merge 27",
        "gh pr merge 27 --squash",
        "gh pr merge --squash --delete-branch 27",
        "gh pr merge 27 --repo owner/name --squash",
        "gh --repo owner/name pr merge 27",
        "gh pr merge",
    ],
)
def test_a_pr_merge_asks(command):
    assert any("PR merge" in r for r in hook._reasons(command)), command


@pytest.mark.parametrize(
    "command",
    [
        "gh pr view 27",
        "gh pr create --title x",
        "gh pr list --state open",
        "gh pr checks 27",
        "gh run list",
        "git merge main",
        "echo 'gh pr merge 27'",
    ],
)
def test_non_merge_gh_and_local_merge_do_not_ask(command):
    """A prompt that fires on `gh pr view` would be ignored within a day. Local
    `git merge` is deliberately out of scope — it is not outward-facing, and
    `warn-stacked-pr-merge` already covers the case that matters there."""
    assert not any("PR merge" in r for r in hook._reasons(command)), command


def test_a_pr_merge_still_asks_alongside_another_destructive_shape():
    reasons = hook._reasons("git push --force origin x && gh pr merge 27 --squash")
    assert len(reasons) == 2
    assert any("force-push" in r for r in reasons)
    assert any("PR merge" in r for r in reasons)


def test_the_merge_match_does_not_span_a_shell_separator():
    r"""`(?!pr\b)[^\s&|;\n]+` must not let the skip run from a `gh pr view`
    across `&&` into an unrelated `pr merge`-looking phrase."""
    assert not any(
        "PR merge" in r for r in hook._reasons("gh pr view 27 && echo pr merge")
    )
