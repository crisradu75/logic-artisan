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
import subprocess
import sys
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


def test_the_merge_prompt_names_the_narrow_variable_a_reader_can_actually_use(
    monkeypatch, capsys
):
    """A merge-only prompt must name `ALLOW_PR_MERGE=1` — the variable honoured
    from command text (`_ALLOW_MERGE_PREFIX`) — not `ALLOW_DESTRUCTIVE_GIT`,
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
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
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
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main", ".")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "t")
    (root / "tracked.txt").write_text("original\n", encoding="utf-8")
    _git(root, "add", "tracked.txt")
    _git(root, "commit", "-qm", "seed")
    return root


@pytest.fixture
def dirty(repo: Path) -> Path:
    """The same repository with uncommitted work in `tracked.txt` -- the exact
    state issue #184's incident was in when `git checkout <file>` erased it."""
    (repo / "tracked.txt").write_text("original\nfifty more lines\n", encoding="utf-8")
    return repo


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
    """Structural non-vacuity guarantee for a guard, per test-quality.md. The
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
    """`HOOK_WORST_CASE_SECONDS["ask-destructive-git.py"] = 9.0` is DERIVED from
    the claim that a hook run makes at most three probes, and feeds the
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
# deleting the branch entirely left the whole suite green. test-quality.md's
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
    which the module docstring already claimed was handled."""
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
    """Dirty enough that EVERY rule above has something real to find."""
    _git(repo, "branch", "feat")
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
