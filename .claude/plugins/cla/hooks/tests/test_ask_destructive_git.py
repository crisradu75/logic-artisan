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
        # Backslash line continuation, at each separator position. These were a
        # SILENT BYPASS of the force-push guard until `_SEP`/`_TAIL` replaced a
        # plain `\s` and a flat `\n` exclusion — a multi-line invocation is
        # ordinary, and a continued newline is a joined line, not a boundary.
        "git push \\\n--force origin feature/x",
        "git \\\npush --force origin feature/x",
        "git push origin feature/x \\\n--force",
        "git \\\npush origin +feat:feat",
        "git push \\\r\n  --force origin feature/x",
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
        "git reset \\\n  --hard",
        "git \\\n reset --hard HEAD~1",
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
#
# These go through `_run()` -> `main()` like every other test in this file, not
# through the private `_reasons` helper: `main()` is what the dispatcher
# consumes, and a first draft that stopped at `_reasons` would have stayed green
# through any change to the emit block.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "command",
    [
        "gh pr merge 27",
        "gh pr merge 27 --squash",
        "gh pr merge --squash --delete-branch 27",
        "gh pr merge 27 --repo owner/name --squash",
        "gh --repo owner/name pr merge 27",
        # A global-option VALUE beginning with `pr`. `(?!pr\b)` rejected the
        # token (word boundary before the `-`), so it could neither be skipped
        # nor complete the match, and this was a silent miss.
        "gh --repo pr-tools/x pr merge 27",
        # Ordinary spellings on this repo's primary platform; bare `\bgh\s`
        # missed both entirely.
        "gh.exe pr merge 27",
        "gh.cmd pr merge 27",
        "gh.bat pr merge 27",
        "gh.ps1 pr merge 27",
        # The extension group exists because Windows is the primary platform,
        # and that shell resolves these case-insensitively — a case-sensitive
        # group would have been the same inconsistency one more time.
        "gh.EXE pr merge 27",
        "gh.Cmd pr merge 27",
        "gh.com pr merge 27",
        "/usr/bin/gh pr merge 27",
        "gh pr merge",
        # An option value that IS exactly `pr`. The first fix used a lookahead
        # that could not skip such a token, so this stayed a miss until the
        # skip was made lazy instead.
        "gh --repo pr pr merge 27",
        "gh --repo o/n --hostname pr pr merge 27",
        # Whitespace variants.
        "gh\tpr\tmerge 27",
        "gh   pr   merge   27",
        # Backslash line continuation. Excluding the newline from the
        # separators to stop the cross-command false positive ALSO broke this,
        # briefly, in the first fix — a continuation is a joined line, not a
        # new command, so it is a separator while a bare newline is not.
        "gh \\\n  pr merge 27",
        "gh --repo o/n \\\n  pr merge 27",
        "gh pr merge 27 \\\n  --squash",
        # Continuation BETWEEN `pr` and `merge`. The first `_SEP` pass covered
        # the gh->token and token->token positions but left the subcommand pair
        # as `[ \t]`, moving the identical bypass one token right — these were
        # silent until `_SEP` was applied at every position.
        "gh pr \\\n  merge 27",
        "gh pr \\\n  merge 27 --squash",
        "gh \\\n pr \\\n merge 27",
        "gh \\\r\n pr \\\r\n merge",
        "git status && gh pr merge 27",
    ],
)
def test_a_pr_merge_asks(command, monkeypatch, capsys):
    payload = _run(command, monkeypatch, capsys)
    assert payload is not None, command
    assert "PR merge" in _reason(payload), command


def test_the_merge_prompt_names_the_override_like_every_other_reason(monkeypatch, capsys):
    """`main()` appends the escape-hatch suffix to any non-empty reason list —
    pinned here because the merge rule is the highest-consequence thing the
    hatch can silence, so the prompt must say how it was silenced."""
    reason = _reason(_run("gh pr merge 27", monkeypatch, capsys))
    assert "ALLOW_DESTRUCTIVE_GIT" in reason
    assert "ask-destructive-git.py" in reason


