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
import json
import os
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parent.parent / "block-direct-push-to-main.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("block_direct_push_to_main", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load_module()


@pytest.fixture(autouse=True)
def _clear_branch_cache():
    """`_current_branch` memoises per cwd so a command carrying several pushes
    costs one subprocess rather than one per push. The module lives for a single
    hook process in production, so the cache never outlives its facts there — but
    pytest keeps it across every test in this file, where one test's resolved
    branch would otherwise answer another test's mocked failure."""
    hook._BRANCH_CACHE.clear()
    yield
    hook._BRANCH_CACHE.clear()


def _never_called():
    """A `_current_branch` stand-in that fails the test if it is reached — used
    to pin the cases that must be decided without shelling out to git."""

    def _fail(cwd=None):
        raise AssertionError("_current_branch was called; this shape must not need git")

    return _fail


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
    # SUBSEQUENT command are never attributed to this push. `echo` is not a
    # push, so scanning every match must not turn this into a false positive.
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: "feature/x")
    assert hook._is_direct_push_to_main("git push origin feature/x && echo main") is False


def test_push_with_remote_but_no_refspec_checks_the_current_branch(monkeypatch):
    # `git push origin` on main pushes main. The old bare-push pattern required
    # end-of-string after the flags, so the remote token defeated it entirely.
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: "main")
    assert hook._is_direct_push_to_main("git push origin") is True
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: "feature/x")
    assert hook._is_direct_push_to_main("git push origin") is False


# --------------------------------------------------------------------------- #
# Every push in a compound command is inspected, not just the first
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "command",
    [
        "git push origin feature/x && git push origin main",
        "git push origin feature/x; git push origin main",
        "git push -u origin feature/x && git push origin master",
        "git push origin dev | tee log && git push origin main",
        "git push origin feature/x\ngit push origin main",  # newline separator
        # The force flag on the SECOND (blocked) push — the "drifted session
        # force-pushes main after a normal push" shape.
        "git push origin feature/x && git push --force origin main",
    ],
)
def test_blocks_a_protected_push_that_follows_an_allowed_one(command, monkeypatch):
    # Each of these reached the remote unblocked: the pre-rename
    # `_push_arguments` took only the FIRST `_GIT_PUSH` match, then truncated
    # at the first shell separator, so every later push in the same command was
    # invisible. "Push the feature branch, then push main" is the likeliest
    # real shape of the offense. A regression: the pre-`_dispatch_lib`
    # whole-string regex caught it.
    monkeypatch.setattr(hook, "_current_branch", _never_called())
    assert hook._is_direct_push_to_main(command) is True


def test_every_push_window_keeps_its_own_arguments(monkeypatch):
    # The windows must not bleed into each other: a first push whose refspec is
    # protected blocks, and a trailing allowed push does not un-block it.
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: "feature/x")
    assert hook._is_direct_push_to_main("git push origin main && git push origin feature/x") is True
    assert (
        hook._is_direct_push_to_main("git push origin feature/x && git push origin dev") is False
    )


def test_a_bare_push_after_an_allowed_push_still_checks_the_current_branch(monkeypatch):
    # The second window has no refspec, so it falls through to the branch check
    # — which only works if windows are evaluated individually rather than the
    # first match deciding for the whole command.
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: "main")
    assert hook._is_direct_push_to_main("git push origin feature/x && git push") is True


# --------------------------------------------------------------------------- #
# HEAD / @ refspecs resolve through the current branch
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("command", ["git push origin HEAD", "git push origin @"])
def test_head_refspec_is_blocked_when_head_is_main(command, monkeypatch):
    # `HEAD` is a POSITIONAL refspec, so the bare-push current-branch check
    # never ran for it, and as a literal ref name it matched nothing protected.
    # `git push origin HEAD` is what a script emits when it does not want to
    # hardcode a branch name — and from main it pushes main.
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: "main")
    assert hook._is_direct_push_to_main(command) is True


@pytest.mark.parametrize("command", ["git push origin HEAD", "git push origin @"])
def test_head_refspec_is_allowed_from_a_feature_branch(command, monkeypatch):
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: "feature/x")
    assert hook._is_direct_push_to_main(command) is False


