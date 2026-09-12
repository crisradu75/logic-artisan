"""Tests for the block-unsafe-recursive-delete PreToolUse hook.

Unit-tests the pure detection/path logic, and end-to-end-tests `main()` via
subprocess for the three trigger conditions (a link AS the target, a worktree
path, and a directory containing a symlink/junction) plus the allow and
escape-hatch cases.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "hooks" / "block-unsafe-recursive-delete.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("block_unsafe_recursive_delete", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load_module()


def _run(payload: dict, cwd: Path, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "ALLOW_UNSAFE_RM": ""}
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(_HOOK)],
        input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(cwd), env=env,
    )


# --------------------------------------------------------------------------- #
# Pure detection logic
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("command", [
    "rm -rf some/dir",
    "rm -fr some/dir",
    "rm -Rf some/dir",
    "rm -r -f some/dir",
    "rm --recursive --force some/dir",
    "rm -r --force some/dir",
    "cmd1 && rm -rf some/dir && cmd2",
    "Remove-Item -Recurse -Force some/dir",
    "Remove-Item some/dir -Recurse -Force",
    "ri -Recurse -Force some/dir",
])
def test_detects_recursive_force_delete(command):
    assert hook._extract_target_paths(command) == ["some/dir"] or "some/dir" in hook._extract_target_paths(command)


@pytest.mark.parametrize("command", [
    "rm some/dir",              # no flags at all
    "rm -r some/dir",           # recursive only, no force
    "rm -f some/file",          # force only, no recursive
    "Remove-Item -Recurse some/dir",   # recurse only
    "Remove-Item -Force some/file",    # force only
    "ls -rf",                   # not an rm/Remove-Item invocation
    "git commit -m 'rm -rf in a message'",
])
def test_does_not_detect_non_matching_commands(command):
    assert hook._extract_target_paths(command) == []


def test_detects_windows_backslash_path():
    # The literal backslash separator must survive -- posix-mode shlex would
    # otherwise treat '\' as an escape char and eat the whole path apart.
    paths = hook._extract_target_paths(r"rm -rf C:\Code\some-repo\.claude\worktrees\x")  # path-fixture-ok
    assert r"C:\Code\some-repo\.claude\worktrees\x" in paths  # path-fixture-ok


def test_detects_posix_escaped_space_path():
    # The macOS/Linux convention of backslash-escaping a space in a path must
    # still resolve to one token, not two.
    paths = hook._extract_target_paths(r"rm -rf /Users/me/My\ Docs")
    assert "/Users/me/My Docs" in paths


def test_worktree_path_detected_regardless_of_separator():
    assert hook._is_worktree_path(Path("C:/Code/some-repo/.claude/worktrees/some-change"))  # path-fixture-ok
    assert hook._is_worktree_path(Path(r"C:\Code\some-repo\.claude\worktrees\some-change"))  # path-fixture-ok


def test_non_worktree_path_not_flagged(tmp_path):
    assert not hook._is_worktree_path(tmp_path / "openspec" / "changes" / "x")


# --------------------------------------------------------------------------- #
# End-to-end via subprocess
# --------------------------------------------------------------------------- #

def test_blocks_worktree_path_delete(tmp_path):
    target = tmp_path / ".claude" / "worktrees" / "some-change"
    target.mkdir(parents=True)
    r = _run({"tool_input": {"command": f"rm -rf {target}"}}, cwd=tmp_path)
    assert r.returncode == 2
    assert "block-unsafe-recursive-delete.py" in r.stderr
    assert "worktrees" in r.stderr


def make_dir_alias(link: Path, real: Path) -> None:
    """Create `link` -> `real` as a real symlink where permitted, falling back
    to an NTFS directory junction (`mklink /J`, no elevated privileges needed
    on Windows -- unlike a symlink) so this test gets real coverage on a
    standard, non-admin Windows account instead of skipping."""
    try:
        link.symlink_to(real, target_is_directory=True)
        return
    except (OSError, NotImplementedError, AttributeError):
        pass
    if os.name != "nt":
        pytest.skip("symlink creation not permitted, and junctions are Windows-only")
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(real)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        pytest.skip(f"neither symlink nor junction creation permitted here: {result.stderr}")
    if not link.exists():
        # `mklink /J` reports success against a MISSING target: rc 0, "Junction
        # created for ...", and the link resolves nowhere. Without this the
        # helper returns normally having created nothing usable, and the caller
        # asserts against an alias that does not resolve -- a test that passes
        # for the wrong reason, which is the failure shape this helper was
        # written to remove.
        pytest.skip("directory alias created but does not resolve")


def test_blocks_directory_containing_a_symlink(tmp_path):
    target = tmp_path / "some-dir"
    target.mkdir()
    real = tmp_path / "real-content"
    real.mkdir()
    (real / "important.txt").write_text("do not delete me", encoding="utf-8")
    make_dir_alias(target / "linked", real)

    r = _run({"tool_input": {"command": f"rm -rf {target}"}}, cwd=tmp_path)
    assert r.returncode == 2
    assert "block-unsafe-recursive-delete.py" in r.stderr
    assert "symlink" in r.stderr or "junction" in r.stderr


def test_allows_a_clean_recursive_delete(tmp_path):
    target = tmp_path / "build-output"
    target.mkdir()
    (target / "artifact.txt").write_text("x", encoding="utf-8")
    r = _run({"tool_input": {"command": f"rm -rf {target}"}}, cwd=tmp_path)
    assert r.returncode == 0
    assert r.stderr.strip() == ""


def test_second_target_still_checked_after_an_earlier_allowed_one(tmp_path):
    # A command with two separate rm -rf invocations: the first targets an
    # ordinary directory (allowed), the second a worktree path (blocked).
    # Guards that resolving/checking the first candidate can't short-circuit
    # the loop before the second, genuinely dangerous one is ever reached.
    ordinary = tmp_path / "build-output"
    ordinary.mkdir()
    target = tmp_path / ".claude" / "worktrees" / "some-change"
    target.mkdir(parents=True)
    command = f"rm -rf {ordinary} && rm -rf {target}"
    r = _run({"tool_input": {"command": command}}, cwd=tmp_path)
    assert r.returncode == 2
    assert "block-unsafe-recursive-delete.py" in r.stderr


def test_allows_when_target_does_not_exist(tmp_path):
    target = tmp_path / "never-existed"
    r = _run({"tool_input": {"command": f"rm -rf {target}"}}, cwd=tmp_path)
    assert r.returncode == 0


def test_allows_a_commit_message_mentioning_rm_rf_as_prose(tmp_path):
    # Regression: this exact shape (a heredoc-wrapped commit message
    # describing this hook's own purpose) tripped the hook against itself --
    # "Remove-Item -Recurse" / "-Force" split across a line break inside the
    # heredoc body was misread as a real invocation, resolving to "/" and
    # blocking on the drive root's own junctions.
    command = """git commit -m "$(cat <<'EOF'
