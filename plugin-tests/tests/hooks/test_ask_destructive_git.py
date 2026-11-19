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

import base64
import importlib.util
import io
import json
import re
import subprocess
import sys
import time
import types
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "hooks"


def _load():
    spec = importlib.util.spec_from_file_location(
        "ask_destructive_git", _HOOKS_DIR / "ask-destructive-git.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load()


def _run(command: str, monkeypatch, capsys, cwd: str | None = None) -> dict | None:
    """Run the hook on `command`; return its parsed stdout JSON, or None.

    `cwd` populates the payload field the working-tree probes resolve against.
    Omitting it is what every text-only test does: the hook then falls back to
    the process cwd, and none of those commands reaches a probe anyway.
    """
    payload: dict = {"tool_input": {"command": command}}
    if cwd is not None:
        payload["cwd"] = cwd
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
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


# requirement: git-guards / A force-push, hard reset or forced branch delete asks first
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


# requirement: git-guards / A force-push, hard reset or forced branch delete asks first
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


# requirement: git-guards / A force-push, hard reset or forced branch delete asks first
@pytest.mark.parametrize(
    "command",
    [
        "git branch -D feature/x",
        "git branch -D feature/x feature/y",
        # Bundled clusters, the same shape the force-push arm exists for.
        "git branch -aD feature/x",
        "git branch -Dr origin/feature/x",
        # `-D` is only a SHORTCUT for `--delete --force` (git-branch(1)), so
        # every decomposition of it destroys a commit just as thoroughly. A
        # first cut matched only the shortcut and the long-long pair, leaving
        # these five silent — 3 of 8 spellings covered.
        "git branch -d -f feature/x",
        "git branch -f -d feature/x",
        "git branch -df feature/x",
        "git branch -fd feature/x",
        "git branch -d --force feature/x",
        "git branch --delete -f feature/x",
        # Long form, both orders — the two flags are matched independently, so
        # order cannot smuggle one past.
        "git branch --delete --force feature/x",
        "git branch --force --delete feature/x",
        # git accepts any UNAMBIGUOUS long-option abbreviation.
        "git branch --dele --forc feature/x",
        "git branch --d --forc feature/x",
        # The flag may be the last token, so the boundary must admit end-of-
        # string. The force-push block pins this; branch-delete did not, and a
        # mutation dropping the `$` alternative survived every case.
        "git branch feature/x -D",
        # The shapes every other rule here is also tested against.
        "git -C /some/path branch -D feature/x",
        "git --git-dir /some/path/.git branch -D feature/x",
        "git branch \\\n  -D feature/x",
        "git \\\n branch -D feature/x",
        "git branch \\\r\n  -D feature/x",
        # The continuation with NO space before the backslash. The shell strips
        # `\`+newline before word-splitting, so this really does force-delete
        # (verified against git: `Deleted branch cont1`), and a terminator of
        # `(?=\s|$)` alone rejected it because the `\` abuts the `D`.
        "git branch -D\\\n  feature/x",
        "git branch --delete\\\n  --force feature/x",
        # Mirrored, so BOTH long terminators are load-bearing. Without this row
        # a mutation reverting only `_FORCE_LONG`'s backslash survived: the case
        # above puts the continuation after `--delete`, leaving `--force ` to
        # match on an ordinary space.
        "git branch --force\\\n  --delete feature/x",
    ],
)
def test_force_branch_delete_shapes_prompt(command, monkeypatch, capsys):
    payload = _run(command, monkeypatch, capsys)
    assert payload is not None, f"expected an ask for: {command!r}"
    assert "force-delete" in _reason(payload)


@pytest.mark.parametrize(
    "command",
    [
        "git.exe branch -D feature/x",
        "git.cmd branch -D feature/x",
        "GIT branch -D feature/x",
        "Git.Exe branch -D feature/x",
    ],
)
def test_branch_delete_fires_on_every_executable_spelling(
    command, monkeypatch, capsys
):
    """The sibling force-push test exists because a rule once proved its FLAG
    constant while nothing proved the command-shape composition. Branch-delete
    shipped without this row, and a mutation swapping `_GIT_CMD` for a literal
    lowercase `git` survived all nine positives — on the platform whose
    tab-completion emits `git.exe`."""
    payload = _run(command, monkeypatch, capsys)
    assert payload is not None, f"expected an ask for: {command!r}"
    assert "force-delete" in _reason(payload)


def test_a_branch_delete_inside_a_quoted_string_does_not_prompt(monkeypatch, capsys):
    """Quote-stripping is what stops the hook prompting about text that merely
    MENTIONS a destructive command. Branch-delete shipped with no case pinning
    it, and replacing `_strip_quoted_spans` with the identity function survived
    every positive and negative in the block."""
    assert _run('echo "never run git branch -D old here"', monkeypatch, capsys) is None
    assert (
        _run('git commit -m "drop it with git branch -D old"', monkeypatch, capsys)
        is None
    )


@pytest.mark.parametrize(
    "command",
    [
        # A delete WITHOUT force: per git-branch(1) the branch must be "fully
        # merged in its upstream branch, or in HEAD if no upstream was set",
        # so git refuses the destructive case itself. Force is what overrides
        # that refusal, which is why force is half the predicate.
        "git branch -d feature/x",
        "git branch --delete feature/x",
        "git branch -d -r origin/feature/x",
        # `--force` WITHOUT a delete flag. Excluded deliberately, but NOT
        # because it is safe: git-branch(1) says `--force` resets an existing
        # branch to a new start-point, so the old tip is orphaned exactly as a
        # force-delete orphans it. Excluded because ref-moving is frequent
        # enough that prompting on it would make the prompt routine. An earlier
        # revision of this comment claimed it "does not destroy a commit",
        # which is false — measured: `git branch --force keepme main` leaves
        # the old tip unreachable from every ref.
        "git branch --force feature/x main",
        "git branch -f feature/x main",
        "git branch -M old new",
        "git branch -C old new",
        # A branch NAME ending in capital D is not a flag cluster.
        "git branch -d featureD",
        "git branch featureD",
        # `--format` shares a prefix with `--force`; only `--forc` is
        # unambiguous, so the abbreviation arm must not reach this.
        "git branch --format='%(refname)'",
        "git branch -a --sort=-committerdate",
        # An option's ARGUMENT shaped like a flag cluster. Each was run against
        # real git and left the branch intact, so a prompt here is pure noise —
        # and noise is what stops a checkpoint being read. The `-u` and `-t`
        # values and the `--sort` key supply the letters; the alphabet filter is
        # what rejects them, since `e`/`v`/`H` are not `git branch` options.
        "git branch -uDev feature/x",
        "git branch --sort -HEAD",
        "git branch -f -tdirect newbranch main",
        "git branch --sort -refname -d merged1",
        "git branch --sort -committerdate -f main origin/main",
        # The pairing that makes the `--forc`-not-`--fo` boundary load-bearing.
        # With a delete flag present, a too-greedy force pattern reads
        # `--format` as force and turns an ordinary non-force delete into a
        # prompt. Measured: widening to `--fo[a-z]*` fails nothing WITHOUT this
        # case, because a lone `--format` never satisfies the delete half.
        "git branch -d --format='%(refname)' feature/x",
        "git branch --delete --format='%(refname)' feature/x",
        # Ordinary listing.
        "git branch",
        "git branch -a",
        "git branch --list",
    ],
)
def test_non_destructive_branch_shapes_stay_silent(command, monkeypatch, capsys):
    assert _run(command, monkeypatch, capsys) is None, f"unexpected ask for: {command!r}"


def test_a_branch_delete_flag_from_a_later_command_is_not_attributed(
    monkeypatch, capsys
):
    """Same attribution bug the force-push rule was fixed for: a `-D` belonging
    to a different command must not make an innocent `git branch` prompt."""
    assert _run("git branch && rm -D /tmp/scratch", monkeypatch, capsys) is None


def test_both_shapes_in_one_line_are_reported_together(monkeypatch, capsys):
    payload = _run("git reset --hard && git push -f origin feature/x", monkeypatch, capsys)
    reason = _reason(payload)
    assert "force-push" in reason and "reset --hard" in reason


def test_a_branch_delete_is_reported_alongside_another_cause(monkeypatch, capsys):
    """`main()`'s escape-hatch advice keys off `found == [MERGE_REASON]`, an
    equality that depends on `_reasons()`'s fixed append order. Inserting a
    fourth reason is exactly the change the comment there asks to be
    re-verified, and nothing pinned it."""
    reason = _reason(
        _run("git reset --hard && git branch -D feature/x", monkeypatch, capsys)
    )
    assert "reset --hard" in reason and "force-delete" in reason


def test_a_branch_delete_with_a_merge_still_names_the_broad_hatch(monkeypatch, capsys):
    """Two reasons where one is the merge: the advice must point at the broad
    variable, since the narrow one would leave the branch guard armed."""
    payload = _run("git branch -D feature/x && gh pr merge 27", monkeypatch, capsys)
    reason = _reason(payload)
    assert "force-delete" in reason
    assert "ALLOW_DESTRUCTIVE_GIT" in json.dumps(payload)


@pytest.mark.parametrize(
    "command,expected",
    [
        ("git.exe push --force origin feature/x", "force-push"),
        ("git.cmd push --force origin feature/x", "force-push"),
        ("GIT.EXE push --force origin feature/x", "force-push"),
        ("GIT push --force origin feature/x", "force-push"),
        ("Git.Exe reset --hard HEAD~1", "reset --hard"),
        ("git.exe -C /some/worktree push --force origin feature/x", "force-push"),
    ],
)
def test_the_guard_itself_fires_on_every_executable_spelling(
    command, expected, monkeypatch, capsys
):
    """`GIT_CMD` is pinned in `test_dispatch_lib.py`, but only as a REGEX.

    Every case in THIS file hardcoded a bare lowercase `git` before these were
    added (`git grep -c` over `main`'s copy: zero non-lowercase spellings). The
    spellings do appear elsewhere in the tree — `_dispatch_lib.py`, the
    `pre-push` hook and its test — but not in any guard's own test, so the
    constant proved the pattern and nothing proved the GUARD, which is the thing
    that emits the prompt. What is untested is the
    COMPOSITION: `GIT_CMD` + `GIT_GLOBAL_OPTS` + the subcommand, which the
    constant test never reaches. Reachable by ordinary use, not evasion —
    PowerShell is a primary shell here and its tab-completion emits `git.exe`.
    """
    payload = _run(command, monkeypatch, capsys)
    assert payload is not None, (
        f"an alternative executable spelling must not walk past the guard: {command!r}"
    )
    # Asserting WHICH rule fired, not merely that something did: a bare
    # `is not None` would stay green if the force-push rule misfired on the
    # `reset --hard` case, which is the kind of mis-attribution a widened
    # command-name pattern is most likely to cause.
    assert expected in _reason(payload), (
        f"{command!r} should be reported as {expected!r}, not as something else"
    )


def test_an_alternative_spelling_of_a_safe_command_still_stays_silent(monkeypatch, capsys):
    """Non-vacuity: the case-folded command name must not turn the guard into
    one that prompts on any line containing `git`.

    `conftest.py` clears `ALLOW_DESTRUCTIVE_GIT` for every test in this scope.
    Without that, this whole assertion is unfalsifiable — the hatch makes the
    hook exit 0 having printed to stderr only, `_run` reads stdout and returns
    `None`, and both lines below pass for any input at all.
    """
    assert _run("git.exe push origin feature/x", monkeypatch, capsys) is None
    assert _run("GIT status", monkeypatch, capsys) is None
    # The guarded form, in an alternative spelling — the widened pattern must
    # not cost the safer habit its exemption.
    assert _run("git.exe push --force-with-lease origin x", monkeypatch, capsys) is None


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


# requirement: git-guards / One override silences every git prompt
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


# requirement: git-guards / A pull request merge asks first
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


def test_the_merge_prompt_names_the_narrow_variable_a_reader_can_actually_use(
    monkeypatch, capsys
):
    """A merge-only prompt must name `ALLOW_PR_MERGE=1` — the variable honoured
    from command text (`_every_merge_is_authorized`) — not `ALLOW_DESTRUCTIVE_GIT`,
    which is env-only and silently no-ops as the inline prefix a reader would
    naturally try. Regression test for the bug where the message recommended
    the broad, unusable variable for the narrowest, highest-consequence reason.
    """
    reason = _reason(_run("gh pr merge 27", monkeypatch, capsys))
    assert "ALLOW_PR_MERGE=1" in reason
    assert "ALLOW_DESTRUCTIVE_GIT" not in reason
    assert "ask-destructive-git.py" in reason


def test_the_force_push_prompt_still_names_the_broad_env_only_variable(
    monkeypatch, capsys
):
    """Force-push and `reset --hard` have no narrow, command-text-honoured
    equivalent, so those prompts keep pointing at `ALLOW_DESTRUCTIVE_GIT`."""
    reason = _reason(_run("git push --force origin feature/x", monkeypatch, capsys))
    assert "ALLOW_DESTRUCTIVE_GIT" in reason
    assert "ALLOW_PR_MERGE" not in reason


def test_a_mixed_reason_prompt_names_the_broad_variable_not_the_narrow_one(
    monkeypatch, capsys
):
    """`ALLOW_PR_MERGE=1` only ever silences the merge reason (see the
    narrow-variable comment above `main()`), so a command that ALSO force-pushes
    or reset --hards must not be told the narrow variable covers it."""
    reason = _reason(
        _run("git push --force origin feature/x && gh pr merge 27", monkeypatch, capsys)
    )
    assert "ALLOW_DESTRUCTIVE_GIT" in reason
    assert "ALLOW_PR_MERGE" not in reason


def test_a_reset_and_merge_mix_also_names_the_broad_variable(monkeypatch, capsys):
    """Same rule as the force-push+merge mix, for the other non-narrow reason —
    reset --hard has no narrow equivalent either, so the merge alongside it
    must not make the prompt claim the narrow variable covers this command."""
    reason = _reason(_run("git reset --hard && gh pr merge 27", monkeypatch, capsys))
    assert "ALLOW_DESTRUCTIVE_GIT" in reason
    assert "ALLOW_PR_MERGE" not in reason


# requirement: git-guards / One override silences every git prompt
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


# requirement: git-guards / A pull request merge asks first
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


def test_allow_pr_merge_does_NOT_silence_a_branch_force_delete(monkeypatch, capsys):
    """`multi-pr` and `multi-lite` set this variable AND delete branches, so the
    two meeting is an ordinary occurrence rather than a corner case."""
    monkeypatch.setenv("ALLOW_PR_MERGE", "1")
    reason = _reason(_run("git branch -D feature/x", monkeypatch, capsys))
    assert "force-delete" in reason


def test_the_allow_pr_merge_notice_names_branch_delete_as_still_armed(
    monkeypatch, capsys
):
    """The note is the only place a human is TOLD what stays armed. It listed
    force-push and reset --hard for one release after branch-delete was added,
    so a reader was told, incorrectly, that this guard was off."""
    monkeypatch.setenv("ALLOW_PR_MERGE", "1")
    # Driven directly rather than through `_run`, which drains capsys.
    monkeypatch.setattr(
        sys, "stdin",
        io.StringIO(json.dumps({"tool_input": {"command": "gh pr merge 27"}})),
    )
    assert hook.main() == 0
    err = capsys.readouterr().err
    assert "DISABLED" in err and "ALLOW_PR_MERGE" in err
    for still_armed in ("Force-push", "reset --hard", "branch force-delete"):
        assert still_armed in err, (
            f"the ALLOW_PR_MERGE notice does not name {still_armed!r} among the "
            "guards that stay armed, so it under-reports the hook's own scope"
        )


def test_allow_destructive_git_silences_a_branch_force_delete(monkeypatch, capsys):
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_GIT", "1")
    # Driven directly rather than through `_run`, which drains capsys.
    monkeypatch.setattr(
        sys, "stdin",
        io.StringIO(json.dumps({"tool_input": {"command": "git branch -D feature/x"}})),
    )
    assert hook.main() == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "", "the broad hatch must suppress the ask entirely"
    assert "DISABLED" in captured.err, (
        "a branch force-delete waved through by the broad hatch must still "
        "announce itself, or it is indistinguishable from one nothing checked"
    )


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
    the variable in an echoed string would disarm the guard.

    The original form of this test used `echo "set ALLOW_PR_MERGE=1 first"`,
    where the token before the variable is `set` — not a shell separator. So it
    passed without ever exercising the `(?:^|[&|;]\\s*)` anchor it claims to
    test, and the anchor was in fact satisfiable by a separator inside a quoted
    span. The cases below all put a REAL separator in front of the variable,
    inside quotes, which is what the shell never evaluates as an assignment.
    """
    monkeypatch.delenv("ALLOW_PR_MERGE", raising=False)
    reason = _reason(
        _run('echo "set ALLOW_PR_MERGE=1 first" && gh pr merge 27', monkeypatch, capsys)
    )
    assert "PR merge" in reason


@pytest.mark.parametrize(
    "command",
    [
        # separator + variable, both inside a quoted span the shell never evaluates
        'gh pr merge 27 && echo "; ALLOW_PR_MERGE=1 done"',
        'echo "; ALLOW_PR_MERGE=1 " && gh pr merge 123 --squash',
        'gh pr merge 123 --squash && echo "done ; ALLOW_PR_MERGE=1 was not used"',
        # the shape a session working on THIS hook actually writes
        'git commit -m "fix hook; ALLOW_PR_MERGE=1 now bypasses it" && gh pr merge 27',
        "gh pr merge 27 && echo '| ALLOW_PR_MERGE=1 '",
    ],
)
def test_a_separator_inside_quotes_does_not_authorize(command, monkeypatch, capsys):
    """The bypass this file shipped with: the anchor accepted a `;`/`&`/`|` that
    sits INSIDE a quoted string, which bash treats as one literal. Every command
    here silenced the prompt entirely before the fix — including a plain commit
    message. Authorization is the one thing a hook cannot read, so a bypass that
    fires on unrelated prose removes exactly the protection this guard adds."""
    monkeypatch.delenv("ALLOW_PR_MERGE", raising=False)
    assert "PR merge" in _reason(_run(command, monkeypatch, capsys)), command


def test_the_genuine_inline_prefix_still_authorizes_after_quote_stripping(
    monkeypatch, capsys
):
    """Non-vacuity partner for the test above: the fix scans quote-STRIPPED text,
    so it must not also break the legitimate per-command form, which is unquoted
    and therefore survives stripping intact."""
    monkeypatch.delenv("ALLOW_PR_MERGE", raising=False)
    payload = _run("ALLOW_PR_MERGE=1 gh pr merge 123 --squash", monkeypatch, capsys)
    assert payload is None or "PR merge" not in _reason(payload)


def test_the_prefix_is_honoured_after_a_shell_separator(monkeypatch, capsys):
    monkeypatch.delenv("ALLOW_PR_MERGE", raising=False)
    assert _run(
        "git fetch --prune && ALLOW_PR_MERGE=1 gh pr merge 27", monkeypatch, capsys
    ) is None


# requirement: git-guards / A pull request merge asks first
@pytest.mark.parametrize(
    "command",
    [
        # a later, unrelated segment carrying the prefix
        "gh pr merge 27 --squash; ALLOW_PR_MERGE=1 true",
        "gh pr merge 27 && ALLOW_PR_MERGE=1 echo done",
        # one prefixed merge must not carry an unprefixed second one
        "ALLOW_PR_MERGE=1 gh pr merge 1 --squash && gh pr merge 2 --squash",
        # the prefix on another command in the same segment chain
        "ALLOW_PR_MERGE=1 git fetch && gh pr merge 27",
    ],
)
def test_the_prefix_authorizes_only_the_merge_it_heads(command, monkeypatch, capsys):
    """The prefix used to match after any separator, so the guarded agent could type its own
    way past the merge checkpoint from an unrelated segment of the same command."""
    monkeypatch.delenv("ALLOW_PR_MERGE", raising=False)
    assert "PR merge" in _reason(_run(command, monkeypatch, capsys)), command


@pytest.mark.parametrize(
    "command",
    [
        "GH_REPO=o/r ALLOW_PR_MERGE=1 gh pr merge 27 --squash",
        "ALLOW_PR_MERGE=1 GH_REPO=o/r gh pr merge 27 --squash",
        "ALLOW_PR_MERGE=1 gh pr merge 1 --squash && ALLOW_PR_MERGE=1 gh pr merge 2 --squash",
        "(ALLOW_PR_MERGE=1 gh pr merge 27 --squash)",
        "ALLOW_PR_MERGE=1 \\\n  gh pr merge 27 --squash",  # a continued line is one command
    ],
)
def test_the_prefix_still_authorizes_every_merge_it_heads(command, monkeypatch, capsys):
    """Non-vacuity partner: other assignments beside the prefix, and every merge prefixed."""
    monkeypatch.delenv("ALLOW_PR_MERGE", raising=False)
    assert _run(command, monkeypatch, capsys) is None, command


# requirement: git-guards / A push that skips the pre-push guard asks first
@pytest.mark.parametrize(
    "command",
    [
        "git push --no-verify origin main",
        "git push --no-veri origin HEAD:main",
        "git -c core.hooksPath=/dev/null push origin main",
        "ALLOW_PUSH_TO_MAIN=1 git push origin main",
        "git fetch && ALLOW_PUSH_TO_MAIN=1 git push",
        # quoted values and a separator right after the value (review of #445)
        'ALLOW_PUSH_TO_MAIN="1" git push origin main',
        "ALLOW_PUSH_TO_MAIN='1' git push origin main",
        "export ALLOW_PUSH_TO_MAIN=1;git push origin main",
        # every other way to point git's hooks elsewhere for the push
        'git -c "core.hooksPath=/dev/null" push origin main',
        "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=/x git push origin main",
        "GIT_CONFIG_PARAMETERS=\"'core.hooksPath=/dev/null'\" git push origin main",
        "git config core.hooksPath /dev/null && git push origin main",
    ],
)
def test_a_push_that_skips_the_pre_push_guard_asks(command, monkeypatch, capsys):
    """The pre-push hook is the only guard on the default branch, and these skip it with no
    prompt: git honours `--no-verify` and `core.hooksPath`, and the hook its own override."""
    monkeypatch.delenv("ALLOW_DESTRUCTIVE_GIT", raising=False)
    assert "skips the pre-push guard" in _reason(_run(command, monkeypatch, capsys)), command


@pytest.mark.parametrize(
    "command",
    [
        "git push origin feature/x",
        "git push --no-ver origin x",  # ambiguous: git refuses it, so nothing is skipped
        'git commit -m "note: ALLOW_PUSH_TO_MAIN=1 is the override" && git push',
        "git -c core.hooksPath=/dev/null commit -m x",
    ],
)
def test_an_ordinary_push_does_not_ask_about_the_pre_push_guard(command, monkeypatch, capsys):
    """Non-vacuity partner: a plain push, an ambiguous abbreviation, the override named only in
    prose, and `core.hooksPath` on a command that is not a push."""
    monkeypatch.delenv("ALLOW_DESTRUCTIVE_GIT", raising=False)
    payload = _run(command, monkeypatch, capsys)
    assert payload is None or "skips the pre-push guard" not in _reason(payload), command


# requirement: git-guards / One override silences every git prompt
def test_the_override_silences_the_push_skip_prompt_too(monkeypatch, capsys):
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_GIT", "1")
    assert _run("git push --no-verify origin main", monkeypatch, capsys) is None


# --------------------------------------------------------------------------- #
# Working-tree discards -- `git checkout <path>`, `git restore <path>`,
# `git clean`. Unlike every rule above, these are CONDITIONAL on the paths
# actually holding work, so each test needs a real repository in a known state:
# a matcher test alone would prove nothing about the half that keeps the prompt
# affordable.
# --------------------------------------------------------------------------- #


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cached_git_repo) -> Path:
    """A repository with one committed file, `tracked.txt`, and a clean tree.

    Pinned against the developer's own git configuration, which this repo has no
    CI to catch. Measured on the first cut: `core.excludesFile` ignoring `*.txt`
    and `commit.gpgsign = true` each errored all 26 of these tests in the
    fixture, and `status.showUntrackedFiles = no` turned one red. None produced
    a FALSE GREEN, so the exposure was someone else's broken run rather than
    absent coverage -- but `init.defaultBranch` did produce a silently weaker
    test, so the whole surface is pinned rather than the one axis.

    `-b main` is part of that: without it the branch is whatever
    `init.defaultBranch` says, and
    `test_a_pathless_branch_checkout_stays_silent_even_in_a_dirty_tree` then
    asserts about a name that is not a branch at all -- a strictly weaker claim
    than the one its docstring makes, on any machine defaulting to `master`.
    """
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(tmp_path / "gitconfig-system"))
    # Built under the pinned config above (the first test builds it), then copied.
    return cached_git_repo("ask_destructive_git", _build_repo, tmp_path / "repo")


def _build_repo(root: Path) -> None:
    _git(root, "init", "-q", "-b", "main", ".")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "t")
    (root / "tracked.txt").write_text("original\n", encoding="utf-8")
    _git(root, "add", "tracked.txt")
    _git(root, "commit", "-qm", "seed")


@pytest.fixture
def dirty(repo: Path) -> Path:
    """The same repository with uncommitted work in `tracked.txt` -- the exact
    state issue #184's incident was in when `git checkout <file>` erased it."""
    (repo / "tracked.txt").write_text("original\nfifty more lines\n", encoding="utf-8")
    return repo


# requirement: git-guards / Discarding uncommitted work asks first
@pytest.mark.parametrize(
    "command",
    [
        "git checkout tracked.txt",
        "git checkout -- tracked.txt",
        "git restore tracked.txt",
        "git restore -- tracked.txt",
        # Behind a global option, and split across a line continuation -- the
        # two shapes every other matcher in this file was found broken on.
        "git -C . checkout tracked.txt",
        "git checkout \\\n-- tracked.txt",
        # Second in a chain, which is how it is actually typed mid-implementation.
        "git status && git checkout tracked.txt",
    ],
)
def test_a_discard_of_dirty_tracked_work_prompts(command, dirty, monkeypatch, capsys):
    payload = _run(command, monkeypatch, capsys, cwd=str(dirty))
    assert payload is not None, f"expected an ask for: {command!r}"
    assert "discard of uncommitted work" in _reason(payload)


# requirement: git-guards / Discarding uncommitted work asks first
@pytest.mark.parametrize(
    "command",
    [
        "git checkout tracked.txt",
        "git restore tracked.txt",
        "git checkout -- .",
    ],
)
def test_the_same_command_on_a_clean_path_stays_silent(
    command, repo, monkeypatch, capsys
):
    """The half that makes the rule affordable. `ask-destructive-git`'s own
    docstring rejected these commands for years because an unconditional prompt
    would bury the force-push one in noise; if this test can be made to fail by
    dropping the probe, the noise objection is back."""
    assert _run(command, monkeypatch, capsys, cwd=str(repo)) is None, command


def test_a_pathless_branch_checkout_stays_silent_even_in_a_dirty_tree(
    dirty, monkeypatch, capsys
):
    """Explicitly out of scope: git already refuses a branch switch that would
    clobber uncommitted changes. No branch-versus-path parser enforces this --
    `main` is passed to the probe as a pathspec, matches no file, and reports no
    work. This test is what says that resolution is intended rather than lucky."""
    assert _run("git checkout main", monkeypatch, capsys, cwd=str(dirty)) is None


def test_creating_a_branch_named_after_a_dirty_file_stays_silent(
    dirty, monkeypatch, capsys
):
    """`-b`'s value is a branch name, not a path operand. Without `_VALUE_OPTS`
    this prompts, because a file called `tracked.txt` is dirty right now."""
    assert _run(
        "git checkout -b tracked.txt", monkeypatch, capsys, cwd=str(dirty)
    ) is None


def test_an_untracked_file_does_not_make_a_checkout_prompt(repo, monkeypatch, capsys):
    """`git checkout <path>` does not touch untracked files, so their presence
    is not work it would destroy. This is why the probe distinguishes `??` lines
    from tracked-modified ones rather than testing for any output at all."""
    (repo / "scratch.txt").write_text("untracked\n", encoding="utf-8")
    assert _run("git checkout -- .", monkeypatch, capsys, cwd=str(repo)) is None


def test_a_quoted_path_containing_a_space_still_reaches_the_probe(
    repo, monkeypatch, capsys
):
    """The reason operands are tokenised against the quote-stripped tail and
    re-sliced from the raw one. Splitting the raw text would yield `"my` and
    `file.txt"`, neither of which is a path, and the guard would go silent on a
    real discard."""
    (repo / "my file.txt").write_text("a\n", encoding="utf-8")
    _git(repo, "add", "my file.txt")
    _git(repo, "commit", "-qm", "add spaced")
    (repo / "my file.txt").write_text("a\nb\n", encoding="utf-8")
    payload = _run('git checkout -- "my file.txt"', monkeypatch, capsys, cwd=str(repo))
    assert payload is not None
    assert "discard of uncommitted work" in _reason(payload)


# --- git clean -------------------------------------------------------------- #


# requirement: git-guards / Discarding uncommitted work asks first
def test_clean_prompts_when_untracked_files_exist(repo, monkeypatch, capsys):
    (repo / "scratch.txt").write_text("untracked\n", encoding="utf-8")
    payload = _run("git clean -fd", monkeypatch, capsys, cwd=str(repo))
    assert payload is not None
    assert "git clean" in _reason(payload)


def test_clean_stays_silent_when_there_is_nothing_untracked_to_delete(
    dirty, monkeypatch, capsys
):
    """A dirty TRACKED file is not something `git clean` removes, so the tree
    being dirty is not by itself a reason to prompt."""
    assert _run("git clean -fd", monkeypatch, capsys, cwd=str(dirty)) is None


@pytest.mark.parametrize(
    "command", ["git clean -nd", "git clean --dry-run", "git clean -d"]
)
def test_a_clean_that_deletes_nothing_stays_silent(command, repo, monkeypatch, capsys):
    """`-n`/`--dry-run` print and delete nothing; without a force flag git
    refuses outright. Prompting on either is pure noise -- and `git clean -nd`
    is itself the probe issue #184 proposed for this case, so firing on it would
    make the guard prompt at anyone checking what a clean would do."""
    (repo / "scratch.txt").write_text("untracked\n", encoding="utf-8")
    assert _run(command, monkeypatch, capsys, cwd=str(repo)) is None, command


# --- probe failure modes ---------------------------------------------------- #


def test_a_wedged_git_prompts_rather_than_going_silent(dirty, monkeypatch, capsys):
    """The probe not running is not evidence that nothing would be lost. A guard
    that allows because it failed to look is indistinguishable from one that
    looked and approved, which is the worst failure this layer has."""
    monkeypatch.setattr(hook, "_run_git", lambda cwd, args: None)
    payload = _run("git checkout tracked.txt", monkeypatch, capsys, cwd=str(dirty))
    assert payload is not None
    assert "discard of uncommitted work" in _reason(payload)


def test_a_pathspec_git_itself_rejects_stays_silent(repo, monkeypatch, capsys):
    """The other failure mode, treated differently on purpose: git refusing the
    pathspec means the real command is about to be refused the same way, so
    there is nothing to destroy."""
    assert _run(
        "git checkout -- ../outside.txt", monkeypatch, capsys, cwd=str(repo)
    ) is None


def test_outside_a_repository_the_guard_stays_silent(tmp_path, monkeypatch, capsys):
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    (plain / "tracked.txt").write_text("x\n", encoding="utf-8")
    assert _run("git checkout tracked.txt", monkeypatch, capsys, cwd=str(plain)) is None


# --- interaction with the existing reasons ---------------------------------- #


def test_a_discard_and_a_force_push_in_one_command_report_both(
    dirty, monkeypatch, capsys
):
    reason = _reason(
        _run(
            "git checkout tracked.txt && git push --force origin x",
            monkeypatch, capsys, cwd=str(dirty),
        )
    )
    assert "discard of uncommitted work" in reason
    assert "force-push" in reason


def test_allow_pr_merge_does_not_silence_a_discard(dirty, monkeypatch, capsys):
    """The narrow hatch drops the merge reason only -- the whole point of having
    it separate from the broad one."""
    monkeypatch.setenv("ALLOW_PR_MERGE", "1")
    reason = _reason(
        _run(
            "git checkout tracked.txt && gh pr merge 27",
            monkeypatch, capsys, cwd=str(dirty),
        )
    )
    assert "discard of uncommitted work" in reason
    assert "PR merge" not in reason


def test_allow_destructive_git_covers_a_discard(dirty, monkeypatch, capsys):
    """Folded into the broad hatch rather than given its own, per issue #184:
    it is the same "I know this discards work" intent."""
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_GIT", "1")
    # Driven directly rather than through `_run`, which drains capsys itself —
    # the same shape `test_the_override_announces_itself_on_a_command_it_
    # suppressed` uses, and for the same reason: stdout and stderr are two
    # assertions about one run.
    monkeypatch.setattr(
        sys, "stdin",
        io.StringIO(json.dumps({
            "tool_input": {"command": "git checkout tracked.txt"},
            "cwd": str(dirty),
        })),
    )
    assert hook.main() == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "", "the override must suppress the prompt"
    assert "DISABLED" in captured.err and "ALLOW_DESTRUCTIVE_GIT" in captured.err


def test_a_discard_only_prompt_names_the_env_only_hatch(dirty, monkeypatch, capsys):
    """`ALLOW_PR_MERGE` is honoured from command text; the broad one is not, and
    the message must not send a reader to a variable that would silently do
    nothing as an inline prefix."""
    reason = _reason(
        _run("git checkout tracked.txt", monkeypatch, capsys, cwd=str(dirty))
    )
    assert "ALLOW_DESTRUCTIVE_GIT=1 in the environment" in reason


def test_the_discard_probe_is_not_vacuous(dirty, monkeypatch, capsys):
    """Structural non-vacuity guarantee for a guard, per test-quality-gates.md. The
    prompt-on-dirty and silence-on-clean assertions above are each satisfiable
    by a half-broken probe, so pin that BOTH outcomes are reachable from the
    SAME repository by changing only its state -- which no constant-returning
    probe can do."""
    assert _run(
        "git checkout tracked.txt", monkeypatch, capsys, cwd=str(dirty)
    ) is not None
    _git(dirty, "checkout", "--", "tracked.txt")
    assert _run("git checkout tracked.txt", monkeypatch, capsys, cwd=str(dirty)) is None


# --- forced checkout / switch ----------------------------------------------- #
# The first cut of this rule was SILENT on every command below. `_operands`
# drops `-f` as a flag, so a bare `git checkout -f` produced no operands and
# never probed; `git checkout -f other` produced the branch name, which matches
# no path and reports no work. Both were verified against real git to destroy
# the uncommitted change outright.


@pytest.mark.parametrize(
    "command",
    [
        "git checkout -f",
        "git checkout --force",
        "git checkout -f main",
        "git checkout --force main",
        "git switch -f main",
        "git switch --discard-changes main",
        # The two shapes every matcher in this file has historically broken on.
        "git -C . checkout -f main",
        "git checkout \\\n-f main",
    ],
)
def test_a_forced_checkout_or_switch_prompts_on_a_dirty_tree(
    command, dirty, monkeypatch, capsys
):
    """The forced path has its OWN reason. `DISCARD_REASON` asserts something
    about "the path(s) named here", and a forced checkout names none -- the same
    false-measurement defect `UNCHECKED_REASON` was split out to fix, left in the
    branch it was diagnosed from."""
    payload = _run(command, monkeypatch, capsys, cwd=str(dirty))
    assert payload is not None, f"expected an ask for: {command!r}"
    reason = _reason(payload)
    assert "FORCED checkout or switch" in reason
    assert "path(s) named here" not in reason


@pytest.mark.parametrize(
    "command", ["git checkout -f", "git checkout -f main", "git switch -f main"]
)
def test_a_forced_checkout_stays_silent_on_a_clean_tree(
    command, repo, monkeypatch, capsys
):
    """Force does not make the command destructive by itself -- it makes the
    OPERANDS uninformative, so the probe widens to the whole tree. On a clean
    tree that still answers 'nothing at stake'."""
    assert _run(command, monkeypatch, capsys, cwd=str(repo)) is None, command


def test_a_bare_switch_to_a_branch_stays_silent(dirty, monkeypatch, capsys):
    """`git switch` is matched ONLY in its forced form. Bare `git switch` refuses
    on conflict exactly as bare `git checkout` does, so prompting on it would be
    the routine prompt this rule is shaped to avoid."""
    assert _run("git switch main", monkeypatch, capsys, cwd=str(dirty)) is None


# --- ignored files, which is where a clean is unrecoverable ------------------ #


@pytest.fixture
def ignored(repo: Path) -> Path:
    """A repository whose ONLY untracked content is gitignored -- the `.env`
    shape `/cla:new-worktree` deliberately carries between worktrees."""
    (repo / ".gitignore").write_text("secret.env\n", encoding="utf-8")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-qm", "ignore")
    (repo / "secret.env").write_text("TOKEN=1\n", encoding="utf-8")
    return repo


@pytest.mark.parametrize("command", ["git clean -fdx", "git clean -fX", "git clean -fdX"])
def test_clean_prompts_on_an_ignored_file_it_would_delete(
    command, ignored, monkeypatch, capsys
):
    """`git status --porcelain` does not list an ignored file without
    `--ignored`, so every one of these was silent while deleting exactly the
    files nothing recovers."""
    payload = _run(command, monkeypatch, capsys, cwd=str(ignored))
    assert payload is not None, f"expected an ask for: {command!r}"
    assert "git clean" in _reason(payload)


def test_clean_without_x_stays_silent_on_an_ignored_file(
    ignored, monkeypatch, capsys
):
    """Non-vacuity partner: plain `git clean -fd` leaves ignored files alone, so
    the `--ignored` widening must not leak into the default predicate."""
    assert _run("git clean -fd", monkeypatch, capsys, cwd=str(ignored)) is None


def test_ignored_only_clean_stays_silent_on_a_merely_untracked_file(
    repo, monkeypatch, capsys
):
    """`-X` deletes ONLY ignored files. Reading the probe as 'any `??` line'
    was wrong in both directions at once: it prompted here, where `-X` deletes
    nothing, and stayed silent on the ignored files it does delete."""
    (repo / "scratch.txt").write_text("untracked\n", encoding="utf-8")
    assert _run("git clean -fX", monkeypatch, capsys, cwd=str(repo)) is None


@pytest.mark.parametrize(
    "command", ["git clean --force", "git clean -f", "git clean -ffd"]
)
def test_every_force_spelling_of_clean_prompts(command, repo, monkeypatch, capsys):
    """The eight-spellings-of-`branch -D` lesson, applied to `clean`. The first
    cut tested only `-fd`, so a regression in the long form would have shipped
    `git clean --force` deleting untracked files with no prompt."""
    (repo / "scratch.txt").write_text("untracked\n", encoding="utf-8")
    payload = _run(command, monkeypatch, capsys, cwd=str(repo))
    assert payload is not None, f"expected an ask for: {command!r}"


@pytest.mark.parametrize("command", ["git clean -f -n", "git clean -f --dry-run"])
def test_force_plus_dry_run_still_deletes_nothing(command, repo, monkeypatch, capsys):
    (repo / "scratch.txt").write_text("untracked\n", encoding="utf-8")
    assert _run(command, monkeypatch, capsys, cwd=str(repo)) is None, command


def test_a_pathless_clean_keeps_its_scope_when_chained_with_a_pathed_one(
    repo, monkeypatch, capsys
):
    """Merging operands across invocations to hold the subprocess count down
    LOST the pathless invocation's scope: the union was `["sub"]`, so the probe
    never looked at the root and the first command's deletion went unannounced."""
    (repo / "sub").mkdir()
    (repo / "scratch.txt").write_text("untracked at the root\n", encoding="utf-8")
    payload = _run(
        "git clean -fd && git clean -fd sub", monkeypatch, capsys, cwd=str(repo)
    )
    assert payload is not None
    assert "git clean" in _reason(payload)


# --- false positives the worktree column removes ----------------------------- #


def test_unstaging_stays_silent(dirty, monkeypatch, capsys):
    """`git restore --staged <path>` rewrites the INDEX from HEAD and never
    touches the working tree. It is the canonical 'unstage this' command, so a
    prompt here is the routine prompt that makes every OTHER prompt unread.

    The file is staged and THEN modified again, so porcelain reads `MM`. That
    state is load-bearing: at plain `M ` the worktree column already reports
    'safe' and this test passes with the `--staged` skip deleted, which is
    exactly how it survived the mutation gate on its first cut. `MM` is the
    state where only the skip can keep it silent."""
    _git(dirty, "add", "tracked.txt")
    (dirty / "tracked.txt").write_text("original\nand more\n", encoding="utf-8")
    assert _run(
        "git restore --staged tracked.txt", monkeypatch, capsys, cwd=str(dirty)
    ) is None


def test_unstaging_that_also_restores_the_worktree_still_prompts(
    dirty, monkeypatch, capsys
):
    """Non-vacuity partner: `--staged --worktree` together DO reach the tree, so
    only the staged-WITHOUT-worktree form may be skipped."""
    _git(dirty, "add", "tracked.txt")
    (dirty / "tracked.txt").write_text("original\nmore still\n", encoding="utf-8")
    payload = _run(
        "git restore --staged --worktree tracked.txt",
        monkeypatch, capsys, cwd=str(dirty),
    )
    assert payload is not None
    assert "discard of uncommitted work" in _reason(payload)


def test_a_staged_file_whose_worktree_matches_the_index_stays_silent(
    dirty, monkeypatch, capsys
):
    """Porcelain `M ` -- staged, worktree identical to the index. `git checkout
    -- <path>` copies the index over a file that already equals it, so it is a
    literal no-op."""
    _git(dirty, "add", "tracked.txt")
    assert _run(
        "git checkout -- tracked.txt", monkeypatch, capsys, cwd=str(dirty)
    ) is None


def test_a_file_deleted_in_the_worktree_stays_silent(repo, monkeypatch, capsys):
    """Porcelain ` D`. A checkout RESTORES the file -- the one case where the
    command is the opposite of destructive."""
    (repo / "tracked.txt").unlink()
    assert _run(
        "git checkout -- tracked.txt", monkeypatch, capsys, cwd=str(repo)
    ) is None


# --- batch probing ----------------------------------------------------------- #


def test_one_bad_pathspec_does_not_silence_the_rest_of_the_batch(
    dirty, monkeypatch, capsys
):
    """Operands are merged into one probe to hold the subprocess count down, and
    git rejects the WHOLE call for one bad pathspec. 'git is about to reject the
    real command the same way' is true per invocation and false per batch: the
    shell runs the second command and it succeeds."""
    payload = _run(
        "git checkout -- ../outside.txt && git checkout -- tracked.txt",
        monkeypatch, capsys, cwd=str(dirty),
    )
    assert payload is not None
    assert "discard of uncommitted work" in _reason(payload)


def test_a_single_rejected_pathspec_is_still_silent(dirty, monkeypatch, capsys):
    """Non-vacuity partner for the test above: with ONE path the refusal
    argument is exactly true, so the fallback must not fire and turn a
    guaranteed-to-fail command into a prompt."""
    assert _run(
        "git checkout -- ../outside.txt", monkeypatch, capsys, cwd=str(dirty)
    ) is None


# --- claims the code's own comments make ------------------------------------- #


def _counting_probe(monkeypatch):
    """Wrap `_run_git` with a call counter, delegating to the real one."""
    calls: list[list[str]] = []
    real = hook._run_git

    def counted(cwd, args):
        calls.append(list(args))
        return real(cwd, args)

    monkeypatch.setattr(hook, "_run_git", counted)
    return calls


def test_the_probe_count_stays_bounded_however_long_the_chain(
    dirty, monkeypatch, capsys
):
    """`HOOK_WORST_CASE_SECONDS["ask-destructive-git.py"] = 12.0` is DERIVED from
    the claim that a hook run makes at most four probes, and feeds the
    dispatcher's handler budget. Nothing else in the suite counts subprocesses,
    so a refactor to a per-invocation probe would make that entry a fiction with
    no red run anywhere."""
    calls = _counting_probe(monkeypatch)
    chain = " && ".join("git checkout tracked.txt" for _ in range(6))
    _run(chain + " && git clean -fd && git clean -fd sub", monkeypatch, capsys,
         cwd=str(dirty))
    # Exactly two, not merely "at most three": one discard probe and one clean
    # probe. An upper bound of 3 is satisfied by a per-invocation probe on a
    # short chain, which is the mutation this is here to kill.
    assert len(calls) == 2, calls


def test_the_whole_tree_fallback_is_probed_at_most_once(
    dirty, monkeypatch, capsys
):
    """The memoisation, which the bounded-chain test above cannot reach: it
    never triggers a refusal, so the fallback is never called there. A bad
    pathspec in BOTH batches makes both fall back, and only the shared cache
    keeps that to one extra process rather than two."""
    (dirty / "sub").mkdir()
    calls = _counting_probe(monkeypatch)
    _run(
        "git checkout -- ../outside.txt && git checkout -- tracked.txt"
        " && git clean -fd ../outside && git clean -fd sub",
        monkeypatch, capsys, cwd=str(dirty),
    )
    assert len(calls) == 3, calls


def test_a_branch_name_reaches_the_probe_as_a_pathspec(dirty, monkeypatch, capsys):
    """`git checkout main` is silent because the probe resolves `main` as a
    pathspec that matches nothing -- NOT because anything parses branches. A
    bare `is None` cannot tell those apart, and would still pass if a parser
    were added, so assert the name actually reached the probe's argv."""
    calls = _counting_probe(monkeypatch)
    assert _run("git checkout main", monkeypatch, capsys, cwd=str(dirty)) is None
    assert any("main" in args for args in calls), calls


def test_two_quoted_paths_both_reach_the_probe(repo, monkeypatch, capsys):
    """The single-quoted-operand case catches a total failure of the offset
    round trip but not a DRIFT, where the first operand survives and later ones
    slide. Two spaced paths, only the SECOND dirty, is what discriminates."""
    for name in ("a b.txt", "c d.txt"):
        (repo / name).write_text("x\n", encoding="utf-8")
        _git(repo, "add", name)
    _git(repo, "commit", "-qm", "spaced")
    (repo / "c d.txt").write_text("x\ny\n", encoding="utf-8")
    payload = _run(
        'git checkout -- "a b.txt" "c d.txt"', monkeypatch, capsys, cwd=str(repo)
    )
    assert payload is not None
    assert "discard of uncommitted work" in _reason(payload)


# --- the probe seam, tested directly ----------------------------------------- #
# Real git cannot produce a non-zero return WITH matching output, so the branch
# that distinguishes "git refused" from "git looked and found nothing" is
# unreachable from a repository fixture -- both produce empty output, and
# deleting the branch entirely left the whole suite green. test-quality-gates.md's
# answer to a state planting cannot reach is to prove it structurally.


def _completed(returncode: int, stdout: str):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout)