def test_head_on_the_source_side_of_a_pair_resolves_too(monkeypatch):
    # `HEAD:<branch>` from main pushes main's content out — the same operation
    # `main:<branch>` is already blocked for.
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: "main")
    assert hook._is_direct_push_to_main("git push origin HEAD:feature/x") is True
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: "feature/x")
    assert hook._is_direct_push_to_main("git push origin HEAD:feature/x") is False


def test_a_literal_refspec_is_decided_without_shelling_out(monkeypatch):
    # The guard must catch its MOST COMMON offense without git being usable at
    # all — HEAD resolution is reached only after the literal comparison fails.
    # A characterization test, not a fix-pin: the old code had no HEAD handling
    # to short-circuit past. It exists because making the hot path
    # subprocess-dependent would be a silent availability regression.
    monkeypatch.setattr(hook, "_current_branch", _never_called())
    assert hook._is_direct_push_to_main("git push origin main") is True
    assert hook._is_direct_push_to_main("git push origin feature/x") is False


def test_a_literal_side_short_circuits_before_the_head_side_is_resolved(monkeypatch):
    # THIS is the order-sensitive case: one side is literally protected while
    # the other is a HEAD alias. The literal comparison runs across BOTH sides
    # first, so the match is found without ever resolving HEAD.
    monkeypatch.setattr(hook, "_current_branch", _never_called())
    assert hook._is_direct_push_to_main("git push origin main:HEAD") is True
    assert hook._is_direct_push_to_main("git push origin HEAD:master") is True


# --------------------------------------------------------------------------- #
# Branch resolution happens in the COMMAND's directory, not the hook process's
# --------------------------------------------------------------------------- #


class _FakeCompleted:
    def __init__(self, stdout):
        self.returncode = 0
        self.stdout = stdout


def test_current_branch_resolves_in_the_given_directory(monkeypatch):
    # A session in a linked worktree while the primary clone sits on main is
    # the case that fails OPEN when the branch is resolved in the hook
    # process's own cwd; the inverse over-blocks a legitimate push.
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeCompleted("feature/x\n")

    monkeypatch.setattr(hook.subprocess, "run", fake_run)
    assert hook._current_branch("/some/worktree") == "feature/x"
    assert captured["cmd"][:3] == ["git", "-C", "/some/worktree"]


def test_no_cwd_means_no_dash_c_argument(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeCompleted("main\n")

    monkeypatch.setattr(hook.subprocess, "run", fake_run)
    assert hook._current_branch() == "main"
    assert "-C" not in captured["cmd"]


def test_payload_cwd_is_threaded_into_the_branch_check(monkeypatch):
    seen = []
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: seen.append(cwd) or "main")
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO('{"cwd": "/session/dir", "tool_input": {"command": "git push"}}'),
    )
    assert hook.main() == 2
    assert seen == ["/session/dir"]


@pytest.mark.parametrize(
    "command,expected",
    [
        ("git -C /repo/wt push", "/repo/wt"),
        ("git --work-tree /repo/wt push", "/repo/wt"),
        ("git --work-tree=/repo/wt push", "/repo/wt"),
        ("git --git-dir=/other/.git push", "/other/.git"),
        ("git --git-dir /other/.git push", "/other/.git"),
        ('git -C "/repo/with a space" push', "/repo/with a space"),
        ("git push", None),
    ],
)
def test_a_dash_c_value_overrides_the_payload_cwd(command, expected, monkeypatch):
    # `GIT_GLOBAL_OPTS` consumed these prefixes without ever USING the target
    # path, so the branch was resolved in the wrong directory even when the
    # command said exactly which one it meant. `--git-dir` is in the set for
    # the same reason: consumed by the matcher, so leaving it out here resolved
    # HEAD in the session's repo while the command named another.
    seen = []
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: seen.append(cwd) or "main")
    assert hook._is_direct_push_to_main(command, "/session/dir") is True
    assert seen == [expected or "/session/dir"]