def test_the_override_silences_the_merge_prompt_too(monkeypatch, capsys):
    """The hatch is shared, so this is expected — pinned because a stale
    exported var silencing the authorization guard is the worst silencing this
    hook allows, and it should be a deliberate, visible property."""
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_GIT", "1")
    assert _run("gh pr merge 27", monkeypatch, capsys) is None


@pytest.mark.parametrize(
    "command",
    [
        "gh pr view 27",
        "gh pr create --title x",
        "gh pr list --state open",
        "gh pr checks 27",
        "gh pr checkout 27",
        "gh pr view 27 --json mergeable",
        "gh pr edit 27 --add-label needs-merge",
        # A real, read-only subcommand. `merge` ended at the hyphen and
        # prompted on it; the rule now uses `merge(?![\w-])`.
        "gh pr merge-queue status",
        "gh run list",
        "git merge main",
        "git merge --no-ff feature/x",
        "echo 'gh pr merge 27'",
        'gh pr comment 27 --body "then gh pr merge it"',
        # Names that merely start with or contain `gh` — the optional extension
        # suffix must not turn these into matches.
        "ghost pr merge 27",
        "gh.exe.bak pr merge 27",
        "mygh pr merge 27",
        "gh-wrapper pr merge 27",
        "gh.sh pr merge 27",
    ],
)
def test_non_merge_gh_and_local_merge_do_not_ask(command, monkeypatch, capsys):
    """A prompt that fires on `gh pr view` would be ignored within a day. Local
    `git merge` is deliberately out of scope — not outward-facing, and
    `warn-stacked-pr-merge` already covers the case that matters there."""
    payload = _run(command, monkeypatch, capsys)
    reason = "" if payload is None else _reason(payload)
    assert "PR merge" not in reason, command


def test_a_pr_merge_still_asks_alongside_another_destructive_shape(monkeypatch, capsys):
    reason = _reason(
        _run("git push --force origin x && gh pr merge 27 --squash", monkeypatch, capsys)
    )
    assert "force-push" in reason
    assert "PR merge" in reason


@pytest.mark.parametrize(
    "command",
    [
        "gh pr view 27 && echo pr merge",
        # A BARE newline ends the command. Separators are `_SEP` — horizontal
        # whitespace or a backslash continuation — never `\s`, which matches a
        # newline: with `\s` the skip walked across line breaks and
        # `gh auth status` + newline + `echo pr merge` fired. Multi-line Bash is
        # ordinary here, and `_PUSH`/`_RESET` exclude `\n` for the same reason.
        # The continuation cases in `test_a_pr_merge_asks` are the other half:
        # a joined line is NOT a command boundary and must still match.
        "gh auth status\necho pr merge is guarded",
        "gh run list\necho pr merge",
        "gh release list\npr merge notes",
    ],
)
def test_the_merge_match_does_not_span_a_shell_separator(command, monkeypatch, capsys):
    payload = _run(command, monkeypatch, capsys)
    reason = "" if payload is None else _reason(payload)
    assert "PR merge" not in reason, command


# --------------------------------------------------------------------------- #
# ALLOW_PR_MERGE — the narrow hatch for skills that merge unattended
#
# `multi-pr` and `multi-lite` merge as an ordinary loop step of a long
# unattended run, so the merge prompt would simply hang. An audit of every
# mutating command those skills emit found the merge ask was the only NEW
# obstacle; the broad ALLOW_DESTRUCTIVE_GIT would have cleared it at the cost of
# disarming force-push and reset --hard for the same command.
# --------------------------------------------------------------------------- #


def test_allow_pr_merge_silences_the_merge_prompt(monkeypatch, capsys):
    monkeypatch.setenv("ALLOW_PR_MERGE", "1")
    assert _run("gh pr merge 27 --squash --delete-branch", monkeypatch, capsys) is None


def test_allow_pr_merge_does_NOT_silence_a_force_push(monkeypatch, capsys):
    """The whole reason for a narrow variable: an unattended run that may merge
    must not thereby lose its force-push guard."""
    monkeypatch.setenv("ALLOW_PR_MERGE", "1")
    reason = _reason(_run("git push --force origin feature/x", monkeypatch, capsys))
    assert "force-push" in reason