def test_a_refusal_is_not_read_as_an_answer(repo, monkeypatch):
    monkeypatch.setattr(hook, "_run_git", lambda cwd, args: _completed(128, "?? x\n"))
    assert hook._holds_work(
        str(repo), ["x"], {"untracked"}, False, lambda: []
    ) is False


def test_the_same_output_with_a_zero_return_is_read_as_an_answer(repo, monkeypatch):
    """Non-vacuity partner: without it, the test above passes against a probe
    that returns False for everything."""
    monkeypatch.setattr(hook, "_run_git", lambda cwd, args: _completed(0, "?? x\n"))
    assert hook._holds_work(
        str(repo), ["x"], {"untracked"}, False, lambda: []
    ) is True


def test_a_raise_in_the_probe_does_not_drop_the_other_guards(
    dirty, monkeypatch, capsys
):
    """The dispatcher DISCARDS an errored hook's stdout, so an exception in the
    new code -- which runs after the four text-only reasons are already
    collected -- would silently un-prompt a force-push. Failing to check is the
    'could not run' case, so it asks."""
    def boom(*args, **kwargs):
        raise RuntimeError("probe exploded")

    monkeypatch.setattr(hook, "_status_lines", boom)
    reason = _reason(
        _run(
            "git push --force origin x && git checkout tracked.txt",
            monkeypatch, capsys, cwd=str(dirty),
        )
    )
    assert "force-push" in reason
    assert "COULD NOT BE RUN" in reason