def test_a_relative_dash_c_is_composed_against_the_session_directory(monkeypatch):
    # Passed through raw, a relative `-C` resolves against whatever cwd the
    # HOOK PROCESS has — reintroducing, for relative paths, the exact
    # wrong-directory bug this hook was fixed for. Verified regression: from a
    # session in `<repo>/sub`, `git -C .. push` (naming a repo root on main)
    # resolved somewhere else entirely, failed, and was ALLOWED.
    seen = []
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: seen.append(cwd) or "main")
    assert hook._is_direct_push_to_main("git -C .. push", "/session/dir") is True
    assert seen == [os.path.join("/session/dir", "..")]


def test_a_per_push_dash_c_applies_to_its_own_window_only(monkeypatch):
    # The intersection of two of this change's fixes: every push is inspected
    # AND each resolves in its own directory. The second push's `-C` must not
    # bleed onto the first, nor the first's absence onto the second.
    seen = []
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: seen.append(cwd) or "main")
    assert (
        hook._is_direct_push_to_main("git push origin feature/x && git -C /repo/wt push", "/session/dir")
        is True
    )
    assert seen == ["/repo/wt"]


def test_a_failed_command_derived_path_falls_back_to_the_session_directory(monkeypatch):
    # A scraped `-C` value is likelier to be wrong than the payload's own cwd,
    # and "unknown" means the guard stops guarding — so an unresolvable
    # command-derived path retries against the session directory rather than
    # collapsing straight to an allow.
    seen = []

    def fake_branch(cwd=None):
        seen.append(cwd)
        return None if cwd == "/bogus" else "main"

    monkeypatch.setattr(hook, "_current_branch", fake_branch)
    assert hook._is_direct_push_to_main("git -C /bogus push", "/session/dir") is True
    assert seen == ["/bogus", "/session/dir"]


def test_an_unresolvable_directory_is_reported_not_silently_allowed(tmp_path, capsys):
    # git EXITS 128 for a bad directory rather than raising, so this — not the
    # OSError branch — is the common degradation now that the directory is
    # caller-supplied. Returning None silently made it indistinguishable from
    # "you are on a feature branch", i.e. the guard reporting success while
    # not guarding. Uses the REAL `_current_branch`, which is the point.
    missing = tmp_path / "no-such-dir"
    assert hook._current_branch(str(missing)) is None
    err = capsys.readouterr().err
    assert "warn" in err.lower()
    assert str(missing) in err


# --------------------------------------------------------------------------- #
# An option value must not pose as a refspec
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "command",
    [
        "git push -o ci.skip origin",
        "git push --push-option ci.skip origin",
        "git push --receive-pack /usr/bin/git-receive-pack origin",
        "git push --repo origin",
    ],
)
def test_a_separate_token_option_value_does_not_suppress_the_branch_check(command, monkeypatch):
    # Flags were dropped by leading dash, but the SEPARATE-TOKEN value of an
    # option that takes one survived as a positional: it read as the remote,
    # pushed the real remote into the refspec slot, and so skipped the
    # refspec-less current-branch check entirely. `git push -o ci.skip origin`
    # is an ordinary push-option invocation, and from main it pushes main.
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: "main")
    assert hook._is_direct_push_to_main(command) is True


def test_an_attached_option_value_is_still_just_a_flag(monkeypatch):
    # The `--opt=value` form is one token and was never the problem; make sure
    # consuming the separate-token form didn't start eating a real refspec.
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: "main")
    assert hook._is_direct_push_to_main("git push --push-option=ci.skip origin feature/x") is False
    assert hook._is_direct_push_to_main("git push -o ci.skip origin feature/x") is False


def test_current_branch_passes_a_timeout_and_warns_when_git_is_unusable(monkeypatch, capsys):
    # Without a timeout a hung `git rev-parse` burns the dispatcher's whole
    # budget and takes every other guard down with it. An unresolvable branch
    # now routes to ASK rather than a silent allow, but the degradation must
    # still be VISIBLE on stderr — it is exactly when the hook cannot vouch
    # for the push.
    captured = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        raise OSError("git not found")

    monkeypatch.setattr(hook.subprocess, "run", fake_run)
    assert hook._current_branch() is None
    assert captured.get("timeout"), "_current_branch must pass a subprocess timeout"
    assert "warn" in capsys.readouterr().err.lower()


