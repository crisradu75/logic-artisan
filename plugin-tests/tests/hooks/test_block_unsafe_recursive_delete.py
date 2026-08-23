"""Tests for the block-unsafe-recursive-delete PreToolUse hook.

Unit-tests the pure detection/path logic, and end-to-end-tests `main()` via
subprocess for the two trigger conditions (a worktree path, and a directory
containing a symlink/junction) plus the allow/escape-hatch cases.
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


def test_malformed_stdin_does_not_block(tmp_path):
    r = subprocess.run(
        [sys.executable, str(_HOOK)],
        input="not json", capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(tmp_path),
    )
    assert r.returncode == 0