def test_the_unchecked_reason_does_not_claim_a_measurement(
    repo, monkeypatch, capsys
):
    """`DISCARD_REASON` ends 'the path(s) named here hold such changes right
    now', which is a measurement -- and the exception path is the one branch
    where nothing was measured. Reusing it made the prompt assert a fact it did
    not have, in the one case where the guard is blind, for a command that names
    no path and runs no checkout."""
    def boom(*args, **kwargs):
        raise RuntimeError("probe exploded")

    monkeypatch.setattr(hook, "_status_lines", boom)
    reason = _reason(_run("git clean -fdx", monkeypatch, capsys, cwd=str(repo)))
    assert "COULD NOT BE RUN" in reason
    assert "hold such changes right now" not in reason


def test_a_raise_leaves_a_trace_on_stderr(repo, monkeypatch, capsys):
    """Without it, a coding bug in the operand parser degrades this guard to
    'always ask' indefinitely and nothing says why."""
    def boom(*args, **kwargs):
        raise RuntimeError("probe exploded")

    monkeypatch.setattr(hook, "_status_lines", boom)
    monkeypatch.setattr(
        sys, "stdin",
        io.StringIO(json.dumps({
            "tool_input": {"command": "git checkout -- tracked.txt"},
            "cwd": str(repo),
        })),
    )
    assert hook.main() == 0
    err = capsys.readouterr().err
    assert "RuntimeError" in err and "probe exploded" in err


# --- long-option abbreviations ----------------------------------------------- #
# git accepts any UNAMBIGUOUS abbreviation, and each command's floor depends on
# its own option set. `git branch`'s rules carried this reasoning; the four
# commands added here did not, so every row below was SILENT while really
# discarding the tree.


@pytest.mark.parametrize(
    "command",
    [
        "git checkout --forc",
        "git checkout --fo",
        "git checkout --f",
        "git checkout --f main",
        "git switch --discard-change main",
        "git switch --discar main",
        "git switch --di main",
    ],
)
def test_an_abbreviated_force_flag_still_prompts(command, dirty, monkeypatch, capsys):
    payload = _run(command, monkeypatch, capsys, cwd=str(dirty))
    assert payload is not None, f"expected an ask for: {command!r}"
    assert "FORCED checkout or switch" in _reason(payload)


@pytest.mark.parametrize("command", ["git clean --f", "git clean --forc -d"])
def test_an_abbreviated_clean_force_still_prompts(command, repo, monkeypatch, capsys):
    (repo / "scratch.txt").write_text("untracked\n", encoding="utf-8")
    payload = _run(command, monkeypatch, capsys, cwd=str(repo))
    assert payload is not None, f"expected an ask for: {command!r}"
    assert "git clean" in _reason(payload)


def test_an_abbreviated_worktree_flag_is_seen(dirty, monkeypatch, capsys):
    """`_RESTORE_WORKTREE` appears under a NOT, so failing to match an
    abbreviation DROPS the invocation rather than merely widening it.
    `git restore --staged --w <path>` resets index AND worktree, and was
    silent."""
    _git(dirty, "add", "tracked.txt")
    (dirty / "tracked.txt").write_text("original\nand more\n", encoding="utf-8")
    payload = _run(
        "git restore --staged --w tracked.txt", monkeypatch, capsys, cwd=str(dirty)
    )
    assert payload is not None
    assert "discard of uncommitted work" in _reason(payload)


def test_an_abbreviated_staged_flag_is_still_exempt(dirty, monkeypatch, capsys):
    """The other direction: `--st` is an unstage too, so the exemption must
    cover it or the routine-prompt problem returns for that spelling."""
    _git(dirty, "add", "tracked.txt")
    (dirty / "tracked.txt").write_text("original\nand more\n", encoding="utf-8")
    assert _run(
        "git restore --st tracked.txt", monkeypatch, capsys, cwd=str(dirty)
    ) is None


def test_the_abbreviation_generator_bottoms_out_at_the_floor():
    """A prefix SHORTER than the floor is ambiguous and git refuses it, so
    matching it would be a false positive. Asserted on the generator directly --
    the hand-written nesting it replaced shipped with unbalanced parentheses,
    which made the whole module fail to import and every check in it silently
    stop running."""
    import re as _re

    pattern = _re.compile(hook._abbrev("worktree", 1) + "$")
    assert pattern.match("worktree") and pattern.match("w") and pattern.match("work")
    assert not pattern.match("") and not pattern.match("worktrees")


# --- the index column, which a FORCED discard puts at stake ------------------ #


@pytest.fixture
def staged_only(repo: Path) -> Path:
    """Staged, with the worktree matching the index -- porcelain `M ` and `A `.
    `newfile.txt` is in no commit anywhere, so a forced checkout deletes it with
    nothing to recover from."""
    _git(repo, "branch", "other")
    (repo / "tracked.txt").write_text("original\nSTAGED WORK\n", encoding="utf-8")
    (repo / "newfile.txt").write_text("NEVER COMMITTED ANYWHERE\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt", "newfile.txt")
    return repo


@pytest.mark.parametrize(
    "command",
    ["git checkout -f other", "git switch -f other", "git switch --discard-changes other"],
)
def test_a_forced_branch_change_prompts_on_staged_only_work(
    command, staged_only, monkeypatch, capsys
):
    """Measured: really running `git checkout -f other` on this tree reverts
    `tracked.txt` and DELETES `newfile.txt`, leaving an empty status. The
    sibling `git reset --hard` rule already prompts on the identical tree, so
    calling this state safe made the two disagree."""
    payload = _run(command, monkeypatch, capsys, cwd=str(staged_only))
    assert payload is not None, f"expected an ask for: {command!r}"
    assert "FORCED checkout or switch" in _reason(payload)


def test_a_pathed_discard_stays_silent_on_the_same_staged_only_tree(
    staged_only, monkeypatch, capsys
):
    """Non-vacuity partner, and the reason the two callers want different kinds:
    a PATHED `git checkout --` copies the index over a file that already equals
    it, which really is a no-op. Widening both callers would reintroduce the
    routine prompt the worktree-column fix removed."""
    assert _run(
        "git checkout -- tracked.txt", monkeypatch, capsys, cwd=str(staged_only)
    ) is None


