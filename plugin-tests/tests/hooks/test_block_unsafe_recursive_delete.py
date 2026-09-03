"""Tests for the block-unsafe-recursive-delete PreToolUse hook.

Unit-tests the pure detection/path logic, and end-to-end-tests `main()` via
subprocess for the three trigger conditions (a link AS the target, a worktree
path, and a directory containing a symlink/junction) plus the allow and
escape-hatch cases.
"""

from __future__ import annotations

import importlib.util
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
    assert real.joinpath("work.txt").exists()


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
    real_file = tmp_path / "real.txt"
    real_file.write_text("x\n", encoding="utf-8")
    file_link = holder / "filelink"
    try:
        file_link.symlink_to(real_file)
    except (OSError, NotImplementedError, AttributeError):
        return
    r = _run({"tool_input": {"command": f'rm -rf "{file_link}"'}}, cwd=tmp_path)
    assert r.returncode == 0, f"a link to a FILE has no far side to recurse into: {r.stderr}"


@pytest.mark.parametrize("spelling", ["{p}/", "{p}//", "{p}/.", "{p}\\"])
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
    # The control: a genuinely different path must NOT be recognised, so the
    # assertion above cannot pass by the stub or the strip being over-broad.
    assert not hook._target_is_link(str(holder))


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