def test_allow_pr_merge_does_NOT_silence_a_reset_hard(monkeypatch, capsys):
    monkeypatch.setenv("ALLOW_PR_MERGE", "1")
    reason = _reason(_run("git reset --hard HEAD~1", monkeypatch, capsys))
    assert "reset --hard" in reason


def test_a_command_that_merges_AND_force_pushes_still_prompts_on_the_push(
    monkeypatch, capsys
):
    """The precise boundary: one reason is dropped, the other survives, so the
    prompt still appears and names only the thing still being guarded."""
    monkeypatch.setenv("ALLOW_PR_MERGE", "1")
    reason = _reason(
        _run("git push --force origin x && gh pr merge 27", monkeypatch, capsys)
    )
    assert "force-push" in reason
    assert "PR merge" not in reason


def test_allow_pr_merge_announces_itself_on_a_merge_it_suppressed(monkeypatch, capsys):
    """A merge sailing through because of a variable set earlier in the run must
    not be indistinguishable from one the guard deliberately allowed."""
    monkeypatch.setenv("ALLOW_PR_MERGE", "1")
    monkeypatch.setattr(
        sys, "stdin",
        io.StringIO(json.dumps({"tool_input": {"command": "gh pr merge 27"}})),
    )
    assert hook.main() == 0
    err = capsys.readouterr().err
    assert "DISABLED" in err and "ALLOW_PR_MERGE" in err


def test_allow_pr_merge_stays_quiet_on_an_ordinary_command(monkeypatch, capsys):
    monkeypatch.setenv("ALLOW_PR_MERGE", "1")
    monkeypatch.setattr(
        sys, "stdin", io.StringIO(json.dumps({"tool_input": {"command": "git status"}}))
    )
    assert hook.main() == 0
    assert capsys.readouterr().err.strip() == ""


def test_without_the_variable_the_merge_still_prompts(monkeypatch, capsys):
    """Non-vacuity: the tests above would all pass if the rule were simply gone."""
    monkeypatch.delenv("ALLOW_PR_MERGE", raising=False)
    assert "PR merge" in _reason(_run("gh pr merge 27", monkeypatch, capsys))


def test_the_inline_prefix_form_actually_works(monkeypatch, capsys):
    """The form the skills document. A PreToolUse hook runs BEFORE the command,
    so an inline assignment never reaches os.environ — reading only the
    environment made the documented usage silently do nothing. Caught by
    running the documented command rather than the mechanism under it."""
    monkeypatch.delenv("ALLOW_PR_MERGE", raising=False)
    assert _run(
        "ALLOW_PR_MERGE=1 gh pr merge 27 --squash --delete-branch", monkeypatch, capsys
    ) is None


def test_the_inline_prefix_does_not_silence_a_force_push(monkeypatch, capsys):
    monkeypatch.delenv("ALLOW_PR_MERGE", raising=False)
    reason = _reason(
        _run("ALLOW_PR_MERGE=1 git push --force origin x", monkeypatch, capsys)
    )
    assert "force-push" in reason


def test_the_prefix_must_sit_where_a_shell_would_treat_it_as_an_assignment(
    monkeypatch, capsys
):
    """Mid-command occurrences must NOT authorize — otherwise merely mentioning
    the variable in an echoed string would disarm the guard."""
    monkeypatch.delenv("ALLOW_PR_MERGE", raising=False)
    reason = _reason(
        _run('echo "set ALLOW_PR_MERGE=1 first" && gh pr merge 27', monkeypatch, capsys)
    )
    assert "PR merge" in reason


def test_the_prefix_is_honoured_after_a_shell_separator(monkeypatch, capsys):
    monkeypatch.delenv("ALLOW_PR_MERGE", raising=False)
    assert _run(
        "git fetch --prune && ALLOW_PR_MERGE=1 gh pr merge 27", monkeypatch, capsys
    ) is None