def test_a_forced_checkout_on_a_conflicted_tree_prompts(repo, monkeypatch, capsys):
    """Unmerged `UD` has `D` in the worktree column and was classified safe, so
    a forced checkout threw away the conflict resolution silently. The work in a
    conflicted file exists in no commit and no reflog."""
    _git(repo, "checkout", "-q", "-b", "side")
    (repo / "tracked.txt").write_text("side change\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "side")
    _git(repo, "checkout", "-q", "main")
    (repo / "tracked.txt").unlink()
    _git(repo, "commit", "-qam", "delete on main")
    merge = subprocess.run(
        ["git", "-C", str(repo), "merge", "side"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert merge.returncode != 0, "expected a modify/delete conflict"
    (repo / "tracked.txt").write_text("HOURS OF RESOLUTION WORK\n", encoding="utf-8")
    payload = _run("git checkout -f", monkeypatch, capsys, cwd=str(repo))
    assert payload is not None, _git_status(repo)
    assert "FORCED checkout or switch" in _reason(payload)


def _git_status(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout


@pytest.mark.parametrize(
    "porcelain,expected",
    [
        ("?? new.txt", "untracked"),
        ("!! ign.txt", "ignored"),
        (" M a.txt", "worktree"),
        ("MM a.txt", "worktree"),
        ("M  a.txt", "index"),
        ("A  a.txt", "index"),
        ("MD a.txt", "index"),
        (" D a.txt", "safe"),
        ("R  a -> b", "index"),
        ("UD a.txt", "worktree"),
        ("UU a.txt", "worktree"),
        ("DD a.txt", "worktree"),
        ("AA a.txt", "worktree"),
        ("DU a.txt", "worktree"),
    ],
)
def test_the_porcelain_classification(porcelain, expected):
    """The table, so a change to one state cannot silently move another. `MD`
    is the one worth reading twice: deleted in the worktree (so a pathed
    checkout restores it) but STAGED-modified, so a forced one loses that."""
    assert hook._line_kind(porcelain) == expected


# --- git switch is matched only in its forced form --------------------------- #


@pytest.mark.parametrize(
    "command", ["git switch -c docs", "git switch --create docs", "git switch -C docs"]
)
def test_creating_a_branch_by_switch_never_prompts(command, repo, monkeypatch, capsys):
    """`_VALUE_OPTS` carries `-b`/`-B` for checkout but not switch's `-c`/`-C`,
    so the branch name reached the probe as a pathspec and `git switch -c docs`
    prompted whenever a `docs/` path was dirty. A bare switch refuses on
    conflict, so every path it contributes is pure false-positive surface --
    which the module docstring already claimed was handled. (`-C` over an
    EXISTING branch holding unique commits does ask; `docs` does not exist.)"""
    (repo / "docs").mkdir()
    (repo / "docs" / "x.md").write_text("a\n", encoding="utf-8")
    _git(repo, "add", "docs/x.md")
    _git(repo, "commit", "-qm", "docs")
    (repo / "docs" / "x.md").write_text("a\nb\n", encoding="utf-8")
    assert _run(command, monkeypatch, capsys, cwd=str(repo)) is None, command


# --- the last separator position ---------------------------------------------- #
# `_SEP` was introduced to stop a backslash continuation being a silent bypass,
# and was applied at every position EXCEPT inside `GIT_GLOBAL_OPTS`, which kept
# a plain `\s+`. That one omission disarmed every rule in this file at once --
# force-push and `reset --hard` included, neither of which this change is about.
# Verified in a real shell: `git -C <repo> \`+newline+`status --porcelain`
# exits 0 with correct output, so the shape really runs.


@pytest.mark.parametrize(
    "command,expected",
    [
        ("git -C . \\\ncheckout -f", "FORCED checkout or switch"),
        # The continuation BETWEEN a global option and its value, which is a
        # different separator position inside the same blob. Without this row a
        # mutation reverting only the `-[cC]` separator survives every case
        # above, because those all continue AFTER the option-value pair.
        ("git -C \\\n. checkout -f", "FORCED checkout or switch"),
        ("git --git-dir \\\n.git push --force origin f", "force-push"),
        ("git -C . \\\npush --force origin f", "force-push"),
        ("git -C . \\\nreset --hard", "reset --hard"),
        ("git --no-pager \\\nreset --hard", "reset --hard"),
        ("git -c core.x=y \\\nclean -fdx", "git clean"),
        ("git --git-dir .git \\\nbranch -D feature/x", "force-delete"),
    ],
)
def test_a_continuation_after_a_global_option_does_not_disarm_a_rule(
    command, expected, dirty, monkeypatch, capsys
):
    (dirty / "junk.txt").write_text("untracked\n", encoding="utf-8")
    payload = _run(command, monkeypatch, capsys, cwd=str(dirty))
    assert payload is not None, f"expected an ask for: {command!r}"
    assert expected in _reason(payload)


def test_a_bare_newline_after_a_global_option_is_still_a_command_boundary(
    dirty, monkeypatch, capsys
):
    """The same plain `\\s+` was wrong in BOTH directions: it also matched a bare
    newline, so a global option on one line and a subcommand word on the next
    read as ONE command. `_SEP` fixes both, and this pins the direction that is
    easy to lose while fixing the other.

    The command is synthetic, and every part of its shape is load-bearing. The
    newline must sit IMMEDIATELY after the global options, and the next line must
    start with the bare subcommand word. Two earlier cuts were vacuous and each
    passed against the bug it was written to catch:

      git -c x=y status\\ngit push origin f   -- line 2 matches on its own merits
      git -c x=y status\\npush --force …      -- `status` sits between the options
                                                and the newline, so `push` never
                                                lines up under either separator

    Only with the options abutting the newline does the option-consuming blob
    have to cross it, which is the thing being pinned."""
    assert _run(
        "git -c core.x=y\npush --force origin f",
        monkeypatch, capsys, cwd=str(dirty),
    ) is None


# =========================================================================== #
# The construct matrix
#
# WHY THIS EXISTS. Four review rounds over this hook each found roughly five
# real bypasses, and every one after the first had the SAME shape: a construct
# was handled correctly for one rule and not carried to the others. The list is
# not anecdote -- each row below is a bug that shipped and was found by a human
# or an agent reading the file, never by a test:
#
#   line continuation abutting a flag   fixed for `branch -D`, missed on
#                                       `--force` and `--hard` for three rounds
#   continuation at a separator         fixed at `git`->subcommand, missed
#                                       inside `GIT_GLOBAL_OPTS`
#   long-option abbreviation            fixed for `branch`, then for four new
#                                       commands, never carried back to `reset`
#   `.exe`/case spelling of `git`       fixed for force-push, missed on
#                                       branch-delete until a mutation caught it
#
# The cause is structural: every rule is hand-written per command, so each new
# construct has to be manually carried to N places and one gets missed. A test
# per bug cannot fix that -- it pins the instance, not the class.
#
# So this is a CROSS PRODUCT, not a list of cases. Every rule x every construct.
# Adding a rule to `RULES` immediately demands it handle every construct;
# adding a construct to `CONSTRUCTS` immediately demands every rule handle it.
# The displacement becomes a red test rather than the next reviewer's finding.
#
# HOW TO EXTEND. Add the rule or construct and run it. If a cell legitimately
# does not apply -- a command has no long flag to abbreviate, say -- put it in
# `_INAPPLICABLE` with the reason. An empty exemption is not allowed to be
# silent, which `test_no_inapplicable_cell_is_a_placeholder` enforces.
# =========================================================================== #


# (id, a command that MUST prompt, the reason fragment it must carry)
RULES = [
    ("force-push", "git push --force origin feat", "force-push"),
    ("force-push-short", "git push -f origin feat", "force-push"),
    ("reset-hard", "git reset --hard", "reset --hard"),
    ("branch-delete", "git branch -D feat", "force-delete"),
    ("discard-pathed", "git checkout -- tracked.txt", "discard of uncommitted work"),
    ("discard-restore", "git restore tracked.txt", "discard of uncommitted work"),
    ("discard-forced", "git checkout -f", "FORCED checkout or switch"),
    ("clean", "git clean -fd", "git clean"),
    ("rebase-published", "git rebase --root main", "rewrites commits already on a remote"),
    ("branch-reset", "git switch -C uniq", "orphans them"),
    ("branch-reset-checkout", "git checkout -B uniq", "orphans them"),
    ("merge-switch", "git switch -m feat", "merging branch change"),
]

# Each construct rewrites a command's text. `None` from a rewriter means the
# construct does not apply to that command, which `_INAPPLICABLE` must justify.


def _exe_spelling(command):
    return command.replace("git ", "git.exe ", 1)


def _upper_spelling(command):
    return command.replace("git ", "GIT ", 1)


def _continuation_after_git(command):
    return command.replace("git ", "git \\\n", 1)


def _continuation_before_flag(command):
    """A continuation immediately BEFORE the first flag."""
    parts = command.split(" ")
    for i, tok in enumerate(parts):
        if tok.startswith("-"):
            return " ".join(parts[:i]) + " \\\n" + " ".join(parts[i:])
    return None


def _continuation_abutting_flag(command):
    """A continuation with NO space before it, abutting the flag it follows.

    The shell strips `\\`+newline before word-splitting, so this really runs --
    and a terminator of `(?:\\s|$)` rejects it because the backslash sits
    directly against the flag's last character. Missed on `--force`/`--hard`
    for three rounds after being fixed on `git branch -D`.
    """
    parts = command.split(" ")
    for i, tok in enumerate(parts):
        if tok.startswith("-") and i + 1 < len(parts):
            return " ".join(parts[: i + 1]) + "\\\n  " + " ".join(parts[i + 1:])
    return None


def _global_option(command):
    return command.replace("git ", "git -C . ", 1)


def _global_option_continuation(command):
    return command.replace("git ", "git -C . \\\n", 1)


def _chained(command):
    return "git status --porcelain && " + command


CONSTRUCTS = [
    ("exe-spelling", _exe_spelling),
    ("upper-spelling", _upper_spelling),
    ("continuation-after-git", _continuation_after_git),
    ("continuation-before-flag", _continuation_before_flag),
    ("continuation-abutting-flag", _continuation_abutting_flag),
    ("global-option", _global_option),
    ("global-option-continuation", _global_option_continuation),
    ("chained", _chained),
]

# (rule_id, construct_id) -> why the cell cannot apply. Every entry is a claim
# that must be re-derivable; a bare "n/a" is rejected by the test below.
_INAPPLICABLE: dict[tuple[str, str], str] = {
    # `git checkout -f` has no token after its flag, so there is nothing for a
    # continuation to abut. The `-f main` form is covered by its own test.
    ("discard-forced", "continuation-abutting-flag"):
        "no token follows the flag in this command, so the construct has no site",
    ("clean", "continuation-abutting-flag"):
        "no token follows the flag in this command, so the construct has no site",
    ("reset-hard", "continuation-abutting-flag"):
        "no token follows the flag in this command; the `--hard HEAD~1` form is "
        "covered by test_a_continuation_abutting_the_hard_flag_still_prompts",
    # `git checkout -- tracked.txt` and `git restore tracked.txt`: the first
    # dash-prefixed token is the `--` separator itself, so inserting a
    # continuation before or abutting it produces a different command shape
    # rather than the same one spelled differently.
    ("discard-pathed", "continuation-abutting-flag"):
        "the only dash-prefixed token is the `--` separator, not a flag",
    # `git restore tracked.txt` carries no flag at all, so neither
    # flag-positioned continuation has anywhere to go. The flagged forms of the
    # same rule (`--staged`, `--worktree`) are covered by their own tests above.
    ("discard-restore", "continuation-before-flag"):
        "this command carries no flag, so a flag-positioned construct has no site",
    ("discard-restore", "continuation-abutting-flag"):
        "this command carries no flag, so a flag-positioned construct has no site",
}


@pytest.fixture
def matrix_repo(repo: Path) -> Path:
    """Dirty enough that EVERY rule above has something real to find: the seed
    commit is on `origin/main` (a rebase rewrites it), `uniq` holds a commit
    nothing else reaches (a reset orphans it), and `staged.txt` is staged."""
    _git(repo, "branch", "feat")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    tree = subprocess.run(
        ["git", "-C", str(repo), "commit-tree", "HEAD^{tree}", "-p", "HEAD", "-m", "u1"],
        check=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout.strip()
    _git(repo, "update-ref", "refs/heads/uniq", tree)
    (repo / "staged.txt").write_text("staged\n", encoding="utf-8")
    _git(repo, "add", "staged.txt")
    (repo / "tracked.txt").write_text("original\nuncommitted\n", encoding="utf-8")
    (repo / "scratch.txt").write_text("untracked\n", encoding="utf-8")
    return repo


@pytest.mark.parametrize("rule_id,command,fragment", RULES, ids=[r[0] for r in RULES])
@pytest.mark.parametrize("construct_id,rewrite", CONSTRUCTS, ids=[c[0] for c in CONSTRUCTS])
def test_every_rule_survives_every_construct(
    rule_id, command, fragment, construct_id, rewrite, matrix_repo, monkeypatch, capsys
):
    if (rule_id, construct_id) in _INAPPLICABLE:
        pytest.skip(_INAPPLICABLE[(rule_id, construct_id)])
    rewritten = rewrite(command)
    assert rewritten is not None, (
        f"{construct_id} could not be applied to {command!r}; either the "
        "rewriter is wrong or the cell belongs in _INAPPLICABLE with a reason"
    )
    payload = _run(rewritten, monkeypatch, capsys, cwd=str(matrix_repo))
    assert payload is not None, (
        f"{rule_id} went SILENT under {construct_id}: {rewritten!r}"
    )
    assert fragment in _reason(payload), (
        f"{rule_id} prompted for the wrong reason under {construct_id}: "
        f"{rewritten!r}"
    )


def test_the_matrix_is_not_vacuous(matrix_repo, monkeypatch, capsys):
    """Every base command must prompt UNMODIFIED. Without this the whole matrix
    could pass because the repo state stopped making any rule fire."""
    for rule_id, command, fragment in RULES:
        payload = _run(command, monkeypatch, capsys, cwd=str(matrix_repo))
        assert payload is not None, f"{rule_id} does not fire even unmodified"
        assert fragment in _reason(payload), rule_id


def test_no_inapplicable_cell_is_a_placeholder():
    """An exemption is a claim, and a claim with no reason is how a matrix
    quietly stops covering the thing it was built for."""
    for key, reason in _INAPPLICABLE.items():
        assert len(reason) > 30, f"{key} is exempted with no real reason: {reason!r}"
    stale = [
        k for k in _INAPPLICABLE
        if k[0] not in {r[0] for r in RULES} or k[1] not in {c[0] for c in CONSTRUCTS}
    ]
    assert not stale, f"_INAPPLICABLE names rules/constructs that no longer exist: {stale}"


def test_a_continuation_abutting_the_hard_flag_still_prompts(
    matrix_repo, monkeypatch, capsys
):
    """The cell `_INAPPLICABLE` defers, made explicit so the exemption is not a
    hole. This exact command was silent for three review rounds while the
    identical shape on `git branch -D` had already been fixed."""
    payload = _run(
        "git reset --hard\\\n  HEAD~1", monkeypatch, capsys, cwd=str(matrix_repo)
    )
    assert payload is not None
    assert "reset --hard" in _reason(payload)


@pytest.mark.parametrize(
    "command,fragment",
    [
        ("git reset --h", "reset --hard"),
        ("git reset --ha", "reset --hard"),
        ("git reset --har", "reset --hard"),
    ],
)
def test_an_abbreviated_hard_flag_still_prompts(
    command, fragment, matrix_repo, monkeypatch, capsys
):
    """`--hard` is `git reset`'s only `--h*` option, so every prefix down to
    `--h` resolves. Measured: `git reset --h` performed a full hard reset while
    the hook printed nothing -- the abbreviation reasoning was carried to
    `branch` and to four new commands, and never back to the rule the module
    docstring names first."""
    payload = _run(command, monkeypatch, capsys, cwd=str(matrix_repo))
    assert payload is not None, f"expected an ask for: {command!r}"
    assert fragment in _reason(payload)


def test_push_force_is_not_abbreviated_because_git_refuses_it(
    matrix_repo, monkeypatch, capsys
):
    """The other half of the abbreviation rule, and the reason each floor has to
    be read off its OWN command's option set: `git push` also has
    `--follow-tags`, `--force-with-lease` and `--force-if-includes`, so `--forc`
    is ambiguous and git refuses it. Matching it would be a false positive on a
    command that cannot run."""
    assert _run(
        "git push --forc origin feat", monkeypatch, capsys, cwd=str(matrix_repo)
    ) is None


# --- pathed discards that also reset the index ------------------------------- #


@pytest.mark.parametrize(
    "command",
    [
        "git restore --staged --worktree tracked.txt",
        "git restore -SW tracked.txt",
        "git restore --staged --w tracked.txt",
        "git checkout HEAD -- tracked.txt",
        "git checkout main -- tracked.txt",
    ],
)
def test_a_pathed_discard_that_resets_the_index_prompts_on_staged_only_work(
    command, staged_only, monkeypatch, capsys
):
    """These are PATHED, so they took `{"worktree"}` -- and they reset the index
    too, so on a staged-but-clean-in-tree file they were silent while really
    wiping the staged content. Measured: running `git checkout HEAD --
    tracked.txt` left an empty status. The `--staged --w` spelling is the one the
    previous round added abbreviation matching for, which then reached a probe
    whose wanted-set made it silent anyway."""
    payload = _run(command, monkeypatch, capsys, cwd=str(staged_only))
    assert payload is not None, f"expected an ask for: {command!r}"
    assert "discard of uncommitted work" in _reason(payload)


def test_a_bare_pathed_discard_is_still_silent_on_staged_only_work(
    staged_only, monkeypatch, capsys
):
    """Non-vacuity partner, and the reason the wanted-set is per invocation
    rather than widened for everyone: a bare `git checkout -- <path>` copies the
    index over a file that already equals it, which really is a no-op."""
    assert _run(
        "git checkout -- tracked.txt", monkeypatch, capsys, cwd=str(staged_only)
    ) is None


def test_an_untracked_collision_prompts_on_a_forced_branch_change(
    repo, monkeypatch, capsys
):
    """`-f` also overrides git's refusal to clobber an untracked file colliding
    with one in the target branch. Measured: a tree holding only
    `?? collide.txt` was silent, and the real command overwrote it with the
    branch's version -- content in no commit and no reflog."""
    _git(repo, "checkout", "-q", "-b", "other")
    (repo / "collide.txt").write_text("from the branch\n", encoding="utf-8")
    _git(repo, "add", "collide.txt")
    _git(repo, "commit", "-qm", "add collide")
    _git(repo, "checkout", "-q", "main")
    (repo / "collide.txt").write_text("UNCOMMITTED UNTRACKED WORK\n", encoding="utf-8")
    payload = _run("git checkout -f other", monkeypatch, capsys, cwd=str(repo))
    assert payload is not None
    assert "FORCED checkout or switch" in _reason(payload)


@pytest.mark.parametrize("command", ["git clean -f --d", "git clean -f --dr", "git clean -f --dry"])
def test_an_abbreviated_dry_run_still_deletes_nothing(
    command, repo, monkeypatch, capsys
):
    """`--dry-run` is clean's only `--d*` option, so these are genuine dry runs.
    Over-prompting on them is the noise this rule's own rationale says makes the
    checkpoint stop being read."""
    (repo / "scratch.txt").write_text("untracked\n", encoding="utf-8")
    assert _run(command, monkeypatch, capsys, cwd=str(repo)) is None, command


# --------------------------------------------------------------------------- #
# `git stash` during a merge, cherry-pick or revert (issue #398)
# --------------------------------------------------------------------------- #
# Real repositories throughout: the hook's whole signal is whether a marker file
# exists in the git dir, so a mocked probe would test the mock.


def _commit_file(repo: Path, name: str, text: str, msg: str) -> None:
    (repo / name).write_text(text, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-qm", msg)


def _conflicted_merge(repo: Path) -> None:
    """Leave `repo` mid-merge with a conflict, so MERGE_HEAD exists."""
    _git(repo, "checkout", "-qb", "side")
    _commit_file(repo, "tracked.txt", "side\n", "side")
    _git(repo, "checkout", "-q", "main")
    _commit_file(repo, "tracked.txt", "main\n", "main")
    subprocess.run(["git", "-C", str(repo), "merge", "side"], capture_output=True)
    assert (repo / ".git" / "MERGE_HEAD").exists()


def _conflicted_pick(repo: Path, verb: str) -> None:
    """Mid cherry-pick or revert, conflicted, so the matching marker exists."""
    _git(repo, "checkout", "-qb", "side")
    _commit_file(repo, "tracked.txt", "side\n", "side")
    _git(repo, "checkout", "-q", "main")
    _commit_file(repo, "tracked.txt", "main\n", "main")
    target = "side" if verb == "cherry-pick" else "HEAD~1"
    subprocess.run(["git", "-C", str(repo), verb, target], capture_output=True)
    marker = "CHERRY_PICK_HEAD" if verb == "cherry-pick" else "REVERT_HEAD"
    assert (repo / ".git" / marker).exists()


_SAVING_STASHES = [
    "git stash",
    "git stash push",
    "git stash push -m wip",
    "git stash save wip",
    "git stash -u",
    "git stash --keep-index",
    "git stash push -- tracked.txt",
    "git -C {repo} stash",
    "git stash && git stash pop",
]


# requirement: git-guards / A stash during an unfinished merge asks first
@pytest.mark.parametrize("command", _SAVING_STASHES)
def test_a_saving_stash_during_a_merge_asks(command, repo, monkeypatch, capsys):
    _conflicted_merge(repo)
    payload = _run(command.format(repo=repo), monkeypatch, capsys, cwd=str(repo))
    assert payload is not None, command
    reason = _reason(payload)
    assert "MERGE_HEAD" in reason
    assert "git show <ref>:<path>" in reason and "scratch worktree" in reason


@pytest.mark.parametrize("verb", ["cherry-pick", "revert"])
def test_a_saving_stash_during_a_pick_or_revert_asks(verb, repo, monkeypatch, capsys):
    _conflicted_pick(repo, verb)
    payload = _run("git stash", monkeypatch, capsys, cwd=str(repo))
    assert payload is not None
    assert "cherry-pick or revert" in _reason(payload)


def test_a_stash_with_no_operation_in_progress_is_silent(repo, monkeypatch, capsys):
    """Non-vacuity partner: the same commands, same repo, no marker file."""
    (repo / "tracked.txt").write_text("dirty\n", encoding="utf-8")
    for command in _SAVING_STASHES:
        assert _run(command.format(repo=repo), monkeypatch, capsys, cwd=str(repo)) is None, command


@pytest.mark.parametrize(
    "command",
    [
        "git stash list",
        "git stash show",
        "git stash show -p stash@{0}",
        "git stash pop",
        "git stash apply",
        "git stash drop",
        "git stash clear",
        "git stash create",
        "git stash store abc123",
        "git stash branch newbranch",
        "git status && git stash list",
        'echo "git stash"',
    ],
)
def test_non_saving_stash_forms_stay_silent_during_a_merge(
    command, repo, monkeypatch, capsys
):
    _conflicted_merge(repo)
    assert _run(command, monkeypatch, capsys, cwd=str(repo)) is None, command


def test_a_worktree_checks_its_own_marker(repo, tmp_path, monkeypatch, capsys):
    """A linked worktree keeps MERGE_HEAD in `.git/worktrees/<name>/`, not in
    the main `.git`. Each side must be judged on its own marker."""
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", "-b", "wtbranch", str(wt))
    _commit_file(wt, "other.txt", "wt\n", "wt change")
    _git(repo, "branch", "side", "main")
    _git(repo, "checkout", "-q", "side")
    _commit_file(repo, "other.txt", "side\n", "side change")
    _git(repo, "checkout", "-q", "main")
    subprocess.run(["git", "-C", str(wt), "merge", "side"], capture_output=True)
    marker = subprocess.run(
        ["git", "-C", str(wt), "rev-parse", "--absolute-git-dir"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout.strip()
    assert (Path(marker) / "MERGE_HEAD").exists()
    assert not (repo / ".git" / "MERGE_HEAD").exists()
    # The worktree is mid-merge, the main checkout is not.
    assert _run("git stash", monkeypatch, capsys, cwd=str(wt)) is not None
    assert _run("git stash", monkeypatch, capsys, cwd=str(repo)) is None
    # `git -C` redirects the probe from either starting directory.
    assert _run(f'git -C "{wt}" stash', monkeypatch, capsys, cwd=str(repo)) is not None
    assert _run(f"git -C {repo} stash", monkeypatch, capsys, cwd=str(wt)) is None


def test_a_relative_dash_c_resolves_against_the_cwd(repo, monkeypatch, capsys):
    _conflicted_merge(repo)
    (repo / "sub").mkdir()
    assert _run("git -C .. stash", monkeypatch, capsys, cwd=str(repo / "sub")) is not None
    assert _run("git -C . stash", monkeypatch, capsys, cwd=str(repo / "sub")) is not None


def test_stashes_in_two_directories_ask_without_probing_each(
    repo, tmp_path, monkeypatch, capsys
):
    """One probe at most keeps the stated worst case honest; two directories are
    asked about rather than probed, because a missed one would be a bypass."""
    other = tmp_path / "other"
    other.mkdir()
    calls = _counting_probe(monkeypatch)
    payload = _run(f"git stash && git -C {other} stash", monkeypatch, capsys, cwd=str(repo))
    assert payload is not None
    reason = _reason(payload)
    assert hook.STASH_MULTI_DIR_REASON in reason
    # Issue #438: the skip is deliberate, so the prompt must not report a fault.
    assert "COULD NOT BE RUN" not in reason
    assert calls == []


def test_a_raising_stash_check_still_runs_the_discard_and_clean_checks(
    dirty, monkeypatch, capsys
):
    """Issue #438: the stash block shared the discard check's handler, so a
    stash-side exception was logged as the discard check and skipped the discard
    and clean checks. The stash check now fails on its own and asks."""
    def boom(*args, **kwargs):
        raise ValueError("embedded null byte")

    (dirty / "new.txt").write_text("untracked\n", encoding="utf-8")
    monkeypatch.setattr(hook, "_stash_dirs", boom)
    monkeypatch.setattr(
        sys, "stdin",
        io.StringIO(json.dumps({
            "tool_input": {
                "command": "git stash && git checkout -- tracked.txt && git clean -f"
            },
            "cwd": str(dirty),
        })),
    )
    assert hook.main() == 0
    captured = capsys.readouterr()
    reason = _reason(json.loads(captured.out))
    assert reason.count(hook.STASH_UNCHECKED_REASON) == 1
    assert hook.DISCARD_REASON in reason
    assert hook.CLEAN_REASON in reason
    assert "the stash check raised ValueError: embedded null byte" in captured.err
    assert "discard check raised" not in captured.err


def test_a_nul_in_a_stash_dash_c_path_asks_and_keeps_the_discard_check(
    dirty, monkeypatch, capsys
):
    """The real raising site, with nothing patched: a NUL in a `-C` value makes
    the stash probe's subprocess call raise ValueError inside
    `_operation_in_progress`. The stash check asks once and the discard check
    still runs."""
    monkeypatch.setattr(
        sys, "stdin",
        io.StringIO(json.dumps({
            "tool_input": {"command": "git -C a\u0000b stash && git checkout -- tracked.txt"},
            "cwd": str(dirty),
        })),
    )
    assert hook.main() == 0
    captured = capsys.readouterr()
    reason = _reason(json.loads(captured.out))
    assert reason.count(hook.STASH_UNCHECKED_REASON) == 1
    assert hook.DISCARD_REASON in reason
    assert "the stash check raised ValueError" in captured.err


def test_a_stash_makes_exactly_one_probe(repo, monkeypatch, capsys):
    calls = _counting_probe(monkeypatch)
    _run("git stash && git stash push", monkeypatch, capsys, cwd=str(repo))
    assert len(calls) == 1, calls


def test_a_stash_probe_that_cannot_run_asks(repo, monkeypatch, capsys):
    """Fail-closed on 'could not look', like the discard check: git missing or a
    hang is not evidence that no merge is in progress."""
    monkeypatch.setattr(hook, "_run_git", lambda cwd, args: None)
    payload = _run("git stash", monkeypatch, capsys, cwd=str(repo))
    assert payload is not None
    assert "COULD NOT BE RUN" in _reason(payload)


def test_a_stash_probe_that_git_refuses_is_silent(repo, monkeypatch, capsys):
    """Not a repository: git rejects the stash itself. Same rule as a refused
    `git status` probe."""
    monkeypatch.setattr(hook, "_run_git", lambda cwd, args: _completed(128, ""))
    assert _run("git stash", monkeypatch, capsys, cwd=str(repo)) is None


@pytest.mark.parametrize(
    "command",
    [
        "git stash 2>&1",
        "git stash >/dev/null",
        "git stash 2>/dev/null",
        "(git stash)",
        "git stash # wip",
        "git stash list 2>&1 && git stash 2>&1",
    ],
)
def test_a_saving_stash_with_an_unreadable_tail_still_asks(
    command, repo, monkeypatch, capsys
):
    _conflicted_merge(repo)
    assert _run(command, monkeypatch, capsys, cwd=str(repo)) is not None, command


@pytest.mark.parametrize(
    "command",
    [
        "git -C ~/repo stash",
        'git -C "$REPO" stash',
        "git -C $HOME/repo stash",
        "git --git-dir=/x/.git --work-tree=/x stash",
        "GIT_DIR=/x/.git git stash",
        "git -C /no/such/dir/at/all stash",
    ],
)
def test_a_stash_whose_repository_cannot_be_named_asks_as_unchecked(
    command, repo, monkeypatch, capsys
):
    """No merge is in progress anywhere here: the prompt is because the hook
    cannot tell, not because it found one."""
    payload = _run(command, monkeypatch, capsys, cwd=str(repo))
    assert payload is not None, command
    assert "COULD NOT BE RUN" in _reason(payload)


def test_equivalent_directory_spellings_count_once(repo, monkeypatch, capsys):
    calls = _counting_probe(monkeypatch)
    _run("git stash && git -C . stash && git -C sub/.. stash", monkeypatch, capsys, cwd=str(repo))
    assert len(calls) == 1, calls


# =========================================================================== #
# Rebase, branch reset and merging switch
#
# Three history changes git does NOT refuse on its own, each CONDITIONAL like the
# discards: a rebase asks only when it rewrites a commit already on a
# remote-tracking branch, a `switch -C`/`checkout -B` only when the branch it
# resets holds commits nothing else reaches, and a merging switch only when
# changes are staged. Each needs a real repository in a known state.
#
# The `history` repo, built once and copied:
#
#   main     seed -- m2                    origin/main = m2
#   feat     seed -- f1 -- f2  (HEAD)      origin/feat = f1, feat's upstream
#   uniq     m2 -- u1                       on no remote, no other branch
#   lonely   l1                             an unrelated root, on no remote
# =========================================================================== #


def _build_history(root: Path) -> None:
    _build_repo(root)
    _git(root, "config", "remote.origin.url", "https://example.invalid/r.git")
    _git(root, "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*")

    def commit(name: str) -> None:
        (root / f"{name}.txt").write_text(name + "\n", encoding="utf-8")
        _git(root, "add", f"{name}.txt")
        _git(root, "commit", "-qm", name)

    commit("m2")
    _git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    _git(root, "switch", "-qc", "uniq")
    commit("u1")
    _git(root, "switch", "-qc", "feat", "main~1")
    commit("f1")
    _git(root, "update-ref", "refs/remotes/origin/feat", "HEAD")
    commit("f2")
    _git(root, "branch", "-q", "--set-upstream-to=origin/feat", "feat")
    _git(root, "switch", "-q", "--orphan", "lonely")
    commit("l1")
    _git(root, "switch", "-q", "feat")


@pytest.fixture
def history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cached_git_repo) -> Path:
    """The repo drawn above, under the same pinned git config as `repo`."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(tmp_path / "gitconfig-system"))
    return cached_git_repo("ask_destructive_git_history", _build_history, tmp_path / "repo")


def _sha(repo: Path, rev: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", rev],
        check=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout.strip()


def _commit_off(repo: Path, parent: str, message: str) -> str:
    """A new commit on top of `parent`, made without touching the worktree."""
    return subprocess.run(
        ["git", "-C", str(repo), "commit-tree", parent + "^{tree}", "-p", parent, "-m", message],
        check=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout.strip()


def _history_probe(monkeypatch):
    """Record each history probe's argv and timeout, delegating to the real one."""
    calls: list[tuple[list[str], float | None]] = []
    real = hook._run_git

    def counted(cwd, args, timeout=None):
        calls.append((list(args), timeout))
        return real(cwd, args, timeout=timeout)

    monkeypatch.setattr(hook, "_run_git", counted)
    return calls


# --- git rebase ----------------------------------------------------------------


# requirement: git-guards / A rebase of pushed commits asks first
@pytest.mark.parametrize(
    "command",
    [
        "git rebase main",
        "git rebase -i main",
        "git rebase --interactive main",
        "git rebase --onto main main~1",
        "git rebase --ont main main~1",
        "git rebase --root",
        "git rebase --ro",
        "git rebase main feat",
        "git rebase -x 'make test' main",
        "git rebase --exec true main",
        "git rebase -s ort -X theirs main",
        "git rebase --strategy ort main",
        "git rebase --strategy-option theirs main",
        "git rebase --whitespace fix main",
        "git rebase --empty drop main",
        "git rebase -C 3 main",
        "git rebase -xtrue main",
        "git rebase -Sx main",
        'git rebase "main"',
        # `-` is git's `@{-1}`, here `lonely`: every commit of feat moves.
        "git rebase -",
        "git rebase 2> err.log main",
        "git rebase main 2>/dev/null",
        "git rebase main > rebase.log",
        "git rebase main # onto the new base",
        "(git rebase main)",
        "git rebase \\\n  main",
        "git -c core.editor=true rebase main",
        "git -C . rebase main",
        "git fetch && git rebase main",
        "git rebase --continue && git rebase main",
    ],
)
def test_a_rebase_of_a_pushed_commit_asks(command, history, monkeypatch, capsys):
    """`main..feat` holds f1, which is on `origin/feat`: rewriting it needs a
    force-push and leaves anyone who fetched it with duplicates."""
    payload = _run(command, monkeypatch, capsys, cwd=str(history))
    assert payload is not None, f"expected an ask for: {command!r}"
    assert "rewrites commits already on a remote-tracking branch" in _reason(payload)


def test_a_rebase_asks_from_another_directory_through_dash_c(
    history, tmp_path, monkeypatch, capsys
):
    """The probe runs where `-C` points, not at the hook's cwd -- here a
    directory that is not a repository at all."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    payload = _run(f"git -C {history} rebase main", monkeypatch, capsys, cwd=str(elsewhere))
    assert payload is not None
    assert hook.REBASE_REASON in _reason(payload)


def test_a_rebase_of_a_branch_pushed_without_an_upstream_asks(
    history, monkeypatch, capsys
):
    """Published means on ANY remote-tracking branch, not only the upstream: a
    branch pushed without `-u` has no upstream and is published all the same."""
    _git(history, "branch", "-q", "--unset-upstream", "feat")
    payload = _run("git rebase main", monkeypatch, capsys, cwd=str(history))
    assert payload is not None
    assert hook.REBASE_REASON in _reason(payload)


# requirement: git-guards / A rebase of pushed commits asks first
@pytest.mark.parametrize(
    "command",
    [
        # Onto its own upstream: only f2, which is local, is rewritten.
        "git rebase",
        "git rebase origin/feat",
        "git rebase origin/feat feat",
        # A local-only branch onto a fresh base: routine.
        "git rebase main uniq",
        "git rebase --onto main~1 main uniq",
        "git rebase --root lonely",
        # Forced, so they reach the counts: only f2 / u1, which are local.
        "git rebase -f origin/feat",
        "git rebase --no-ff origin/feat",
        "git rebase -i origin/feat",
    ],
)
def test_a_rebase_of_local_commits_stays_silent(command, history, monkeypatch, capsys):
    assert _run(command, monkeypatch, capsys, cwd=str(history)) is None, command


# requirement: git-guards / A rebase of pushed commits asks first
@pytest.mark.parametrize(
    "command",
    [
        "git rebase --continue",
        "git rebase --abort",
        "git rebase --skip",
        "git rebase --quit",
        "git rebase --edit-todo",
        "git rebase --show-current-patch",
        "git rebase --con",
        "git rebase --ab",
        "git rebase --sk",
        "git -C . rebase --abort",
    ],
)
def test_an_action_on_a_rebase_under_way_stays_silent(
    command, history, monkeypatch, capsys
):
    """These act on the rebase already running and rewrite nothing new. The
    probe would otherwise count `@{upstream}..HEAD` and could ask."""
    calls = _history_probe(monkeypatch)
    assert _run(command, monkeypatch, capsys, cwd=str(history)) is None, command
    assert calls == [], calls


def test_a_rebase_with_no_upstream_stays_silent(history, monkeypatch, capsys):
    """`uniq` has no upstream, so a bare `git rebase` is refused by git and the
    probe's `@{upstream}` is refused the same way."""
    _git(history, "switch", "-q", "uniq")
    assert _run("git rebase", monkeypatch, capsys, cwd=str(history)) is None


def test_a_rebase_on_a_dirty_tree_of_local_commits_stays_silent(
    history, monkeypatch, capsys
):
    """git refuses a rebase over unstaged or staged changes itself, and
    `--autostash` keeps them in the stash when the re-apply conflicts
    (measured, git 2.43), so a dirty tree alone loses nothing."""
    (history / "f2.txt").write_text("edited\n", encoding="utf-8")
    _git(history, "add", "f2.txt")
    (history / "tracked.txt").write_text("edited\n", encoding="utf-8")
    for command in ("git rebase origin/feat", "git rebase --autostash origin/feat"):
        assert _run(command, monkeypatch, capsys, cwd=str(history)) is None, command


@pytest.mark.parametrize(
    "command",
    ["GIT_DIR=/x/.git git rebase main", "git --git-dir=/x/.git rebase main"],
)
def test_a_rebase_whose_repository_cannot_be_named_stays_silent(
    command, history, monkeypatch, capsys
):
    """Fail-open, unlike the stash check: the old commits stay in the reflog."""
    assert _run(command, monkeypatch, capsys, cwd=str(history)) is None, command


def test_a_rebase_outside_a_repository_stays_silent(tmp_path, monkeypatch, capsys):
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    assert _run("git rebase main", monkeypatch, capsys, cwd=str(plain)) is None


def test_a_rebase_quoted_in_prose_stays_silent(history, monkeypatch, capsys):
    assert _run(
        'git commit -m "then git rebase main"', monkeypatch, capsys, cwd=str(history)
    ) is None


# --- git switch -C / git checkout -B ---------------------------------------------


# requirement: git-guards / A branch reset that would orphan commits asks first
@pytest.mark.parametrize(
    "command",
    [
        "git switch -C uniq",
        "git switch -C uniq main~1",
        "git switch --force-create uniq",
        "git switch --force-create=uniq",
        "git switch --force- uniq",
        "git switch -Cuniq",
        "git switch -fC uniq",
        "git checkout -B uniq",
        "git checkout -B uniq main~1",
        "git checkout -fB uniq",
        "git checkout -Buniq",
        "git switch -C uniq -t origin/feat",
        "git switch -C uniq --conflict diff3",
        "git -C . switch -C uniq",
        "git -c core.x=y checkout -B uniq",
        "git status && git switch -C uniq",
        "git switch -C \\\n  uniq",
    ],
)
def test_a_reset_of_a_branch_with_unique_commits_asks(
    command, history, monkeypatch, capsys
):
    """u1 is on `uniq` and nowhere else: resetting `uniq` to HEAD (feat) or to
    main~1 orphans it, and git does it without a word (measured)."""
    payload = _run(command, monkeypatch, capsys, cwd=str(history))
    assert payload is not None, f"expected an ask for: {command!r}"
    assert "orphans them" in _reason(payload)


# requirement: git-guards / A branch reset that would orphan commits asks first
@pytest.mark.parametrize(
    "command",
    [
        # A new branch: nothing to lose.
        "git switch -C brand-new",
        "git checkout -B brand-new main",
        # Onto a start point that already holds every commit of the branch.
        "git switch -C uniq uniq",
        "git checkout -B main origin/main",
        # The current branch onto HEAD, its own tip.
        "git switch -C feat",
        # `-c` takes the rest of the cluster: this creates a branch named `C`.
        "git switch -cC uniq",
        "git switch -c uniq2",
        "git checkout -b uniq2",
        # A bare switch: git refuses on conflict and moves no ref.
        "git switch uniq",
        "git checkout uniq",
        # Out of scope, named in the module docstring.
        "git branch -f uniq main",
    ],
)
def test_a_branch_change_that_orphans_nothing_stays_silent(
    command, history, monkeypatch, capsys
):
    assert _run(command, monkeypatch, capsys, cwd=str(history)) is None, command


def test_a_reset_whose_commits_are_on_another_branch_stays_silent(
    history, monkeypatch, capsys
):
    """Reachable from another branch means nothing is orphaned."""
    _git(history, "branch", "keep", "uniq")
    assert _run("git switch -C uniq", monkeypatch, capsys, cwd=str(history)) is None


# --- merging switch ----------------------------------------------------------


@pytest.fixture
def staged(history: Path) -> Path:
    """`history` with a staged change to `tracked.txt`."""
    (history / "tracked.txt").write_text("staged\n", encoding="utf-8")
    _git(history, "add", "tracked.txt")
    return history


# requirement: git-guards / A merging branch change over staged work asks first
@pytest.mark.parametrize(
    "command",
    [
        "git switch -m main",
        "git switch --merge main",
        "git switch --m main",
        "git switch --conflict=diff3 main",
        "git switch -qm main",
        "git checkout -m main",
        "git checkout --merge main",
        "git checkout --conflict=zdiff3 main",
        "git checkout --c=merge main",
        "git -C . switch -m main",
        "git -c core.x=y checkout -m main",
        "git status && git switch -m main",
        "git switch -m \\\n  main",
    ],
)
def test_a_merging_switch_over_staged_work_asks(command, staged, monkeypatch, capsys):
    """git-checkout(1): 'When switching branches with --merge, staged changes
    may be lost.' git 2.43 refuses that case itself (measured); older git does
    not, so the guard asks."""
    payload = _run(command, monkeypatch, capsys, cwd=str(staged))
    assert payload is not None, f"expected an ask for: {command!r}"
    assert "merging branch change" in _reason(payload)


def test_a_merging_switch_over_unstaged_work_stays_silent(history, monkeypatch, capsys):
    """An unstaged change survives a conflicted merge switch, in the conflict
    markers and as index stage 3 (measured), so nothing is lost."""
    (history / "tracked.txt").write_text("unstaged\n", encoding="utf-8")
    for command in ("git switch -m main", "git checkout --merge main"):
        assert _run(command, monkeypatch, capsys, cwd=str(history)) is None, command


# requirement: git-guards / A merging branch change over staged work asks first
@pytest.mark.parametrize(
    "command",
    [
        # Not a merging switch.
        "git switch main",
        "git checkout main",
        # `-b`/`-c` take the rest of the cluster: a branch named `mainline`.
        # All letters, so `_SHORT_CLUSTER` reads it as a cluster; a digit
        # (`-bmain2`) would keep the walk from ever seeing the `m`.
        "git checkout -bmainline",
        "git switch -cmainline",
        # The path form re-creates a conflict; the discard check owns it.
        "git checkout -m -- tracked.txt",
        # `-m` belongs to rebase here, and means something else.
        "git rebase -m origin/feat",
    ],
)
def test_a_non_merging_branch_change_over_staged_work_stays_silent(
    command, staged, monkeypatch, capsys
):
    payload = _run(command, monkeypatch, capsys, cwd=str(staged))
    assert payload is None or "merging branch change" not in _reason(payload), command


def test_a_merging_switch_on_a_clean_tree_stays_silent(history, monkeypatch, capsys):
    assert _run("git switch -m main", monkeypatch, capsys, cwd=str(history)) is None


def test_an_untracked_file_is_not_staged_work(history, monkeypatch, capsys):
    """`??` has `?` in column X, so the probe leaves untracked files out."""
    (history / "new.txt").write_text("untracked\n", encoding="utf-8")
    assert _run("git switch -m main", monkeypatch, capsys, cwd=str(history)) is None


# --- shared behaviour: override, fail-open, budget --------------------------


@pytest.mark.parametrize(
    "command,fixture",
    [
        ("git rebase main", "history"),
        ("git switch -C uniq", "history"),
        ("git switch -m main", "staged"),
    ],
)
def test_allow_destructive_git_silences_the_history_checks(
    command, fixture, request, monkeypatch, capsys
):
    directory = request.getfixturevalue(fixture)
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_GIT", "1")
    monkeypatch.setattr(
        sys, "stdin",
        io.StringIO(json.dumps({"tool_input": {"command": command}, "cwd": str(directory)})),
    )
    assert hook.main() == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == ""
    assert "DISABLED" in captured.err


def test_allow_pr_merge_does_not_silence_a_rebase(history, monkeypatch, capsys):
    monkeypatch.setenv("ALLOW_PR_MERGE", "1")
    payload = _run("git rebase main", monkeypatch, capsys, cwd=str(history))
    assert payload is not None
    assert "ALLOW_DESTRUCTIVE_GIT" in _reason(payload)


def test_all_three_reasons_are_reported_together(staged, monkeypatch, capsys):
    reason = _reason(_run(
        "git rebase main && git switch -C uniq && git switch -m main",
        monkeypatch, capsys, cwd=str(staged),
    ))
    for expected in (hook.REBASE_REASON, hook.BRANCH_RESET_REASON, hook.MERGE_SWITCH_REASON):
        assert reason.count(expected) == 1, expected


def test_each_history_reason_is_reported_once(staged, monkeypatch, capsys):
    reason = _reason(_run(
        "git rebase main && git rebase --root && git switch -C uniq"
        " && git checkout -B uniq && git switch -m main && git checkout -m main",
        monkeypatch, capsys, cwd=str(staged),
    ))
    for expected in (hook.REBASE_REASON, hook.BRANCH_RESET_REASON, hook.MERGE_SWITCH_REASON):
        assert reason.count(expected) == 1, expected


def test_a_history_reason_adds_to_the_earlier_ones(history, monkeypatch, capsys):
    reason = _reason(_run(
        "git push --force origin x && git rebase main", monkeypatch, capsys, cwd=str(history)
    ))
    assert "force-push" in reason and hook.REBASE_REASON in reason


@pytest.mark.parametrize(
    "command,expected",
    [
        ("git --git-dir=/x/.git rebase main && git switch -C uniq", "BRANCH_RESET_REASON"),
        ("git rebase main && git --git-dir=/x/.git switch -C uniq", "REBASE_REASON"),
        ("git --git-dir=/x/.git pull --rebase origin main && git switch -C uniq",
         "BRANCH_RESET_REASON"),
    ],
)
def test_an_unnamed_repository_skips_only_its_own_invocation(
    command, expected, history, monkeypatch, capsys
):
    payload = _run(command, monkeypatch, capsys, cwd=str(history))
    assert payload is not None, command
    assert getattr(hook, expected) in _reason(payload)


def test_run_git_passes_a_shorter_timeout_through(monkeypatch):
    """The history probes depend on it: without it every call gets 3s and the
    hook's 12s entry is no longer true."""
    import _dispatch_lib

    seen: list = []
    monkeypatch.setattr(
        _dispatch_lib.subprocess, "run", lambda *a, **kw: seen.append(kw["timeout"])
    )
    _dispatch_lib.run_git(".", ["status"], timeout=0.5)
    _dispatch_lib.run_git(".", ["status"])
    assert seen == [0.5, _dispatch_lib.GIT_TIMEOUT_SECONDS]


def test_a_history_reason_keeps_the_merge_prompt_last(history, monkeypatch, capsys):
    """`main()` relies on the merge reason being appended last."""
    found = hook._reasons("gh pr merge 3 && git rebase main", str(history))
    assert found == [hook.REBASE_REASON, hook.MERGE_REASON]


@pytest.mark.parametrize(
    "command,fixture",
    [
        ("git rebase main", "history"),
        ("git switch -C uniq", "history"),
        ("git switch -m main", "staged"),
    ],
)
def test_a_history_probe_that_cannot_run_stays_silent(
    command, fixture, request, monkeypatch, capsys
):
    """Fail-OPEN, the opposite of the discard and stash checks: what these
    protect is still in the reflog or the object store."""
    directory = request.getfixturevalue(fixture)
    monkeypatch.setattr(hook, "_run_git", lambda cwd, args, timeout=None: None)
    assert _run(command, monkeypatch, capsys, cwd=str(directory)) is None


@pytest.mark.parametrize(
    "command,fixture",
    [
        ("git rebase main", "history"),
        ("git switch -C uniq", "history"),
        ("git switch -m main", "staged"),
    ],
)
def test_a_history_probe_that_git_refuses_stays_silent(
    command, fixture, request, monkeypatch, capsys
):
    directory = request.getfixturevalue(fixture)
    monkeypatch.setattr(
        hook, "_run_git", lambda cwd, args, timeout=None: _completed(128, "9\n")
    )
    assert _run(command, monkeypatch, capsys, cwd=str(directory)) is None


def test_a_raise_in_the_history_check_keeps_the_other_guards_and_says_so(
    history, monkeypatch, capsys
):
    def boom(*args, **kwargs):
        raise RuntimeError("history exploded")

    monkeypatch.setattr(hook, "_rebase_range", boom)
    monkeypatch.setattr(
        sys, "stdin",
        io.StringIO(json.dumps({
            "tool_input": {"command": "git push --force origin x && git rebase main"},
            "cwd": str(history),
        })),
    )
    assert hook.main() == 0
    captured = capsys.readouterr()
    reason = _reason(json.loads(captured.out))
    assert "force-push" in reason
    assert hook.REBASE_REASON not in reason
    assert "the rebase and branch-change check raised RuntimeError" in captured.err


def test_the_history_probes_share_the_hook_budget(history, monkeypatch, capsys):
    """`HOOK_WORST_CASE_SECONDS["ask-destructive-git.py"]` stays true only if
    these probes spend what the four earlier ones left: each gets at most
    `GIT_TIMEOUT_SECONDS`, and less as the deadline nears."""
    import _dispatch_lib

    assert hook._PROBE_BUDGET_SECONDS == _dispatch_lib.HOOK_WORST_CASE_SECONDS["ask-destructive-git.py"]
    # `_reasons` reads the clock once, then each probe once: two rev-parses, the
    # ancestry check, and the first rev-list, after which the 12s are spent.
    clock = iter([100.0, 100.0, 109.5, 110.0, 111.0, 112.5])
    # The hook's own `time` only; patching the shared module would reach pytest.
    monkeypatch.setattr(hook, "time", types.SimpleNamespace(monotonic=lambda: next(clock)))
    calls = _history_probe(monkeypatch)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"tool_input": {"command": "git rebase main"}, "cwd": str(history)}
    )))
    assert hook.main() == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == ""
    # The library's constant, not the hook's own name for it.
    assert [t for _, t in calls] == [_dispatch_lib.GIT_TIMEOUT_SECONDS, 2.5, 2.0, 1.0], calls
    assert "probe did not run" in captured.err


def test_no_history_probe_starts_once_the_budget_is_spent(history, monkeypatch, capsys):
    monkeypatch.setattr(hook, "_PROBE_BUDGET_SECONDS", 0.0)
    calls = _history_probe(monkeypatch)
    assert _run(
        "git rebase main && git switch -C uniq", monkeypatch, capsys, cwd=str(history)
    ) is None
    assert calls == []


def test_an_identical_history_probe_runs_once(history, monkeypatch, capsys):
    """Silent rebases, so the second is probed rather than skipped as already
    reported."""
    calls = _history_probe(monkeypatch)
    assert _run(
        "git rebase origin/feat && git -C . rebase origin/feat",
        monkeypatch, capsys, cwd=str(history),
    ) is None
    # Two rev-parses and the ancestry check, once.
    assert len(calls) == 3, calls


def test_a_rebase_probe_counts_against_the_remotes(history, monkeypatch, capsys):
    """The ask is the difference between the two counts, so both must reach git
    over the same range, the second leaving out what `--remotes` reaches."""
    calls = _history_probe(monkeypatch)
    _run("git rebase main", monkeypatch, capsys, cwd=str(history))
    head = _sha(history, "HEAD")
    main = _sha(history, "main")
    assert [args for args, _ in calls] == [
        ["rev-parse", "--verify", "--quiet", "--end-of-options", "HEAD^{commit}"],
        ["rev-parse", "--verify", "--quiet", "--end-of-options", "main^{commit}"],
        ["merge-base", "--is-ancestor", main, head],
        ["rev-list", "--count", head, "^" + main, "--"],
        ["rev-list", "--count", head, "^" + main, "--not", "--remotes", "--"],
    ]


# --- review round: no command text reaches git as an option -------------------
# `rev-list` honours `--output=<file>` and opens the file for writing. A quoted
# operand once reached it bare, so the hook truncated a file before the user was
# asked anything. Every revision now goes through `rev-parse --end-of-options`
# and only SHAs reach the other probes.


@pytest.mark.parametrize(
    "template",
    [
        'git rebase main "--output={f}"',
        "git rebase main '--output={f}'",
        'git rebase "--output={f}" main',
        'git rebase --root "--output={f}"',
        'git switch -C topic "--output={f}"',
        "git checkout -B topic '--output={f}'",
        'git switch -C "--output={f}"',
        'git switch -C uniq "--output={f}"',
        'git pull --rebase origin "--output={f}"',
        'git pull --rebase "--output={f}" main',
    ],
)
def test_a_quoted_option_never_reaches_git(template, history, tmp_path, monkeypatch, capsys):
    victim = tmp_path / "victim"
    victim.write_bytes(b"ninebytes")
    fresh = tmp_path / "fresh"
    calls = _history_probe(monkeypatch)
    for target in (victim, fresh):
        _run(template.format(f=target), monkeypatch, capsys, cwd=str(history))
    assert victim.read_bytes() == b"ninebytes"
    assert not fresh.exists()
    assert not [args for args in (a for a, _ in calls) if _reads_as_option(args, "--output")], calls


def _reads_as_option(args: list[str], option: str) -> bool:
    """True when `option` sits where git would read it as one: before any `--`
    or `--end-of-options`."""
    for arg in args:
        if arg in ("--", "--end-of-options"):
            return False
        if arg.startswith(option):
            return True
    return False


def test_every_revision_probe_ends_its_options(history, monkeypatch, capsys):
    """Only `rev-parse --end-of-options` sees command text; every other probe
    gets SHAs, `--` and options this hook wrote itself."""
    calls = _history_probe(monkeypatch)
    _run(
        "git rebase main feat && git pull --rebase origin main && git switch -C uniq main",
        monkeypatch, capsys, cwd=str(history),
    )
    assert calls
    for args, _ in calls:
        if args[0] == "rev-parse":
            assert args[:4] == ["rev-parse", "--verify", "--quiet", "--end-of-options"], args
        elif args[0] in ("rev-list", "merge-base"):
            for arg in args[1:]:
                # SHA-1 or SHA-256 object names, never command text.
                assert arg.startswith("-") or len(arg.lstrip("^")) in (40, 64), args


# --- quoted options read like their unquoted forms ---------------------------


@pytest.mark.parametrize(
    "command,fragment",
    [
        ('git rebase "-i" main', "rewrites commits already"),
        ('git rebase "--root"', "rewrites commits already"),
        ("git rebase '--onto' main main~1", "rewrites commits already"),
        ('git switch "-C" uniq', "orphans them"),
        ('git checkout "-B" uniq', "orphans them"),
    ],
)
def test_a_quoted_option_reads_like_its_unquoted_form(
    command, fragment, history, monkeypatch, capsys
):
    payload = _run(command, monkeypatch, capsys, cwd=str(history))
    assert payload is not None, command
    assert fragment in _reason(payload)


def test_a_quoted_merge_flag_reads_like_its_unquoted_form(staged, monkeypatch, capsys):
    payload = _run('git switch "-m" main', monkeypatch, capsys, cwd=str(staged))
    assert payload is not None
    assert "merging branch change" in _reason(payload)


def test_a_quoted_action_is_still_an_action(history, monkeypatch, capsys):
    calls = _history_probe(monkeypatch)
    assert _run('git rebase "--continue"', monkeypatch, capsys, cwd=str(history)) is None
    assert calls == []


# --- a rebase that replays nothing -------------------------------------------


# requirement: git-guards / A rebase of pushed commits asks first
@pytest.mark.parametrize(
    "command", ["git rebase main~1", "git rebase origin/feat", "git rebase -r main~1"]
)
def test_a_rebase_onto_an_ancestor_replays_nothing_and_stays_silent(
    command, history, monkeypatch, capsys
):
    """`main~1` is where feat forked, so git reports it up to date and moves
    nothing, though f1 is pushed."""
    assert _run(command, monkeypatch, capsys, cwd=str(history)) is None, command


# requirement: git-guards / A rebase of pushed commits asks first
@pytest.mark.parametrize(
    "command",
    [
        "git rebase -f main~1",
        "git rebase --force-rebase main~1",
        "git rebase --no-ff main~1",
        "git rebase --signoff main~1",
        "git rebase --reset-author-date main~1",
        "git rebase -i main~1",
        "git rebase --interactive main~1",
        "git rebase -x true main~1",
        "git rebase --exec true main~1",
        "git rebase --onto main main~1",
        # The `=` forms: the option is read from the part before `=`.
        "git rebase --onto=main main~1",
        "git rebase --exec=true main~1",
    ],
)
def test_an_option_that_replays_an_up_to_date_branch_asks(
    command, history, monkeypatch, capsys
):
    """Measured on git 2.43: these rewrite an up-to-date branch (or hand the
    todo list, a command or a new base the chance to)."""
    payload = _run(command, monkeypatch, capsys, cwd=str(history))
    assert payload is not None, command
    assert hook.REBASE_REASON in _reason(payload)


# --- git pull with rebase ------------------------------------------------------


# requirement: git-guards / A rebasing pull of pushed commits asks first
@pytest.mark.parametrize(
    "command",
    [
        # Explicit remote and branch: origin/main..HEAD holds f1, pushed.
        "git pull --rebase origin main",
        "git pull -r origin main",
        "git pull --rebase=merges origin main",
        "git pull --rebase=interactive origin main",
        "git pull --reb origin main",
        "git pull -vr origin main",
        "git pull --rebase origin refs/heads/main",
        "git pull --rebase origin main:main",
        'git pull "--rebase" origin main',
        "git -C . pull --rebase origin main",
        "git -c core.x=y pull --rebase origin main",
        "git fetch && git pull --rebase origin main",
        "git pull --rebase \\\n  origin main",
        "git pull --rebase --depth 5 origin main",
        "git pull --rebase --refmap x origin main",
        "git pull --rebase --negotiation-tip HEAD origin main",
        "git pull --rebase -s ort origin main",
        "git pull -rmerges origin main",
    ],
)
def test_a_rebasing_pull_of_a_pushed_commit_asks(command, history, monkeypatch, capsys):
    payload = _run(command, monkeypatch, capsys, cwd=str(history))
    assert payload is not None, f"expected an ask for: {command!r}"
    assert hook.REBASE_REASON in _reason(payload)


# requirement: git-guards / A rebasing pull of pushed commits asks first
@pytest.mark.parametrize(
    "command",
    [
        # Onto its own upstream (origin/feat): only f2, unpushed, moves.
        "git pull --rebase",
        "git pull -r",
        "git pull --rebase origin",
        "git pull --rebase origin feat",
        # Not a rebase.
        "git pull origin main",
        "git pull --no-rebase origin main",
        "git pull --rebase=false origin main",
        "git pull -r --no-rebase origin main",
        "git pull -rfalse origin main",
        # `-S` owns the rest of its cluster: a key named `r`, not `-r`.
        "git pull -Sr origin main",
        # More than one branch: git refuses to rebase onto them.
        "git pull --rebase origin main feat",
        # A URL names no remote-tracking ref this hook can read.
        "git pull --rebase https://example.invalid/r.git main",
    ],
)
def test_a_pull_that_moves_no_pushed_commit_stays_silent(
    command, history, monkeypatch, capsys
):
    assert _run(command, monkeypatch, capsys, cwd=str(history)) is None, command


def test_a_pull_rebased_by_the_pull_setting_asks(history, monkeypatch, capsys):
    _git(history, "config", "pull.rebase", "true")
    payload = _run("git pull origin main", monkeypatch, capsys, cwd=str(history))
    assert payload is not None
    assert hook.REBASE_REASON in _reason(payload)


def test_the_branch_setting_overrides_the_pull_setting(history, monkeypatch, capsys):
    _git(history, "config", "pull.rebase", "true")
    _git(history, "config", "branch.feat.rebase", "false")
    assert _run("git pull origin main", monkeypatch, capsys, cwd=str(history)) is None
    _git(history, "config", "pull.rebase", "false")
    _git(history, "config", "branch.feat.rebase", "merges")
    assert _run("git pull origin main", monkeypatch, capsys, cwd=str(history)) is not None


def test_a_rebasing_pull_ignores_up_to_date(history, monkeypatch, capsys):
    """The fetch can move the upstream past HEAD, so an up-to-date upstream
    before it proves nothing: `main~1` is an ancestor of feat now."""
    _git(history, "update-ref", "refs/remotes/origin/base", "main~1")
    payload = _run("git pull --rebase origin base", monkeypatch, capsys, cwd=str(history))
    assert payload is not None
    assert hook.REBASE_REASON in _reason(payload)


# --- branch reset: what counts as reachable elsewhere ---------------------------


def test_a_reset_of_commits_held_by_a_tag_stays_silent(history, monkeypatch, capsys):
    tip = _commit_off(history, "main", "t1")
    _git(history, "update-ref", "refs/heads/tagged", tip)
    _git(history, "tag", "v1", tip)
    assert _run("git switch -C tagged", monkeypatch, capsys, cwd=str(history)) is None
    _git(history, "tag", "-d", "v1")
    assert _run("git switch -C tagged", monkeypatch, capsys, cwd=str(history)) is not None


def test_a_reset_of_commits_held_by_a_remote_stays_silent(history, monkeypatch, capsys):
    tip = _commit_off(history, "main", "r1")
    _git(history, "update-ref", "refs/heads/remoted", tip)
    _git(history, "update-ref", "refs/remotes/origin/remoted", tip)
    assert _run("git switch -C remoted", monkeypatch, capsys, cwd=str(history)) is None
    _git(history, "update-ref", "-d", "refs/remotes/origin/remoted")
    assert _run("git switch -C remoted", monkeypatch, capsys, cwd=str(history)) is not None


@pytest.mark.parametrize(
    "command", ["git checkout --force-create uniq", "git checkout --force- uniq"]
)
def test_checkout_has_no_force_create(command, history, monkeypatch, capsys):
    """Only `switch` takes `--force-create`; git rejects it on checkout."""
    assert _run(command, monkeypatch, capsys, cwd=str(history)) is None, command


def test_a_probe_that_does_not_run_says_so(history, monkeypatch, capsys):
    monkeypatch.setattr(hook, "_run_git", lambda cwd, args, timeout=None: None)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"tool_input": {"command": "git rebase main"}, "cwd": str(history)}
    )))
    assert hook.main() == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == ""
    assert captured.err.count("probe did not run") == 1