feat(hooks): block unsafe recursive+force delete

Prevents rm -rf / Remove-Item -Recurse
-Force from silently destroying files outside the intended target.
EOF
)\""""
    assert hook._extract_target_paths(command) == []
    r = _run({"tool_input": {"command": command}}, cwd=tmp_path)
    assert r.returncode == 0
    assert r.stderr.strip() == ""


def test_allows_non_destructive_command(tmp_path):
    r = _run({"tool_input": {"command": "git status"}}, cwd=tmp_path)
    assert r.returncode == 0
    assert r.stderr.strip() == ""


def test_escape_hatch_allows_worktree_delete(tmp_path):
    target = tmp_path / ".claude" / "worktrees" / "some-change"
    target.mkdir(parents=True)
    r = _run(
        {"tool_input": {"command": f"rm -rf {target}"}},
        cwd=tmp_path,
        env_extra={"ALLOW_UNSAFE_RM": "1"},
    )
    assert r.returncode == 0


def test_blocks_a_delete_whose_target_is_itself_a_junction(tmp_path):
    """The shape the hook was written for, and the one it used to allow.

    `rm` from git-bash/MSYS recurses THROUGH a directory junction as though it
    were an ordinary directory, so `rm -rf <the junction>` deletes the real
    contents on the far side rather than removing the link. The guard resolved
    the target before looking at it, and `Path.resolve()` follows the reparse
    point — so by the time anything checked, the junction was gone from the path
    and what remained named the destination.

    Measured before the fix: this exact command exited 0. `rm -rf` on the
    junction's PARENT exited 2, because `_contains_symlink` walks inside the
    resolved directory and finds the link there. The guard blocked the distant
    shape and allowed the near one.
    """
    real = tmp_path / "real_payload"
    real.mkdir()
    (real / "work.txt").write_text("irreplaceable\n", encoding="utf-8")
    holder = tmp_path / "holder"
    holder.mkdir()
    link = holder / "alias"
    make_dir_alias(link, real)

    r = _run({"tool_input": {"command": f"rm -rf {link}"}}, cwd=tmp_path)
    assert r.returncode == 2, "deleting the junction itself must be blocked"
    assert "itself a symlink or directory junction" in r.stderr, (
        "the message must name the target-is-a-link case, not the contains-a-link "
        "one — they have different remedies"
    )
    assert real.joinpath("work.txt").exists(), "the fixture's real payload is untouched"


@pytest.mark.parametrize("suffix", ["", "/", "/.", "\\"])
def test_blocks_the_junction_target_however_the_path_is_spelled(tmp_path, suffix):
    """Trailing separators, and the reason this is a separate test.

    `os.path.islink` is an lstat, and POSIX lstat RESOLVES a trailing slash — so
    `islink('link/')` is False while `islink('link')` is True. That matters
    because the two spellings behave in opposite directions on POSIX: measured on
    GNU coreutils, `rm -rf link` unlinks the link and the far side survives,
    while `rm -rf link/` leaves the link and DELETES the far side's contents.

    Measured with GNU coreutils 9.7: `link` leaves the far side INTACT, `link/`
    and `link//` DESTROY it, and `link/.` is refused by rm itself ("refusing to
    remove '.' or '..' directory"). So only two of these four spellings are
    actually destructive — the `/.` cases are blocked conservatively, not
    because they would delete anything.

    The first version of this fix tested the unstripped path, so on POSIX it
    blocked the safe spelling and allowed the destructive one — a precise
    inversion, found by a reviewer who ran it under WSL. Windows was never
    affected, because `os.stat(..., follow_symlinks=False)` reads the reparse
    point through a trailing separator; that is exactly why a Windows-only run
    could not see it, and why this test is parametrized rather than written
    against one spelling.
    """
    real = tmp_path / "real_payload"
    real.mkdir()
    (real / "work.txt").write_text("irreplaceable\n", encoding="utf-8")
    holder = tmp_path / "holder"
    holder.mkdir()
    link = holder / "alias"
    make_dir_alias(link, real)

    r = _run({"tool_input": {"command": f'rm -rf "{link}{suffix}"'}}, cwd=tmp_path)
    assert r.returncode == 2, f"spelling {suffix!r} must still be blocked: {r.stderr}"


def test_a_link_that_is_not_a_directory_is_not_blocked(tmp_path):
    """The false positives the first version of this fix introduced.

    A DANGLING link points at nothing and a link to a FILE has no far side to
    recurse into, so neither can produce the incident — and this hook BLOCKS and
    ships to every consuming repo, so blocking them stops real work. Measured by
    a reviewer against the first version: `rm -rf ~/.config/nvim` where that is a
    dotfiles symlink, and `rm -rf node_modules/<pkg>` in a workspace, both hard-
    blocked. `_target_is_link` requires the target to resolve to a directory.
    """
    holder = tmp_path / "holder"
    holder.mkdir()

    # A DANGLING link, made without needing symlink privilege. `mklink /J`
    # against a missing target reports success and produces a junction that
    # resolves nowhere — `make_dir_alias` skips on exactly that condition,
    # because there it is an accident; here it is the fixture. On POSIX a
    # symlink to a missing path does the same thing.
    dangling = holder / "dangling"
    made = False
    try:
        dangling.symlink_to(tmp_path / "gone", target_is_directory=True)
        made = True
    except (OSError, NotImplementedError, AttributeError):
        if os.name == "nt":
            made = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(dangling), str(tmp_path / "gone")],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            ).returncode == 0
    if not made:
        pytest.skip("no way to create a dangling link here")

    assert hook._is_link_like(str(dangling)), "the fixture must actually be a link"
    r = _run({"tool_input": {"command": f'rm -rf "{dangling}"'}}, cwd=tmp_path)
    assert r.returncode == 0, f"a dangling link points at nothing: {r.stderr}"

    # A link to a FILE, where the platform permits one. Same argument: no far
    # side to recurse into. Skipped rather than faked where symlink creation is
    # not permitted — `mklink /J` is directories-only, so there is no junction
    # equivalent of this shape.

def test_a_link_to_a_file_is_not_blocked(tmp_path):
    """The other half of the directory requirement, in its OWN test.

    It was a second half of the dangling-link test, after a bare `return` when
    symlink creation is not permitted — so on a default non-admin Windows
    account (`WinError 1314`) it never executed while the test reported PASSED,
    contributing to a "43 passed, 0 skipped" claim in which this case, the one
    the change headlines, had never run anywhere. A `pytest.skip` in the same
    place would have been visible but would also have discarded the dangling
    half's result, since a skip aborts the whole test. Two tests, two honest
    verdicts.

    The two halves also pin DIFFERENT things: the dangling one fails the
    directory check because the target is MISSING, this one because it is a
    FILE. An `os.stat`-based check that only tested existence would pass the
    first and fail this one.
    """
    real_file = tmp_path / "real.txt"
    real_file.write_text("x\n", encoding="utf-8")
    holder = tmp_path / "holder"
    holder.mkdir()
    file_link = holder / "filelink"
    try:
        file_link.symlink_to(real_file)
    except (OSError, NotImplementedError, AttributeError) as exc:
        pytest.skip(f"file symlink creation not permitted here: {exc}")

    assert hook._is_link_like(str(file_link)), "the fixture must actually be a link"
    r = _run({"tool_input": {"command": f'rm -rf "{file_link}"'}}, cwd=tmp_path)
    assert r.returncode == 0, f"a link to a FILE has no far side to recurse into: {r.stderr}"


@pytest.mark.parametrize("spelling", [
    "{p}/", "{p}//", "{p}/.", "{p}\\",
    # Added after review: the `/.` rule and the separator rule used to run
    # in SEQUENCE, so a separator AFTER the dot escaped both -- `link/.`
    # was recognised and `link/./` was not. TWO of these three discriminate
    # the fold: `{p}/./` and `{p}/./.` fail against the old ordering.
    # `{p}//.` passed under it as well (the `/.` strip left `P/`, and the
    # separator loop then ran and stripped it) and is kept as a plain
    # regression cell, not as evidence for the folding.
    "{p}/./", "{p}/./.", "{p}//.",
])
def test_the_trailing_separator_strip_is_what_sees_through_a_slash(tmp_path, spelling, monkeypatch):
    """The strip, isolated — and it can only be tested this way.

    On Windows the strip is a NO-OP: `os.stat(..., follow_symlinks=False)` reads
    the reparse point straight through a trailing separator, so
    `_is_link_like('link/')` is already True and removing the strip changes
    nothing. A mutant on it therefore SURVIVES on Windows however many junction
    fixtures you write — measured, on the batch that added it.

    On POSIX the strip is load-bearing, because `lstat` RESOLVES a trailing
    slash: `os.path.islink('link/')` is False while `os.path.islink('link')` is
    True. And `rm -rf link/` is the spelling that reaches through there.

    So this stubs `_is_link_like` with POSIX's slash-sensitive contract — true
    only for the exact path, false for any spelling carrying a trailing
    separator. That is not a mock of convenience: it is the one behaviour that
    differs between the platforms, and stating it explicitly is what lets a
    Windows machine test the POSIX-only code path at all. CLAUDE.md's warning
    that platform-divergent code is only exercised on the machine you are on is
    the reason this exists.
    """
    real = tmp_path / "real_payload"
    real.mkdir()
    holder = tmp_path / "holder"
    holder.mkdir()
    link = holder / "alias"
    make_dir_alias(link, real)

    exact = str(link)
    monkeypatch.setattr(hook, "_is_link_like", lambda p: p == exact)

    spelled = spelling.format(p=exact)
    assert hook._target_is_link(spelled), (
        f"{spelled!r} must still be recognised as targeting the link; without the "
        "trailing-separator strip this is the destructive POSIX spelling going silent"
    )
    # A weak control, and worth labelling as such rather than over-claiming. It
    # feeds a DIFFERENT input, so it catches a stub that answers True for
    # everything -- and nothing else. A reviewer replayed candidate wrong strips
    # against these assertions: front-stripping and off-by-one are caught, but
    # `os.path.dirname` (the textbook over-broad strip) passes this control
    # cleanly. What catches `dirname` is
    # `test_a_target_reached_through_a_link_is_still_allowed`, in the other
    # direction entirely.
    assert not hook._target_is_link(str(holder))


def test_a_path_whose_own_lstat_fails_blocks_rather_than_allowing(tmp_path, monkeypatch):
    """The Critical from round three: an UNREADABLE LINK, not an unreadable far
    side.

    `_is_link_like` used to swallow every probe error into False, so a link whose
    own `lstat` fails scored as "not a link" and `_target_is_link` returned False
    before the conservative far-side gate was ever reached. Measured on both
    platforms against a real junction and a real symlink whose parent denies
    traverse: rc=0, empty stderr — byte-identical to the guard having examined
    the command and approved it. The previous round installed the right policy
    one gate too far downstream to enforce itself.

    BOTH PROBES ARE DENIED, and the assertion is on IDENTITY with the sentinel.
    An earlier version stubbed only `os.lstat` and asserted `is True`, which
    reviewers showed encoded a filesystem state that cannot exist — `lstat`
    failing with EACCES while `stat` answers ENOENT for the same path. Real
    filesystems answer both calls the same way. Under a consistent stub that
    version's routing mutant SURVIVED, because a truthy sentinel falls through to
    `_far_side_is_a_directory`, which reaches the same verdict by another route.

    Asserting identity fixes that without the impossible fixture: with the
    routing branch removed the fall-through returns `_UNDETERMINED_FAR_SIDE_BLOCKS`,
    which is `True` and is NOT the sentinel, so the assertion still fails. With
    the sentinel collapsed to False it returns False. Only routing the
    undetermined verdict returns the sentinel itself.

    The identity also matters to `main`: the sentinel is what selects the
    "could not examine this path" message over the "this is a junction" one, and
    those assert different things.
    """
    def deny(path, *a, **kw):
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(hook.os, "lstat", deny)
    monkeypatch.setattr(hook.os, "stat", deny)
    assert hook._target_is_link(str(tmp_path / "gone")) is hook._LINK_UNDETERMINED, (
        "a path whose link-ness cannot be determined must return the sentinel, so "
        "it BLOCKS and says so honestly; False here is the exit-0-with-empty-stderr "
        "that reads as an approval, and True claims a junction nobody confirmed"
    )


def test_an_unreadable_far_side_blocks_rather_than_allowing(tmp_path, monkeypatch):
    """"Could not tell" must not become "allow" — the policy, pinned.

    `os.path.isdir` was the first spelling of this check and it swallows every
    error into False, so "the far side is a file" and "the far side could not be
    read" became the same answer, and the second one silently ALLOWED. A
    reviewer measured the consequence: a symlink to a directory under a mode-000
    parent was BLOCKED before the directory check existed and ALLOWED after it —
    a coverage regression introduced by the check meant to REDUCE false
    positives. A junction into a clone whose far side cannot be stat'd is
    exactly the shape this hook exists for.

    Stubbing `os.stat` rather than chmod-ing a real directory: an unreadable
    directory is trivial to make on POSIX and awkward on Windows (it needs
    `icacls` and an ACL that the test then has to unwind), so a real fixture
    would run on one platform and skip on the other — and this policy is
    platform-independent. The stub raises exactly what an unreadable parent
    raises.
    """
    def deny(path, *a, **kw):
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(hook.os, "stat", deny)
    assert hook._far_side_is_a_directory(str(tmp_path)) is True, (
        "an unreadable far side must be treated as a directory and BLOCK; "
        "returning False here is the regression that allows the delete"
    )

    # The control: a MISSING target is a determinate answer, not an undetermined
    # one, and must still allow — a dangling link cannot destroy what is not
    # there. Without this, `return True` unconditionally would pass the
    # assertion above.
    def missing(path, *a, **kw):
        raise FileNotFoundError(2, "No such file or directory", str(path))

    monkeypatch.setattr(hook.os, "stat", missing)
    assert hook._far_side_is_a_directory(str(tmp_path)) is False, (
        "a missing target is a real allow, not an unknown"
    )


@pytest.mark.parametrize("target", ["dist/*", "node_modules/*", "build/*.log", "a?b", "out 2>&1"])
def test_a_glob_or_redirection_token_is_not_treated_as_undetermined(tmp_path, target):
    """The regression the tri-state introduced, and the reason it needs three
    error classes rather than two.

    On Windows `os.lstat` raises `OSError(EINVAL)` for a path containing `*`,
    `?`, `<` or `>`, because those cannot name an NTFS file. The first tri-state
    split routed every non-ENOENT `OSError` to "undetermined", so 7 of 16
    everyday commands began to BLOCK — `rm -rf dist/*` among them — with a
    message asserting the target was a junction. This hook ships to four repos
    and the launcher runs `--permission-mode auto`, where the hooks are the
    safety layer, so that made `rm -rf dist/*` unrunnable.

    A string that cannot NAME a file is a determinate "not a link". Only a read
    failure on a nameable path is an unknown.
    """
    (tmp_path / "dist").mkdir()
    r = _run({"tool_input": {"command": f"rm -rf {tmp_path / target}"}}, cwd=tmp_path)
    assert r.returncode == 0, f"an ordinary command must not block: {r.stderr[:300]}"


def test_an_unreadable_target_says_it_could_not_examine_the_path(tmp_path, monkeypatch):
    """The block message must not assert what the code did not determine.

    The undetermined branch reused the confirmed-link text, so a path the hook
    could not READ was told it "is itself a symlink or directory junction" and
    to "remove the link itself instead" — an assertion never made and advice that
    cannot be followed. A correct fail-closed policy explained wrongly is how a
    real block gets dismissed as a known-bogus one, which costs exactly what the
    policy buys.
    """
    real = tmp_path / "real"
    real.mkdir()
    holder = tmp_path / "holder"
    holder.mkdir()
    link = holder / "alias"
    make_dir_alias(link, real)

    confirmed = _run({"tool_input": {"command": f'rm -rf "{link}"'}}, cwd=tmp_path)
    assert confirmed.returncode == 2
    assert "is itself a symlink or directory junction" in confirmed.stderr

    def deny(path, *a, **kw):
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(hook.os, "lstat", deny)
    monkeypatch.setattr(hook.os, "stat", deny)
    verdict = hook._target_is_link(str(link))
    assert verdict is hook._LINK_UNDETERMINED, (
        "an unreadable path must be distinguishable from a confirmed link, or the "
        "two cannot carry different messages"
    )


def test_a_decided_block_survives_a_failed_write_to_stderr(tmp_path, monkeypatch, capsys):
    """The `_Blocked` refactor, pinned — it had no test.

    All three block sites once sat inside `except OSError: continue`, so a
    `BrokenPipeError` writing the message skipped the `return 2`, continued the
    loop, and fell through to `return 0`: a decided BLOCK became a clean ALLOW.
    The commit that fixed it measured the defect by injection and pinned it with
    nothing, so re-nesting the prints passed the whole suite.

    Drives `main()` in-process because the failure is in the write itself, which
    a subprocess harness cannot inject.
    """
    target = tmp_path / ".claude" / "worktrees" / "some-change"
    target.mkdir(parents=True)
    payload = json.dumps({"tool_input": {"command": f"rm -rf {target}"}, "cwd": str(tmp_path)})

    class _BrokenStderr:
        def write(self, *_a, **_kw):
            raise BrokenPipeError(32, "Broken pipe")

        def flush(self):
            pass

    monkeypatch.setattr(hook.sys, "stdin", io.StringIO(payload))
    monkeypatch.setattr(hook.sys, "stderr", _BrokenStderr())
    monkeypatch.delenv("ALLOW_UNSAFE_RM", raising=False)

    with pytest.raises(BrokenPipeError):
        hook.main()


def test_an_embedded_null_in_the_path_does_not_crash_the_hook(tmp_path):
    """A regression this fix introduced and a reviewer caught.

    `os.stat` raises `ValueError` — not `OSError` — for an embedded null
    (`stat: embedded null character in path`), and the command arrives as JSON
    on stdin, so a null is trivially reachable. `os.path.islink` catches it
    internally, which is why the old code never met it: the new check was the
    first to hand a raw unresolved path to `os.stat`.

    Measured against the previous commit: `rm -rf <worktree>/x\\0y` went from
    exit 2 (an unconditional block) to exit 1 (an uncaught raise). The
    dispatcher fails that open into `permissionDecision: "ask"`, so it is not a
    silent allow — but a hard block became a prompt, and in an unattended
    multi-lite run nobody is at the prompt.
    """
    target = tmp_path / ".claude" / "worktrees" / "some-change"
    target.mkdir(parents=True)
    r = _run({"tool_input": {"command": f"rm -rf {target}\x00y"}}, cwd=tmp_path)
    assert r.returncode == 2, (
        f"the worktree block must survive a null in the path, not raise: "
        f"rc={r.returncode} stderr={r.stderr[:200]}"
    )


def test_a_target_reached_through_a_link_is_still_allowed(tmp_path):
    """The negative case that actually guards trigger 0, replacing a weaker one.

    An earlier version of this test just deleted an ordinary nested directory —
    which `test_allows_a_clean_recursive_delete` already does, more strictly,
    since it also asserts stderr is empty. It claimed to defend against an
    over-broad check invisible to every block-case test; that was not true, and
    the pre-existing test would have caught the same over-broad versions.

    This is the case neither covers: the TARGET is an ordinary directory that
    happens to sit BEHIND a link. Deleting it recurses through nothing — the
    link is above it, not below — so it must pass. macOS `/tmp` being a symlink
    to `/private/tmp` makes this an everyday shape, not a contrived one, and a
    check keyed on any ancestor's link-ness rather than the target's own would
    block every delete under it.
    """
    real = tmp_path / "real_payload"
    (real / "inner").mkdir(parents=True)
    (real / "inner" / "artifact.txt").write_text("x\n", encoding="utf-8")
    holder = tmp_path / "holder"
    holder.mkdir()
    link = holder / "alias"
    make_dir_alias(link, real)

    r = _run({"tool_input": {"command": f'rm -rf "{link}/inner"'}}, cwd=tmp_path)
    assert r.returncode == 0, (
        f"the target is behind the link, not the link itself: {r.stderr}"
    )


def test_an_override_of_anything_but_1_does_not_disarm_the_guard(tmp_path):
    """The hatch's VALUE semantics, which nothing here pinned.

    `ALLOW_UNSAFE_RM=0` reads as "off" and must not disarm a guard over recursive
    deletion. A hook treating any non-empty value as "on" does the opposite of
    what the variable says, on the one guard where being wrong destroys work.

    Written because the batch's hatch mutant (`== "1"` -> `is not None`) was
    dying for the wrong reason: its only killer was
    `test_blocks_worktree_path_delete`, which fails merely because the `_run`
    helper sets `ALLOW_UNSAFE_RM` to the empty string for every subprocess. That
    assertion states "a worktree delete is blocked", not "a non-1 value keeps the
    guard armed" — so changing `_run` to unset the variable instead, a perfectly
    reasonable cleanup, would have left the mutant alive with no test lost.
    `test_pre_push.py` pins the same property directly; this is its counterpart.
    """
    target = tmp_path / ".claude" / "worktrees" / "some-change"
    target.mkdir(parents=True)
    for value in ("0", "true", "yes", " 1"):
        r = _run(
            {"tool_input": {"command": f"rm -rf {target}"}},
            cwd=tmp_path,
            env_extra={"ALLOW_UNSAFE_RM": value},
        )
        assert r.returncode == 2, f"ALLOW_UNSAFE_RM={value!r} must not disarm the guard"


def test_malformed_stdin_does_not_block(tmp_path):
    r = subprocess.run(
        [sys.executable, str(_HOOK)],
        input="not json", capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(tmp_path),
    )
    assert r.returncode == 0


# --------------------------------------------------------------------------- #
# The escape hatch the block message actually invites (issue #220)
# --------------------------------------------------------------------------- #

def test_an_inline_allow_prefix_disarms_the_guard(tmp_path):
    """The spelling a caller types at the point of failure, and it was inert.

    The hook runs as its own process BEFORE the command's shell exists, so an
    inline env-assignment prefix never reaches `os.environ`. `main()` read only
    `os.environ`, while the block message told the caller to set
    `ALLOW_UNSAFE_RM=1` -- so `rm -rf <path>` and `ALLOW_UNSAFE_RM=1 rm -rf
    <path>` returned the identical block and the documented exit did nothing.
    """
    target = tmp_path / ".claude" / "worktrees" / "some-change"
    target.mkdir(parents=True)
    r = _run(
        {"tool_input": {"command": f"ALLOW_UNSAFE_RM=1 rm -rf {target}"}},
        cwd=tmp_path,
    )
    assert r.returncode == 0, r.stderr


def test_an_inline_allow_prefix_works_after_a_shell_separator(tmp_path):
    target = tmp_path / ".claude" / "worktrees" / "some-change"
    target.mkdir(parents=True)
    r = _run(
        {"tool_input": {"command": f"echo hi && ALLOW_UNSAFE_RM=1 rm -rf {target}"}},
        cwd=tmp_path,
    )
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("command", [
    'echo "run this: ALLOW_UNSAFE_RM=1 rm -rf x" ; rm -rf {t}',
    "echo 'x; ALLOW_UNSAFE_RM=1 y' ; rm -rf {t}",
    "rm -rf {t} # ALLOW_UNSAFE_RM=1 ",
])
def test_the_allow_prefix_is_not_satisfied_by_a_mention(tmp_path, command):
    """A quoted or trailing mention is not an assignment a shell would honour.

    Without the quoted-span strip, the second case matches: the `;` inside the
    string looks like a separator to the anchor. The guard would then be
    disarmed by text the shell treats as data.
    """
    target = tmp_path / ".claude" / "worktrees" / "some-change"
    target.mkdir(parents=True)
    r = _run({"tool_input": {"command": command.format(t=target)}}, cwd=tmp_path)
    assert r.returncode == 2, f"a mention must not disarm the guard: {command!r}"


def test_an_inline_prefix_of_anything_but_1_does_not_disarm_the_guard(tmp_path):
    target = tmp_path / ".claude" / "worktrees" / "some-change"
    target.mkdir(parents=True)
    for value in ("0", "true", "11"):
        r = _run(
            {"tool_input": {"command": f"ALLOW_UNSAFE_RM={value} rm -rf {target}"}},
            cwd=tmp_path,
        )
        assert r.returncode == 2, f"inline ALLOW_UNSAFE_RM={value!r} must not disarm"


# --------------------------------------------------------------------------- #
# The orphaned worktree: the state `git worktree remove` cannot clear (#220)
# --------------------------------------------------------------------------- #

def _init_repo(root: Path) -> None:
    for args in (
        ["init", "-q"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "t"],
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    (root / "seed.txt").write_text("seed", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "seed"], check=True, capture_output=True
    )


def test_an_orphaned_worktree_is_not_sent_into_git_worktree_remove(tmp_path):
    """The dead end #220 measured, and the reason it is a dead end.

    A directory under `.claude/worktrees/` with no `.git` file is not in git's
    registry, so `git worktree remove` fails with "is not a working tree" --
    and that is exactly the state in which a directory is left needing manual
    deletion. The hook blocked the raw delete, recommended that command, and
    named an override that did nothing, leaving no sanctioned path at all.
    """
    _init_repo(tmp_path)
    target = tmp_path / ".claude" / "worktrees" / "orphan"
    target.mkdir(parents=True)

    r = _run({"tool_input": {"command": f"rm -rf {target}"}}, cwd=tmp_path)

    assert r.returncode == 2
    assert "git worktree prune" in r.stderr
    assert "ALLOW_UNSAFE_RM=1" in r.stderr
    # The message may NAME `git worktree remove` -- explaining why it cannot
    # work here is the point. What it must not do is PRESCRIBE it, which is the
    # phrase the original message uses.
    assert "use `git worktree remove <path>` instead" not in r.stderr
    assert "would fail" in r.stderr


def test_a_registered_worktree_still_gets_the_git_worktree_remove_advice(tmp_path):
    """The counterpart, and the one that keeps the fix from being a blanket swap.

    Where git DOES list the worktree, `git worktree remove` is the right tool
    and the original message is correct. Only the orphaned state changes.
    """
    _init_repo(tmp_path)
    target = tmp_path / ".claude" / "worktrees" / "live"
    subprocess.run(
        ["git", "-C", str(tmp_path), "worktree", "add", "-q", str(target), "-b", "wt"],
        check=True, capture_output=True,
    )

    r = _run({"tool_input": {"command": f"rm -rf {target}"}}, cwd=tmp_path)

    assert r.returncode == 2
    # The PRESCRIPTIVE phrase, not the bare substring. Both messages mention
    # `git worktree remove` -- the orphan one only to say it would fail -- so
    # asserting the substring alone passes on either branch and distinguishes
    # nothing.
    assert "use `git worktree remove <path>` instead" in r.stderr
    assert "does NOT list" not in r.stderr
    assert "git worktree prune" not in r.stderr


def test_an_unanswerable_registry_lookup_keeps_the_original_advice(tmp_path):
    """Undetermined is not "not registered" -- the same policy as `_is_link_like`.

    `tmp_path` is not a git repository, so the lookup errors. Reading that as
    "git does not list it" would assert `git worktree remove` is guaranteed to
    fail when nobody actually checked.
    """
    target = tmp_path / ".claude" / "worktrees" / "some-change"
    target.mkdir(parents=True)

    r = _run({"tool_input": {"command": f"rm -rf {target}"}}, cwd=tmp_path)

    assert r.returncode == 2
    assert "use `git worktree remove <path>` instead" in r.stderr
    assert "does NOT list" not in r.stderr
    assert "git worktree prune" not in r.stderr


def test_registry_lookup_reports_undetermined_rather_than_false(tmp_path):
    assert hook._is_registered_worktree(str(tmp_path), str(tmp_path / "x")) is None