def test_bare_push_checks_current_branch(monkeypatch):
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: "main")
    assert hook._is_direct_push_to_main("git push") is True


def test_bare_push_on_feature_branch_is_allowed(monkeypatch):
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: "feature/x")
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


# --------------------------------------------------------------------------- #
# The ASK arm -- cases that were SILENT ALLOWS before the 3-state redesign
#
# Each case below was previously waved through with no signal at all (or, for
# the heredoc, hard-blocked as a false positive). A guard that cannot resolve a
# push now escalates to the user's permission prompt instead of guessing.
# --------------------------------------------------------------------------- #


def _verdict(command, cwd=None):
    return hook._push_verdict(command, cwd)[0]


def test_a_possible_alias_near_a_protected_name_asks(monkeypatch):
    # `git pushmain` could be a user alias expanding to a real push. Resolving
    # it via `git config --get alias.<name>` would need a second subprocess,
    # which does not fit the handler budget (see the module docstring), so the
    # uncertainty is escalated instead of ignored.
    monkeypatch.setattr(hook, "_current_branch", _never_called())
    assert _verdict("git pushmain") == "ASK"


def test_an_unknown_subcommand_without_a_protected_name_is_allowed(monkeypatch):
    # The ASK arm must not fire on every unrecognized subcommand — only when a
    # protected branch name is also present. Otherwise ordinary use of a git
    # subcommand missing from the table becomes a prompt, and a prompt that
    # fires routinely stops being read.
    monkeypatch.setattr(hook, "_current_branch", _never_called())
    assert _verdict("git whatever-custom-command --flag") == "ALLOW"


@pytest.mark.parametrize(
    "command",
    [
        "bash <<'EOF'\ngit push origin main\nEOF",       # EXECUTES the body
        "cat <<'EOF' > deploy.sh\ngit push origin main\nEOF",  # merely writes it
    ],
)
def test_a_heredoc_body_containing_a_protected_push_asks(command, monkeypatch):
    # Previously a hard BLOCK for both, which is a false positive for the
    # write-to-file form. Telling the two apart means parsing what consumes the
    # heredoc, so both escalate rather than one being wrong in each direction.
    monkeypatch.setattr(hook, "_current_branch", _never_called())
    assert _verdict(command) == "ASK"


def test_an_unresolvable_branch_on_a_bare_push_asks(monkeypatch):
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: None)
    assert _verdict("git push") == "ASK"


def test_an_unresolvable_branch_on_a_head_refspec_asks(monkeypatch):
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: None)
    assert _verdict("git push origin HEAD") == "ASK"


def test_an_unlexable_command_mentioning_a_protected_push_asks(monkeypatch):
    # An unbalanced quote defeats tokenization entirely. Absence of a parse is
    # not evidence of absence of a push.
    monkeypatch.setattr(hook, "_current_branch", _never_called())
    assert _verdict("git push origin 'main") == "ASK"


def test_an_unlexable_command_without_a_push_is_allowed(monkeypatch):
    monkeypatch.setattr(hook, "_current_branch", _never_called())
    assert _verdict("echo 'unterminated") == "ALLOW"


# --------------------------------------------------------------------------- #
# Defects found by running the redesign against the corpus -- each was a NEW
# bypass introduced by the first draft of the shlex parser, not present in the
# regex version it replaced. Pinned so they cannot regress.
# --------------------------------------------------------------------------- #


def test_a_windows_backslash_path_is_not_mangled_by_the_lexer():
    # In POSIX mode shlex treats a backslash as an escape, so a Windows drive
    # path tokenized with its separators stripped — the branch would then
    # resolve in the WRONG directory, the exact bug class `_branch_for` exists
    # to prevent. Windows is this harness's primary platform.
    segments, ok = hook._segments(r"git -C C:\repo\sub push origin main")  # path-fixture-ok
    assert ok
    assert segments == [["git", "-C", r"C:\repo\sub", "push", "origin", "main"]]  # path-fixture-ok