def test_a_probe_that_runs_leaves_no_note(history, monkeypatch, capsys):
    _run("git rebase main && git switch -C uniq", monkeypatch, capsys, cwd=str(history))
    assert "did not run" not in capsys.readouterr().err


def test_a_revision_starting_with_a_dash_is_never_probed(history, monkeypatch):
    calls = _history_probe(monkeypatch)
    probes = hook._Probes(hook.time.monotonic())
    assert probes.commit(str(history), "--output=x") is None
    assert probes.commit(str(history), "") is None
    assert calls == []


def test_only_a_sha_comes_back_from_a_revision_probe(history, monkeypatch):
    """Whatever rev-parse prints, only a commit id goes on to another probe."""
    monkeypatch.setattr(
        hook, "_run_git", lambda cwd, args, timeout=None: _completed(0, "--output=x\n")
    )
    probes = hook._Probes(hook.time.monotonic())
    assert probes.commit(str(history), "main") is None


@pytest.mark.parametrize(
    "command", ['git switch --force-create=-x', 'git switch -C "-x"', "git checkout -B-x"]
)
def test_a_branch_name_starting_with_a_dash_is_never_probed(
    command, history, monkeypatch, capsys
):
    calls = _history_probe(monkeypatch)
    assert _run(command, monkeypatch, capsys, cwd=str(history)) is None
    assert calls == [], calls


def test_a_refused_revision_probe_yields_nothing(history, monkeypatch):
    """A non-zero rev-parse is a refusal, whatever it printed."""
    monkeypatch.setattr(
        hook, "_run_git", lambda cwd, args, timeout=None: _completed(1, "a" * 40 + "\n")
    )
    probes = hook._Probes(hook.time.monotonic())
    assert probes.commit(str(history), "main") is None


@pytest.mark.parametrize(
    "command",
    [
        "git rebase main no-such-branch",
        "git rebase no-such-base",
        "git switch -C uniq no-such-start",
        "git pull --rebase origin no-such-branch",
    ],
)
def test_an_unresolvable_revision_is_silence_not_an_error(
    command, history, monkeypatch, capsys
):
    """Silent because the revision does not resolve, not because a `None` reached
    a probe and the exception handler swallowed it."""
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"tool_input": {"command": command}, "cwd": str(history)}
    )))
    assert hook.main() == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == ""
    assert "raised" not in captured.err, captured.err


def test_a_pull_whose_setting_probes_cannot_run_is_silence_not_an_error(
    history, monkeypatch, capsys
):
    monkeypatch.setattr(hook, "_run_git", lambda cwd, args, timeout=None: None)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"tool_input": {"command": "git pull origin main"}, "cwd": str(history)}
    )))
    assert hook.main() == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == ""
    assert "raised" not in captured.err and "did not run" in captured.err