def test_a_windows_path_is_threaded_through_as_the_directory_override(monkeypatch):
    seen = []
    monkeypatch.setattr(
        hook, "_current_branch", lambda cwd=None: seen.append(cwd) or "main"
    )
    assert hook._is_direct_push_to_main(r"git -C C:\repo\sub push") is True  # path-fixture-ok
    assert seen == [r"C:\repo\sub"]  # path-fixture-ok


def test_an_env_var_prefix_does_not_hide_the_push(monkeypatch):
    # Requiring tokens[0] == "git" let `GIT_DIR=/x git push origin main` past
    # entirely. The regex version matched `git ... push` anywhere, so this
    # would have been a regression rather than a pre-existing gap.
    monkeypatch.setattr(hook, "_current_branch", _never_called())
    assert hook._is_direct_push_to_main("GIT_DIR=/x git push origin main") is True


def test_a_global_option_outside_the_closed_set_no_longer_bypasses(monkeypatch):
    # The regex version's `GIT_GLOBAL_OPTS` was a closed set; a shape outside it
    # silently mis-parsed and allowed the push. The table-driven walk consumes
    # the `--opt=value` form generically.
    monkeypatch.setattr(hook, "_current_branch", _never_called())
    assert hook._is_direct_push_to_main("git --exec-path=/x push origin main") is True


def test_repeated_dash_c_uses_the_last_value(monkeypatch):
    # git applies repeated `-C` cumulatively; the regex version was
    # first-match-wins and resolved against the wrong one.
    seen = []
    monkeypatch.setattr(
        hook, "_current_branch", lambda cwd=None: seen.append(cwd) or "main"
    )
    assert hook._is_direct_push_to_main("git -C /a -C /b push") is True
    assert seen == ["/b"]


def test_interpolated_refspecs_stay_allowed(monkeypatch):
    # A DOCUMENTED limitation, pinned so a future change to it is deliberate:
    # the value is not knowable without running the shell, and asking on every
    # `$VAR` push would make the prompt routine.
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: "main")
    assert _verdict("git push $REMOTE $BRANCH") == "ALLOW"


# --------------------------------------------------------------------------- #
# main() -- the ask travels as stdout JSON, per the dispatcher's contract
# --------------------------------------------------------------------------- #


def test_main_emits_an_ask_decision_as_stdout_json(monkeypatch, capsys):
    # Exit 0 + stdout JSON is the only shape the dispatcher re-emits as a
    # permission decision (`dispatch-bash-pretooluse.py::_extract_ask`). A
    # non-zero exit would discard stdout and silently downgrade it to an allow.
    monkeypatch.setattr(
        "sys.stdin", io.StringIO('{"tool_input": {"command": "git pushmain"}}')
    )
    monkeypatch.setattr(hook.os, "environ", {})
    assert hook.main() == 0
    payload = json.loads(capsys.readouterr().out)
    nested = payload["hookSpecificOutput"]
    assert nested["permissionDecision"] == "ask"
    assert nested["hookEventName"] == "PreToolUse"
    assert "alias" in nested["permissionDecisionReason"].lower()


def test_main_emits_nothing_on_stdout_when_allowing(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.stdin", io.StringIO('{"tool_input": {"command": "git status"}}')
    )
    monkeypatch.setattr(hook.os, "environ", {})
    assert hook.main() == 0
    assert capsys.readouterr().out.strip() == ""


def test_the_escape_hatch_suppresses_an_ask_too(monkeypatch, capsys):
    # Someone who set the override wants no friction — not a downgraded prompt.
    monkeypatch.setattr(
        "sys.stdin", io.StringIO('{"tool_input": {"command": "git pushmain"}}')
    )
    monkeypatch.setattr(hook.os, "environ", {"ALLOW_PUSH_TO_MAIN": "1"})
    assert hook.main() == 0
    assert capsys.readouterr().out.strip() == ""