# --- review round 2: fork-point and the no-replay set ---------------------------


@pytest.fixture
def rewound(history: Path) -> Path:
    """Branch `fp` holds Y and T, both pushed (`origin/fp`); its upstream
    `origin/base` once held Y and was then rewound to X. A fork-point rebase
    drops Y and replays T although X is an ancestor of `fp` (measured)."""
    x = _sha(history, "main~1")
    _git(history, "update-ref", "-m", "fetch", "refs/remotes/origin/base", x)
    y = _commit_off(history, x, "Y")
    _git(history, "update-ref", "-m", "fetch", "refs/remotes/origin/base", y)
    t = _commit_off(history, y, "T")
    _git(history, "update-ref", "refs/heads/fp", t)
    _git(history, "update-ref", "refs/remotes/origin/fp", t)
    _git(history, "branch", "-q", "--set-upstream-to=origin/base", "fp")
    _git(history, "update-ref", "-m", "forced-update", "refs/remotes/origin/base", x)
    _git(history, "switch", "-q", "fp")
    return history


# requirement: git-guards / A rebase of pushed commits asks first
@pytest.mark.parametrize(
    "command",
    ["git rebase", "git rebase --fork-point origin/base", "git rebase -q", "git -C . rebase"],
)
def test_a_fork_point_rebase_that_drops_a_pushed_commit_asks(
    command, rewound, monkeypatch, capsys
):
    payload = _run(command, monkeypatch, capsys, cwd=str(rewound))
    assert payload is not None, command
    assert hook.REBASE_REASON in _reason(payload)


@pytest.mark.parametrize(
    "command",
    [
        "git rebase origin/base",
        "git rebase --no-fork-point",
        "git -c rebase.forkPoint=false rebase",
        "git -c rebase.forkpoint=no rebase",
    ],
)
def test_without_fork_point_the_same_branch_is_up_to_date(
    command, rewound, monkeypatch, capsys
):
    """An upstream operand turns fork-point off by default; so do the flag and
    the setting. Then X is an ancestor of `fp` and git moves nothing."""
    assert _run(command, monkeypatch, capsys, cwd=str(rewound)) is None, command


def test_the_fork_point_setting_in_the_repository_is_read(rewound, monkeypatch, capsys):
    _git(rewound, "config", "rebase.forkPoint", "false")
    assert _run("git rebase", monkeypatch, capsys, cwd=str(rewound)) is None
    assert _run("git -c rebase.forkPoint=true rebase", monkeypatch, capsys, cwd=str(rewound)) is not None


def test_the_fork_point_probe_names_a_ref_never_command_text(rewound, monkeypatch, capsys):
    calls = _history_probe(monkeypatch)
    _run("git rebase", monkeypatch, capsys, cwd=str(rewound))
    fork = [args for args, _ in calls if args[:2] == ["merge-base", "--fork-point"]]
    assert fork == [["merge-base", "--fork-point", "--end-of-options",
                     "refs/remotes/origin/base", _sha(rewound, "fp")]], calls


# requirement: git-guards / A rebase of pushed commits asks first
@pytest.mark.parametrize(
    "command",
    [
        "git rebase --ignore-date main~1",
        "git rebase --whitespace=fix main~1",
        "git rebase --committer-date-is-author-date main~1",
        "git rebase --apply main~1",
        "git rebase -C3 main~1",
        # An abbreviation of a no-replay option is not in the measured set.
        "git rebase --autosq main~1",
    ],
)
def test_an_unmeasured_option_turns_the_up_to_date_shortcut_off(
    command, history, monkeypatch, capsys
):
    """Measured on git 2.43: the first three replay an up-to-date branch, and
    f1 is pushed. Anything outside the measured set is treated the same."""
    payload = _run(command, monkeypatch, capsys, cwd=str(history))
    assert payload is not None, command
    assert hook.REBASE_REASON in _reason(payload)


@pytest.mark.parametrize(
    "command",
    [
        "git rebase -r main~1",
        "git rebase --rebase-merges main~1",
        "git rebase --rebase-merges=rebase-cousins main~1",
        "git rebase --keep-base main~1",
        "git rebase --autosquash main~1",
        "git rebase -q main~1",
        "git rebase -v main~1",
        "git rebase -qv main~1",
        "git rebase --update-refs main~1",
        "git rebase -s ort main~1",
        "git rebase -X theirs main~1",
        "git rebase --strategy=ort main~1",
        "git rebase --strategy-option theirs main~1",
        "git rebase --autostash --no-verify --stat main~1",
        "git rebase -m main~1",
        # `-m`'s long form, and `-X theirs` with its value attached
        "git rebase --merge main~1",
        "git rebase -Xtheirs main~1",
    ],
)
def test_a_measured_no_replay_option_keeps_the_shortcut(
    command, history, monkeypatch, capsys
):
    """Each measured on git 2.43: an up-to-date branch is left as it was."""
    assert _run(command, monkeypatch, capsys, cwd=str(history)) is None, command


# --- -c overrides ----------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git -c pull.rebase=true pull origin main",
        "git -c 'pull.rebase=true' pull origin main",
        'git -c "pull.rebase=merges" pull origin main',
        "git -c Pull.Rebase=true pull origin main",
        "git -c pull.rebase pull origin main",
        "git -c branch.feat.rebase=true pull origin main",
    ],
)
def test_a_dash_c_setting_makes_a_pull_rebase(command, history, monkeypatch, capsys):
    payload = _run(command, monkeypatch, capsys, cwd=str(history))
    assert payload is not None, command
    assert hook.REBASE_REASON in _reason(payload)


def test_a_dash_c_setting_outranks_the_repository(history, monkeypatch, capsys):
    _git(history, "config", "pull.rebase", "true")
    assert _run(
        "git -c pull.rebase=false pull origin main", monkeypatch, capsys, cwd=str(history)
    ) is None
    assert _run(
        "git -c branch.feat.rebase=false pull origin main", monkeypatch, capsys, cwd=str(history)
    ) is None


def test_config_keys_compare_as_git_does():
    assert hook._config_key("Pull.Rebase") == "pull.rebase"
    assert hook._config_key("BRANCH.Feat.REBASE") == "branch.Feat.rebase"
    assert hook._config_overrides("-c a.b=1 -c 'x.y=two words' -c z.w ") == {
        "a.b": "1", "x.y": "two words", "z.w": "true",
    }


# --- quoting ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "word,expected",
    [
        ("main", "main"),
        ("'main'", "main"),
        ('"main"', "main"),
        ('ma"in"', "main"),
        ("m'a'in", "main"),
        ("$'main'", "main"),
        ("$'ma\\x69n'", "main"),
        ("$'ma\\151n'", "main"),
        ("$'a\\tb'", "a\tb"),
        ("$'it\\'s'", "it's"),
        ('$"main"', "main"),
        ("ma\\in", "main"),
        ('"a\\"b"', 'a"b'),
        ('--force-create="uniq"', "--force-create=uniq"),
        ("'unterminated", "unterminated"),
    ],
)
def test_unquote_reads_a_word_as_the_shell_does(word, expected):
    assert hook._unquote(word) == expected


# requirement: git-guards / A rebase of pushed commits asks first
@pytest.mark.parametrize(
    "command",
    [
        "git rebase $'main'",
        'git rebase ma"in"',
        "git rebase $'ma\\x69n'",
        "git rebase ':/m2'",
        "git pull --rebase . main",
        'git pull --rebase="true" origin main',
    ],
)
def test_a_quoted_or_searched_upstream_still_asks(command, history, monkeypatch, capsys):
    """`:/m2` is the commit whose message says m2 (main's tip); `.` is this
    repository, so `pull --rebase . main` is `git rebase main`."""
    payload = _run(command, monkeypatch, capsys, cwd=str(history))
    assert payload is not None, command
    assert hook.REBASE_REASON in _reason(payload)


@pytest.mark.parametrize(
    "command",
    [
        'git pull --rebase="false" origin main',
        'git pull "--rebase=false" origin main',
        "git pull --rebase . origin/feat",
    ],
)
def test_a_quoted_false_or_local_only_pull_stays_silent(command, history, monkeypatch, capsys):
    assert _run(command, monkeypatch, capsys, cwd=str(history)) is None, command


@pytest.mark.parametrize(
    "command",
    ['git switch --force-create="uniq"', "git switch -C uniq ':/m2'", "git switch -C $'uniq'"],
)
def test_a_quoted_reset_name_or_searched_start_still_asks(
    command, history, monkeypatch, capsys
):
    payload = _run(command, monkeypatch, capsys, cwd=str(history))
    assert payload is not None, command
    assert "orphans them" in _reason(payload)


# --- shell wrappers and expansions ----------------------------------------------
# `bash -c "git push -f origin x"` and `X=push; git $X -f origin x` were measured
# allowed before `_expand` existed: the quoted body was blanked, and `$X` matched
# no subcommand. Each wrapped form must reach the decision its bare form reaches.

_FORCE = "force-push"
_HARD = "reset --hard"
_DELETE = "force-delete of a branch"


def _wrapped_ps(command: str) -> str:
    return base64.b64encode(command.encode("utf-16-le")).decode("ascii")


# requirement: git-guards / A destructive git command run through a shell wrapper asks first
@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ('bash -c "git push -f origin x"', _FORCE),
        ("sh -c 'git reset --hard'", _HARD),
        ("zsh -c 'git branch -D topic'", _DELETE),
        ('eval "git push --force"', _FORCE),
        ("eval git push --force origin x", _FORCE),
        ("bash -lc 'git push --force origin x'", _FORCE),
        ("bash -e -o pipefail -c 'git reset --hard HEAD~1'", _HARD),
        ('sudo bash -c "git reset --hard HEAD~1"', _HARD),
        ("/bin/bash -c 'git push -f origin x'", _FORCE),
        ("bash.exe -c 'git push -f origin x'", _FORCE),
        ("bash \\\n  -c 'git push -f origin x'", _FORCE),
        ("bash -c git\\ push\\ -f\\ origin\\ x", _FORCE),
        ("bash -c \"sh -c 'git push -f origin x'\"", _FORCE),
        ("bash -c \"eval 'git push -f origin x'\"", _FORCE),
        ("bash -c 'cd sub && git reset --hard'", _HARD),
        ("echo ok && bash -c 'git push -f origin x' && echo done", _FORCE),
        ('xargs -I{} sh -c "git branch -D {}"', _DELETE),
        ('echo "$(bash -c \'git push -f origin x\')"', _FORCE),
        # PowerShell runs through the same dispatcher
        ("pwsh -Command 'git push -f origin x'", _FORCE),
        ('powershell -c "git reset --hard"', _HARD),
        ("pwsh -NoProfile -ExecutionPolicy Bypass -Command \"git push -f origin x\"", _FORCE),
        ("Invoke-Expression 'git push --force origin x'", _FORCE),
        ('iex "git branch -D topic"', _DELETE),
        ('cmd /c "git push -f origin x"', _FORCE),
        ("pwsh -EncodedCommand " + _wrapped_ps("git push -f origin x"), _FORCE),
        ("powershell.exe -ec " + _wrapped_ps("git reset --hard"), _HARD),
        ('bash -c "gh pr merge 27 --squash"', "PR merge"),
        ('bash -c "git push --no-verify origin main"', "pre-push"),
    ],
)
def test_a_wrapped_destructive_command_asks_like_the_bare_one(command, expected, monkeypatch, capsys):
    payload = _run(command, monkeypatch, capsys)
    assert payload is not None, f"expected an ask for: {command!r}"
    reason = _reason(payload)
    assert expected in reason, reason
    assert "cannot resolve" not in reason, reason


# requirement: git-guards / A destructive git command run through a shell wrapper asks first
@pytest.mark.parametrize(
    "command",
    [
        'bash -c "git status"',
        "bash -c 'git log --oneline -3'",
        "sh -c 'git push origin feature/x'",
        'eval "$(ssh-agent)"',
        'eval "$(ssh-agent -s)" && git push origin feat',
        "pwsh -Command 'git status'",
        "Invoke-Expression 'git fetch origin'",
        "pwsh -EncodedCommand " + _wrapped_ps("git status"),
        "pwsh -EncodedCommand not-base64!",
        'cmd /c "git diff"',
        'sh -c "$CMD"',
        "bash script.sh",
        "cd /opt/cmd && git status",
        # a word that only ends in `sh` is not a shell
        "refresh -c 'git reset --hard'",
        # the wrapper's words end with its own command
        "bash -c 'git status' ; echo 'git push -f origin x'",
        "eval 'git status' && echo 'git reset --hard'",
        # the wrapper is inside quoted text, which the shell never runs
        'echo "bash -c \'git push -f\'"',
        "git commit -m \"fix: bash -c 'git push -f' was allowed\"",
        "git commit -m 'eval \"git reset --hard\" was allowed'",
        "git commit -m \"$(cat <<'EOF'\nfix: sh -c 'git reset --hard' was allowed\nEOF\n)\"",
    ],
)
def test_a_wrapped_harmless_command_stays_silent(command, monkeypatch, capsys):
    assert _run(command, monkeypatch, capsys) is None, command


# requirement: git-guards / A destructive git command run through a shell wrapper asks first
def test_a_wrapped_discard_probes_the_tree_like_the_bare_one(dirty, monkeypatch, capsys):
    """The working-tree probes read the wrapper's body too: a wrapped checkout
    over uncommitted work asks, and the same wrapper on a clean path does not."""
    payload = _run("bash -c 'git checkout tracked.txt'", monkeypatch, capsys, cwd=str(dirty))
    assert payload is not None
    assert "uncommitted" in _reason(payload)
    (dirty / "other.txt").write_text("x\n", encoding="utf-8")
    _git(dirty, "add", "other.txt")
    _git(dirty, "commit", "-qm", "other")
    assert _run("bash -c 'git checkout other.txt'", monkeypatch, capsys, cwd=str(dirty)) is None


# requirement: git-guards / A destructive git command run through a shell wrapper asks first
def test_wrappers_nested_past_the_depth_cap_ask_rather_than_pass(monkeypatch, capsys):
    """Three levels are read. A fourth is not, and asks instead of being allowed:
    the body there was never read."""
    inner = "git status"
    for _ in range(hook._WRAP_DEPTH):
        inner = "eval " + json.dumps(inner)
    assert _run(inner, monkeypatch, capsys) is None
    payload = _run("eval " + json.dumps(inner), monkeypatch, capsys)
    assert payload is not None
    assert hook.WRAP_DEPTH_REASON in _reason(payload)
    assert hook.UNRESOLVED_REASON not in _reason(payload)


def test_a_command_with_nothing_to_expand_is_read_as_itself():
    """The expansion is invisible to every other command: nothing appended, so
    each existing check reads exactly the text it read before."""
    for command in ("git push origin main", "echo hi", "git commit -m 'bash -c x'"):
        text, scanned, unread = hook._scan(command)
        assert text == command and unread is None
        assert scanned == hook._strip_quoted_spans(command)


def test_each_part_is_quote_stripped_on_its_own():
    """An odd quote in the command must not pair with one in an appended body."""
    command = "echo \"it's\" ; bash -c 'git push -f origin x' ; echo '"
    text, scanned, _ = hook._scan(command)
    assert len(text) == len(scanned)
    parts = text.split(hook._PART_SEP)
    assert scanned.split(hook._PART_SEP) == [hook._strip_quoted_spans(p) for p in parts]


# requirement: git-guards / A git subcommand or flag from an unresolved expansion asks first
@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("X=push; git $X -f origin x", _FORCE),
        ("X=push; git ${X} -f origin x", _FORCE),
        ('export X=push && git "$X" --force origin x', _FORCE),
        ("git 'push' -f origin x", _FORCE),
        ('git "reset" --hard', _HARD),
        ("git $'branch' -D topic", _DELETE),
        ("F=--force; git push $F origin x", _FORCE),
        ("M=--hard; git reset $M HEAD~1", _HARD),
        ("A=push; B=-f; git $A $B origin x", _FORCE),
        # every value a name is given is tried
        ("X=status; git $X; X=push; git $X -f origin x", _FORCE),
        ('bash -c \'X=push; git $X -f origin x\'', _FORCE),
        ("$X = 'push'; git $X -f origin x", _FORCE),
        # a `$(...)` value ends at its own `)`, so the next assignment is read
        ("X=$(date) Y=push; git $Y -f origin x", _FORCE),
        ("echo ); X=$(date) Y=push; git $Y -f origin x", _FORCE),
    ],
)
def test_a_resolved_expansion_asks_like_the_literal(command, expected, monkeypatch, capsys):
    payload = _run(command, monkeypatch, capsys)
    assert payload is not None, f"expected an ask for: {command!r}"
    reason = _reason(payload)
    assert expected in reason, reason
    assert hook.UNRESOLVED_REASON not in reason, reason


# requirement: git-guards / A git subcommand or flag from an unresolved expansion asks first
@pytest.mark.parametrize(
    "command",
    [
        "git $SUB -f origin x",
        "git ${SUB} origin x",
        'git "$@"',
        "git $1 --hard",
        "git $(echo push) -f origin x",
        "git `echo push` -f origin x",
        "X=$(echo push); git $X -f origin x",
        "for s in push; do git $s -f origin x; done",
        "git -C repo $SUB",
        "sudo git $SUB",
        "git push $F origin x",
        "git reset $MODE",
        "git branch $FLAGS topic",
        "bash -c 'git $SUB -f origin x'",
        "$X = Get-Verb; git $X -f origin x",
        "$X = @('push'); git $X -f origin x",
        "X='push;x'; git $X -f origin x",
        "[[ $X == push ]] && git $X -f origin x",
        "env -i git $SUB",
        "GIT_TRACE=1 git $SUB",
        "git `echo push` -f origin x",
    ],
)
def test_an_unresolved_expansion_asks(command, monkeypatch, capsys):
    payload = _run(command, monkeypatch, capsys)
    assert payload is not None, f"expected an ask for: {command!r}"
    assert hook.UNRESOLVED_REASON in _reason(payload)


# requirement: git-guards / A git subcommand or flag from an unresolved expansion asks first
@pytest.mark.parametrize(
    "command",
    [
        "X=status; git $X",
        "X=log; git $X --oneline",
        'git -C "$DIR" push origin x',
        'git -c "$KEY" status',
        'git --git-dir "$D" status',
        'git push origin "$BRANCH"',
        "git push -u origin $BRANCH",
        "git push -u origin $(git branch --show-current)",
        'git push "$REMOTE" "$BRANCH"',
        'git branch "$NAME"',
        'git reset --soft "$BASE"',
        'git log --format="%H $X"',
        'grep -rn git "$ROOT"',
        'ls repo.git "$X"',
        'echo git "$X"',
        'git commit -m "$MSG"',
        "git push '$remote' $BRANCH",
    ],
)
def test_an_expansion_that_cannot_change_the_decision_stays_silent(command, monkeypatch, capsys):
    assert _run(command, monkeypatch, capsys) is None, command


def test_rewrites_past_their_cap_ask_rather_than_pass(monkeypatch, capsys):
    """Each value is tried, up to `_EXPAND_MAX_LINES` lines; past that the
    command asks rather than being read in part."""
    values = "; ".join(f"X=v{i}" for i in range(hook._EXPAND_MAX_LINES + 1))
    payload = _run(values + "; git $X", monkeypatch, capsys)
    assert payload is not None
    assert hook.UNRESOLVED_REASON in _reason(payload)
    assert _run("X=v1; X=v2; git $X", monkeypatch, capsys) is None


def test_a_merge_through_a_wrapper_still_honours_the_merge_override(monkeypatch, capsys):
    """`ALLOW_PR_MERGE=1` in the environment drops the wrapped merge's prompt
    exactly as it drops a bare one's; a wrapped force-push still asks."""
    monkeypatch.setenv("ALLOW_PR_MERGE", "1")
    assert _run('bash -c "gh pr merge 27"', monkeypatch, capsys) is None
    capsys.readouterr()
    payload = _run("bash -c 'gh pr merge 27 && git push -f origin x'", monkeypatch, capsys)
    assert payload is not None
    assert _FORCE in _reason(payload) and "PR merge" not in _reason(payload)


# requirement: git-guards / A destructive git command run through a shell wrapper asks first
@pytest.mark.parametrize(
    ("tool", "command"),
    [
        ("Bash", 'bash -c "git push -f origin x"'),
        ("Bash", "X=push; git $X -f origin x"),
        ("PowerShell", "pwsh -Command 'git reset --hard'"),
        ("PowerShell", "$X = 'push'; git $X -f origin x"),
    ],
)
def test_the_dispatcher_asks_on_a_wrapped_command(tool, command, tmp_path):
    """End to end through the real Bash/PowerShell dispatcher, as Claude Code runs it."""
    payload = json.dumps({"tool_name": tool, "tool_input": {"command": command}, "cwd": str(tmp_path)})
    result = subprocess.run(
        [sys.executable, str(_HOOKS_DIR / "dispatch-bash-pretooluse.py")],
        input=payload, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "ask"


# --- the measured handler deadline ------------------------------------------------


def test_the_history_probes_stop_at_a_measured_handler_deadline(history, monkeypatch, capsys):
    """A stamp 14s old leaves `15 - 14 - 1` = 0s of handler: the history probes,
    which run last, start none rather than risk a kill that would drop every
    reason already found."""
    monkeypatch.setenv("CLA_HOOK_T0", f"{time.time() - 14.0:.6f}")
    calls = _history_probe(monkeypatch)
    assert _run("git rebase main", monkeypatch, capsys, cwd=str(history)) is None
    assert calls == []
    monkeypatch.setenv("CLA_HOOK_T0", f"{time.time() - 0.5:.6f}")
    _run("git rebase main", monkeypatch, capsys, cwd=str(history))
    assert calls, "a fresh stamp leaves the probes their budget"


def test_a_wrapper_body_without_git_is_not_read_further(monkeypatch, capsys):
    """Only a body that holds `git` or `gh` is read: nesting past the depth cap
    with nothing a guard reads is no reason to ask."""
    inner = "echo hi"
    for _ in range(hook._WRAP_DEPTH + 2):
        inner = "eval " + json.dumps(inner)
    assert _run(inner, monkeypatch, capsys) is None


def test_wrapped_text_past_its_cap_asks(monkeypatch, capsys):
    """Appended text is capped at the command's length plus `_EXPAND_SLACK`; a
    command whose bodies outgrow that asks rather than being read in part."""
    small = "git status; " * 10
    assert _run("bash -c \"sh -c '" + small + "'\"", monkeypatch, capsys) is None
    big = "git status; " * (hook._EXPAND_SLACK // 8)
    payload = _run("bash -c \"sh -c '" + big + "'\"", monkeypatch, capsys)
    assert payload is not None
    assert hook.UNRESOLVED_REASON in _reason(payload)


def test_expansions_past_the_round_cap_ask(monkeypatch, capsys):
    """Each round fills in one expansion per git line, and a round that still
    produced a new line leaves the next unread: `_EXPAND_ROUNDS` names in one
    line ask, one fewer is read to the end."""
    names = "ABCDEFGHIJ"[: hook._EXPAND_ROUNDS]
    assigns = "; ".join(f"{n}=v" for n in names)
    refs = " ".join(f"${n}" for n in names)
    payload = _run(f"{assigns}; git push {refs}", monkeypatch, capsys)
    assert payload is not None
    assert hook.UNRESOLVED_REASON in _reason(payload)
    fewer = "; ".join(f"{n}=v" for n in names[:-1])
    refs = " ".join(f"${n}" for n in names[:-1])
    assert _run(f"{fewer}; git push {refs}", monkeypatch, capsys) is None


def test_appended_text_never_joins_a_continued_last_line(monkeypatch, capsys):
    """A command ending in `\\` must not continue into the body appended after
    it: the push here is not forced."""
    command = "bash -c 'git log -f' ; git push origin x \\"
    assert _run(command, monkeypatch, capsys) is None


# --- quoted and partly expanded flags ---------------------------------------------
# Each of these was allowed by the first version of `_expand`: it read a flag only
# when a whole word was one `$NAME`, and a subcommand only when its first
# character was a quote, `$` or backtick.


# requirement: git-guards / A git subcommand or flag from an unresolved expansion asks first
@pytest.mark.parametrize(
    ("command", "expected"),
    [
        # a flag's literal start is `-`, and the rest cannot be known
        ("git push --force$X origin x", hook.UNRESOLVED_REASON),
        ("git push -f$X origin x", hook.UNRESOLVED_REASON),
        ("git reset --hard$X", hook.UNRESOLVED_REASON),
        ("git branch -D$X foo", hook.UNRESOLVED_REASON),
        ("git push origin x --force$X", hook.UNRESOLVED_REASON),
        ('git push "-f"$X origin x', hook.UNRESOLVED_REASON),
        ("git push ${F} origin x", hook.UNRESOLVED_REASON),
        # the value of `X` runs to its own closing `)`, past the one inside it,
        # so `Y` is assigned inside a computed value and is not known
        ("X=$( (a) Y=push ); git $Y -f origin x", hook.UNRESOLVED_REASON),
        # a subcommand with an expansion inside it
        ('git pu$X"sh" -f origin x', hook.UNRESOLVED_REASON),
        # quoted or escaped flags and subcommands read as their value
        ('git push "-f" origin x', _FORCE),
        ("git push '--force' origin x", _FORCE),
        ("git push -\\f origin x", _FORCE),
        ('bash -c "git push \\"-f\\" origin x"', _FORCE),
        ('git reset "--hard"', _HARD),
        ('git branch "-D" topic', _DELETE),
        ("git p'us'h -f origin x", _FORCE),
        ('X=""; git pu$X"sh" -f origin x', _FORCE),
        ("X=; git push --force$X origin x", _FORCE),
        # what follows a `+` or a `--name=` cannot change what they are
        ("git push origin '+main'", _FORCE),
        ("git push origin +$B", _FORCE),
        ("git push --force=$X origin x", _FORCE),
    ],
)
def test_a_quoted_or_partly_expanded_flag_asks(command, expected, monkeypatch, capsys):
    payload = _run(command, monkeypatch, capsys)
    assert payload is not None, f"expected an ask for: {command!r}"
    reason = _reason(payload)
    assert expected in reason, reason
    if expected != hook.UNRESOLVED_REASON:
        assert hook.UNRESOLVED_REASON not in reason, reason


# requirement: git-guards / A git subcommand or flag from an unresolved expansion asks first
@pytest.mark.parametrize(
    "command",
    [
        'git commit -m "$MSG"',
        'git push origin "$BRANCH"',
        'git -C "$DIR" push origin x',
        'git --git-dir="$D" status',
        "git --exec-path=$X status",
        'git "status"',
        "git push origin 'main'",
        'git reset --soft "HEAD~1"',
        'git branch -d "$B"',
        "git push --push-option=$X origin x",
        "git push --force-with-lease=$X origin x",
        "X=-with-lease; git push --force$X origin x",
    ],
)
def test_a_quoted_or_partly_expanded_harmless_word_stays_silent(command, monkeypatch, capsys):
    assert _run(command, monkeypatch, capsys) is None, command


# --- reading time ---------------------------------------------------------------
# The first version of `_expand` walked the rest of the command once per wrapper
# word and once per `X=$(`: 20 kB of `eval eval ...` ran past the 15 s handler
# timeout, which Claude Code answers by ALLOWING the call, unread. Measured in
# processing time, not wall time, so a loaded machine cannot fail these.

_SCAN_CAP = int(
    re.search(
        r"^MAX_SCANNED_COMMAND_CHARS = ([\d_]+)",
        (_HOOKS_DIR / "dispatch-bash-pretooluse.py").read_text(encoding="utf-8"),
        re.M,
    ).group(1)
)
_PUSH_F = "git push -f origin x"


def _fill(head: str, unit: str, tail: str = "") -> str:
    """`unit` repeated between `head` and `tail` up to the dispatcher's cap."""
    return head + unit * ((_SCAN_CAP - len(head) - len(tail)) // len(unit)) + tail


# requirement: git-guards / A long command is read within the guard's time
@pytest.mark.parametrize(
    ("command", "expected", "unread"),
    [
        pytest.param(_fill("", "eval ", _PUSH_F), _FORCE, True, id="eval-run-then-push"),
        pytest.param(_fill(_PUSH_F + "; echo ", "eval "), _FORCE, False, id="push-then-eval-run"),
        pytest.param(_fill(_PUSH_F + " # ", "sh "), _FORCE, False, id="push-then-sh-run"),
        pytest.param(_fill(_PUSH_F + "; ", "X=$("), _FORCE, False, id="push-then-unclosed-substitutions"),
        pytest.param(_fill("", "eval "), None, False, id="eval-run"),
    ],
)
def test_a_command_at_the_scan_cap_is_read_in_time(command, expected, unread, monkeypatch, capsys):
    """Each shape asks as its push asks, and nothing more: a reader that walks the
    text again per word runs into the work cap, which adds the unresolved reason.
    The eval run before the push asks that too, for a body longer than the cap on
    appended text."""
    assert len(command) > _SCAN_CAP - 8
    started = time.process_time()
    payload = _run(command, monkeypatch, capsys)
    elapsed = time.process_time() - started
    assert elapsed < 2.0, f"{elapsed:.2f}s of processing for {len(command)} characters"
    if expected is None:
        assert payload is None
        return
    reason = _reason(payload)
    assert expected in reason
    assert (hook.UNRESOLVED_REASON in reason) is unread, reason


# requirement: git-guards / A long command is read within the guard's time
def test_reading_past_the_work_cap_asks_rather_than_reading_in_part(monkeypatch, capsys):
    """With no work allowed, the first word a wrapper hands on stops the reading,
    and the command asks instead of passing on what was read so far."""
    command = "bash -c 'git status'"
    assert _run(command, monkeypatch, capsys) is None
    monkeypatch.setattr(hook, "_WORK_FACTOR", 0)
    hook._scan.cache_clear()
    payload = _run(command, monkeypatch, capsys)
    assert payload is not None
    assert hook.UNRESOLVED_REASON in _reason(payload)


def test_a_long_wrapped_command_is_read_inside_the_work_cap(monkeypatch, capsys):
    """A real command is read in full: a long wrapped chain of pushes stays silent,
    and one force-push in it asks for that alone."""
    body = "git push origin b; " * 400
    assert _run(f"bash -c '{body}'", monkeypatch, capsys) is None
    payload = _run(f"bash -c '{body}{_PUSH_F}'", monkeypatch, capsys)
    assert payload is not None
    reason = _reason(payload)
    assert _FORCE in reason and hook.UNRESOLVED_REASON not in reason, reason
    # A long value is walked twice, where it is assigned and in the line it fills:
    # more than the command's own length plus the slack, and inside the cap.
    assert _run("X=" + "a" * 20000 + "; git push origin $X", monkeypatch, capsys) is None


# --- backticks that close a span opened before `git` ------------------------------
# Prose quotes git commands in backticks. In `` run `git status` here `` the
# backtick after `status` closes a span that opened before `git`; reading it as a
# substitution inside the word asked on every heredoc commit message or PR body
# that quoted a git command.


# requirement: git-guards / A git subcommand or flag from an unresolved expansion asks first
@pytest.mark.parametrize(
    "command",
    [
        "git commit -F - <<'EOF'\nfix: don't trust `git status` here\nEOF",
        "gh pr create --title t --body-file - <<'EOF'\nIt's fixed; run `git log` to see.\nEOF",
        "cat > notes.md <<'EOF'\nthe framework's temp dir\nextract with `git archive`, then run\nEOF",
        "git commit -F - <<'EOF'\nsee `git branch -m`, which renamed it\nEOF",
        # outside a heredoc the span is read: the flag ends at its backtick
        "echo `git branch -m`, which renamed it",
        'echo `git "status"`, then more',
        # the span ends the git command: `-f` is an argument of `echo`
        'echo `git "push"` -f origin x',
        # apostrophes pair across the prose and hide two backticks, so the count
        # before `git` is even; the backtick right before it still opens a span
        "gh pr create --body-file - <<'EOF'\nthe ` mark: it's `y`, that's `git status`, so\nEOF",
        "echo it's `git branch -a` that lists step 2's `-d` and `-D` here",
        "git commit -F - <<'EOF'\nit's `git push origin x`, then `git reset --soft HEAD~1`\nEOF",
    ],
)
def test_a_backtick_after_a_quoted_git_command_stays_silent(command, monkeypatch, capsys):
    assert _run(command, monkeypatch, capsys) is None, command


# requirement: git-guards / A git subcommand or flag from an unresolved expansion asks first
@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git `echo push` -f origin x", hook.UNRESOLVED_REASON),
        ("git push -f`echo` origin x", _FORCE),
        # the flag before a closing backtick is still read
        ("echo `git branch topic -D` here", _DELETE),
        # an even number of backticks before `git`: one in a word opens a
        # substitution, whose output cannot be known
        ("git push -`echo f` origin x", hook.UNRESOLVED_REASON),
        ("git push --`echo force` origin x", hook.UNRESOLVED_REASON),
        ("git reset --`echo hard`", hook.UNRESOLVED_REASON),
        ("git branch -`echo D` foo", hook.UNRESOLVED_REASON),
        ("git pu`echo sh` -f origin x", hook.UNRESOLVED_REASON),
        ("git re`echo set` --hard", hook.UNRESOLVED_REASON),
        ('git push "-`echo f`" origin x', hook.UNRESOLVED_REASON),
        ("bash -c 'git push -`echo f` origin x'", hook.UNRESOLVED_REASON),
        ("X=f; git push -`echo $X` origin x", hook.UNRESOLVED_REASON),
        # inside a span, an escaped backtick still opens one a level down
        ("echo `git push -\\`echo f\\` origin x`", hook.UNRESOLVED_REASON),
        # a span closed before the next command leaves that command whole
        ('echo "`git status`" && git push -f origin x', _FORCE),
        ("echo `git status` && git push -f origin x", _FORCE),
    ],
)
def test_a_backtick_that_opens_a_substitution_still_counts(command, expected, monkeypatch, capsys):
    payload = _run(command, monkeypatch, capsys)
    assert payload is not None, command
    assert expected in _reason(payload)


def test_many_quoted_git_commands_add_nothing_to_read():
    """A git word whose only backtick closes it is not an expansion, so it adds
    no rewritten line; were each mention rewritten, the line cap would ask."""
    command = "echo " + "`git status` " * (hook._EXPAND_MAX_LINES + 16)
    text, _, unread = hook._scan(command)
    assert unread is None and text == command


def _shipped_prose() -> list[Path]:
    """Every shipped `.md` in the plugin and every `docs/*.md`, read from the
    tree at test time: the text a chain quotes in commit messages and PR bodies."""
    root = _HOOKS_DIR.parents[3]
    return sorted([*(_HOOKS_DIR.parent).rglob("*.md"), *(root / "docs").glob("*.md")])


_PROSE = _shipped_prose()


def test_the_prose_corpus_is_not_empty():
    assert len(_PROSE) > 20, _PROSE


# requirement: git-guards / A git subcommand or flag from an unresolved expansion asks first
@pytest.mark.parametrize(
    "path", _PROSE, ids=[str(p.relative_to(_HOOKS_DIR.parents[3])) for p in _PROSE]
)
def test_shipped_prose_in_a_heredoc_is_read_in_full(path):
    """A commit message or PR body built from this repo's own prose is never
    unreadable. It may still ask for a destructive command it quotes (the same
    asks as before the expansion reading existed); only the reason `_expand`
    adds, for text it could not read, is checked here."""
    command = "git commit -F - <<'EOF'\n" + path.read_text(encoding="utf-8") + "\nEOF"
    assert hook._scan(command)[2] is None


# --- the history probes' refusals, driven directly ----------------------------------
# A probe that git refuses, or that cannot run, must not read as an answer. These
# drive `_Probes` and `_replays_nothing` with a fake git, because a real repository
# cannot be made to refuse one probe and answer the next.


def _fake_git(monkeypatch, answers: dict):
    """`hook._run_git` answering from `answers`, keyed by the probe's first two
    arguments: a `(returncode, stdout)` pair, or None for a probe that cannot run.
    Returns the list of argv it was asked."""
    asked: list[list[str]] = []

    def run(cwd, args, timeout=None):
        asked.append(list(args))
        answer = answers.get(tuple(args[:2]))
        if answer is None:
            return None
        return subprocess.CompletedProcess(args, answer[0], stdout=answer[1], stderr="")

    monkeypatch.setattr(hook, "_run_git", run)
    return asked


def test_a_ref_probe_reads_only_a_ref_that_git_confirmed(monkeypatch, tmp_path):
    probes = hook._Probes(time.monotonic())
    asked = _fake_git(monkeypatch, {("rev-parse", "--verify"): (0, "refs/heads/x\n")})
    assert probes.ref(str(tmp_path), "--output=x") is None
    assert asked == [], "a revision that starts with `-` is never handed to git"
    assert probes.ref(str(tmp_path), "x") == "refs/heads/x"
    for answer in ((1, "refs/heads/y\n"), (0, "HEAD\n"), (0, "deadbeef\n")):
        _fake_git(monkeypatch, {("rev-parse", "--verify"): answer})
        assert hook._Probes(time.monotonic()).ref(str(tmp_path), "y") is None, answer


class _Answers:
    """A `_Probes` stand-in for `_replays_nothing`: `git` answers by the
    probe's first two arguments, `ref` gives one fixed name."""

    def __init__(self, answers: dict):
        self.answers = answers

    def git(self, directory, args):
        answer = self.answers.get(tuple(args[:2]))
        if answer is None:
            return None
        return subprocess.CompletedProcess(args, answer[0], stdout=answer[1], stderr="")

    def ref(self, directory, rev):
        return "refs/remotes/origin/main"


def test_a_probe_that_cannot_run_counts_as_up_to_date():
    """`_replays_nothing` fails open, as its docstring says: no ancestry answer,
    or no fork-point answer, reads as up to date, never as a replay."""
    base, tip = "a" * 40, "b" * 40
    assert hook._replays_nothing("d", "origin/main", base, tip, False, _Answers({}))
    ancestor = {("merge-base", "--is-ancestor"): (0, "")}
    assert hook._replays_nothing("d", "origin/main", base, tip, True, _Answers(ancestor))
    assert not hook._replays_nothing(
        "d", "origin/main", base, tip, False, _Answers({("merge-base", "--is-ancestor"): (1, "")})
    )


def test_a_refused_fork_point_probe_finds_no_fork_point():
    """A fork-point probe git refuses yields nothing, so the branch is up to
    date; one that names a different commit means git would replay."""
    base, tip = "a" * 40, "b" * 40
    answers = {("merge-base", "--is-ancestor"): (0, "")}
    refused = {**answers, ("merge-base", "--fork-point"): (1, "c" * 40 + "\n")}
    assert hook._replays_nothing("d", "origin/main", base, tip, True, _Answers(refused))
    other = {**answers, ("merge-base", "--fork-point"): (0, "c" * 40 + "\n")}
    assert not hook._replays_nothing("d", "origin/main", base, tip, True, _Answers(other))


def test_an_empty_setting_does_not_rebase():
    assert hook._is_true("true") and hook._is_true("merges")
    assert not hook._is_true("") and not hook._is_true("  ")
