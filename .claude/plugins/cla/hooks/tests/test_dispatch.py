"""Tests for the two PreToolUse dispatcher scripts (dispatch-bash-pretooluse.py,
dispatch-edit-write-pretooluse.py), which each replace 5 separate hook-process
spawns with 1 in-process run via `_dispatch_lib`. These exercise a representative
block / warn / allow case per dispatcher, end-to-end via subprocess, to confirm
the consolidation preserves each sibling hook's original semantics.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent.parent
_BASH_DISPATCH = _HOOKS_DIR / "dispatch-bash-pretooluse.py"
_EDIT_WRITE_DISPATCH = _HOOKS_DIR / "dispatch-edit-write-pretooluse.py"


def _run(script: Path, payload: dict, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload), capture_output=True, text=True,
        cwd=str(cwd) if cwd else None,
        env={**os.environ, "ALLOW_SHARED_CLONE_MUTATION": "", "ALLOW_WORKTREE_PATH_ESCAPE": ""},
    )


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


def _hooks_copy(tmp_path: Path) -> Path:
    """Copy every hook script (dispatchers + _dispatch_lib + siblings) into a
    scratch directory so a test can corrupt one file's copy without touching
    the real hooks this whole test suite depends on."""
    dest = tmp_path / "hooks"
    dest.mkdir()
    for f in _HOOKS_DIR.glob("*.py"):
        shutil.copy(f, dest / f.name)
    return dest


# --------------------------------------------------------------------------- #
# Bash dispatcher
# --------------------------------------------------------------------------- #

def test_bash_dispatch_blocks_cd(tmp_path):
    r = _run(_BASH_DISPATCH, {"tool_input": {"command": "cd /tmp && ls"}, "cwd": str(tmp_path)})
    assert r.returncode == 2
    assert "block-cd-in-bash.py" in r.stderr


def test_bash_dispatch_blocks_unsafe_worktree_delete(tmp_path):
    target = tmp_path / ".claude" / "worktrees" / "some-change"
    target.mkdir(parents=True)
    r = _run(_BASH_DISPATCH, {"tool_input": {"command": f"rm -rf {target}"}, "cwd": str(tmp_path)})
    assert r.returncode == 2
    assert "block-unsafe-recursive-delete.py" in r.stderr


def test_bash_dispatch_warns_branch_base_off_non_master(tmp_path):
    _git(tmp_path, "init", "-b", "feature/base")
    _git(tmp_path, "config", "user.email", "t@t.t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "init")

    r = _run(
        _BASH_DISPATCH,
        {"tool_input": {"command": "git checkout -b feature/new-thing"}, "cwd": str(tmp_path)},
        cwd=tmp_path,
    )
    assert r.returncode == 0
    assert "warn-branch-base" in r.stderr
    assert "feature/base" in r.stderr


def test_bash_dispatch_allows_clean_command(tmp_path):
    r = _run(_BASH_DISPATCH, {"tool_input": {"command": "git status"}, "cwd": str(tmp_path)}, cwd=tmp_path)
    assert r.returncode == 0
    assert r.stderr.strip() == ""


def test_bash_dispatch_isolates_a_broken_sibling_hook(tmp_path):
    # A hook that fails to LOAD (position 1) must not prevent a LATER hook
    # (position 2) from still evaluating and blocking — the whole point of
    # run_hook_file's load-failure isolation.
    hooks_dir = _hooks_copy(tmp_path)
    (hooks_dir / "block-cd-in-bash.py").write_text("this is ) not ( valid python !!!", encoding="utf-8")

    r = subprocess.run(
        [sys.executable, str(hooks_dir / "dispatch-bash-pretooluse.py")],
        input=json.dumps({"tool_input": {"command": "git push origin main"}, "cwd": str(tmp_path)}),
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert r.returncode == 2
    assert "block-direct-push-to-main.py" in r.stderr  # the later hook still fired and blocked
    assert "block-cd-in-bash.py" in r.stderr           # the load failure is surfaced, not silent
    assert "failed to load" in r.stderr


def test_bash_dispatch_exits_nonzero_when_a_hook_errors_but_nothing_blocks(tmp_path):
    # A hook that crashes inside main() (not a load failure) must still make
    # the dispatcher exit non-zero even when no hook blocked, so the failure
    # is visible via Claude Code's hook-error notice instead of vanishing
    # (exit 0 discards all stderr per the documented hook contract).
    hooks_dir = _hooks_copy(tmp_path)
    (hooks_dir / "warn-branch-base.py").write_text(
        "def main():\n    raise RuntimeError('boom')\n", encoding="utf-8"
    )

    r = subprocess.run(
        [sys.executable, str(hooks_dir / "dispatch-bash-pretooluse.py")],
        input=json.dumps({"tool_input": {"command": "ls -la"}, "cwd": str(tmp_path)}),
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert r.returncode == 1
    assert "warn-branch-base" in r.stderr
    assert "boom" in r.stderr


# --------------------------------------------------------------------------- #
# Edit|Write dispatcher
# --------------------------------------------------------------------------- #

def test_edit_write_dispatch_blocks_path_escape(tmp_path):
    primary = tmp_path / "primary"
    primary.mkdir()
    _git(primary, "init", "-b", "master")
    _git(primary, "config", "user.email", "t@t.t")
    _git(primary, "config", "user.name", "t")
    (primary / "f.txt").write_text("x", encoding="utf-8")
    _git(primary, "add", "-A")
    _git(primary, "commit", "-m", "init")
    wt = tmp_path / "wt"
    _git(primary, "worktree", "add", str(wt), "-b", "feature/x")

    escape_target = primary / "escaped.txt"
    r = subprocess.run(
        [sys.executable, str(_EDIT_WRITE_DISPATCH)],
        input=json.dumps({"tool_input": {"file_path": str(escape_target), "content": "x"}}),
        capture_output=True, text=True, cwd=str(wt),
        env={**os.environ, "ALLOW_WORKTREE_PATH_ESCAPE": ""},
    )
    assert r.returncode == 2
    assert "block-worktree-path-escape.py" in r.stderr


def test_edit_write_dispatch_warns_comment_date(tmp_path):
    target = tmp_path / "script.py"
    target.write_text("x = 1\n", encoding="utf-8")
    r = _run(
        _EDIT_WRITE_DISPATCH,
        {
            "tool_input": {
                "file_path": str(target),
                "old_string": "x = 1",
                "new_string": "x = 1  # confirmed 2026-07-12",
            },
            "cwd": str(tmp_path),
        },
        cwd=tmp_path,
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "YYYY-MM-DD" in ctx


def test_edit_write_dispatch_allows_clean_edit(tmp_path):
    target = tmp_path / "notes.ts"
    r = _run(
        _EDIT_WRITE_DISPATCH,
        {"tool_input": {"file_path": str(target), "content": "export const x = 1;\n"}, "cwd": str(tmp_path)},
        cwd=tmp_path,
    )
    assert r.returncode == 0
    assert r.stdout.strip() == ""
    assert r.stderr.strip() == ""


def test_edit_write_dispatch_does_not_drop_earlier_warning_when_later_hook_blocks(tmp_path):
    # Regression: warn-smoke-test-drift.py (position 4) fires a non-blocking
    # stdout-JSON warning, then block-worktree-path-escape.py (position 5)
    # blocks on the same edit. The earlier warning must still reach the user
    # via stderr (the only channel fed back on a block) instead of vanishing.
    primary = tmp_path / "primary"
    primary.mkdir()
    _git(primary, "init", "-b", "master")
    _git(primary, "config", "user.email", "t@t.t")
    _git(primary, "config", "user.name", "t")
    (primary / "test-app.mjs").write_text(
        "page.waitForSelector('text=Total Media Budget (EUR)')\n", encoding="utf-8"
    )
    (primary / "f.txt").write_text("x", encoding="utf-8")
    _git(primary, "add", "-A")
    _git(primary, "commit", "-m", "init")
    wt = tmp_path / "wt"
    _git(primary, "worktree", "add", str(wt), "-b", "feature/x")

    # Escapes the worktree (blocks) AND removes a locator warn-smoke-test-drift.py
    # cares about (would otherwise only warn). Built with forward slashes
    # explicitly: warn-smoke-test-drift.py's scope check hardcodes
    # 'src/components/' (forward slashes), so a Windows-native backslash path
    # from Path/str() would never match its scope regardless of this fix.
    escape_target = (primary / "src" / "components" / "Thing.tsx").as_posix()
    payload = {
        "tool_input": {
            "file_path": escape_target,
            "old_string": "Total Media Budget (EUR)",
            "new_string": "Budget",
        },
    }
    r = subprocess.run(
        [sys.executable, str(_EDIT_WRITE_DISPATCH)],
        input=json.dumps(payload),
        capture_output=True, text=True, cwd=str(wt),
        env={**os.environ, "ALLOW_WORKTREE_PATH_ESCAPE": "", "CLAUDE_PROJECT_DIR": str(primary)},
    )
    assert r.returncode == 2
    assert "block-worktree-path-escape.py" in r.stderr
    assert "Total Media Budget (EUR)" in r.stderr  # the earlier warning survived


def test_edit_write_dispatch_isolates_a_broken_sibling_hook(tmp_path):
    hooks_dir = _hooks_copy(tmp_path)
    (hooks_dir / "warn-comment-dates.py").write_text("this is ) not ( valid python !!!", encoding="utf-8")

    target = tmp_path / "script.py"
    r = subprocess.run(
        [sys.executable, str(hooks_dir / "dispatch-edit-write-pretooluse.py")],
        input=json.dumps({"tool_input": {"file_path": str(target), "content": "x = 1\n"}}),
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    # Nothing else blocks this edit, but the load failure must still be visible.
    assert r.returncode == 1
    assert "warn-comment-dates.py" in r.stderr
    assert "failed to load" in r.stderr


# --------------------------------------------------------------------------- #
# Handler budget -- what a spent budget is allowed to drop, and what it is not
#
# Claude Code kills a handler at the hooks.json `timeout`, and a killed handler
# is enforcement that did not run. The dispatchers pre-empt that by skipping
# ADVISORY hooks once the budget is gone. These tests pin both halves: the
# warnings do get dropped (loudly), and the blocking guards never do.
# --------------------------------------------------------------------------- #


class _ExpiredDeadline:
    """Stands in for a budget already spent by earlier hooks in the same run."""

    def remaining(self) -> float:
        return -1.0

    def expired(self) -> bool:
        return True


def _load_dispatcher(filename: str):
    """Import a dispatcher in-process so its `Deadline` can be monkeypatched.

    The subprocess helper used elsewhere in this file runs a fresh interpreter,
    which gives a test no way to reach that symbol.
    """
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    spec = importlib.util.spec_from_file_location(
        filename.replace("-", "_")[: -len(".py")], _HOOKS_DIR / filename
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_in_process(mod, payload: dict, monkeypatch) -> int:
    monkeypatch.setattr(mod, "Deadline", lambda *a, **k: _ExpiredDeadline())
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return mod.main()


def test_bash_dispatch_skips_advisory_hooks_when_the_budget_is_spent(monkeypatch, capsys, tmp_path):
    mod = _load_dispatcher("dispatch-bash-pretooluse.py")
    rc = _run_in_process(mod, {"tool_input": {"command": "ls"}, "cwd": str(tmp_path)}, monkeypatch)
    err = capsys.readouterr().err

    assert rc == 0
    # Never silently: a dropped guard the user cannot see is the failure mode
    # this whole mechanism exists to avoid.
    assert "skipped" in err
    for advisory in mod._ADVISORY_HOOKS:
        assert advisory in err, f"{advisory} was skipped without being named"


def test_bash_dispatch_still_blocks_after_the_budget_is_spent(monkeypatch, capsys, tmp_path):
    mod = _load_dispatcher("dispatch-bash-pretooluse.py")
    rc = _run_in_process(
        mod, {"tool_input": {"command": "cd /tmp && ls"}, "cwd": str(tmp_path)}, monkeypatch
    )
    assert rc == 2, "an expired budget must never downgrade a block to an allow"
    assert "block-cd-in-bash.py" in capsys.readouterr().err


def test_edit_write_dispatch_still_blocks_after_the_budget_is_spent(monkeypatch, capsys, tmp_path):
    # Worth its own case: in this dispatcher a BLOCKING hook sits last in
    # _HOOK_FILES, so list order gives it none of the protection the Bash
    # dispatcher happens to get. Only its absence from _ADVISORY_HOOKS saves it.
    mod = _load_dispatcher("dispatch-edit-write-pretooluse.py")
    target = tmp_path / ".claude" / "notes.md"
    target.parent.mkdir(parents=True)
    rc = _run_in_process(
        mod,
        {"tool_input": {"file_path": str(target), "content": "(added 2026-01-01)"},
         "cwd": str(tmp_path)},
        monkeypatch,
    )
    assert rc == 2
    assert "block-dated-stamps-in-prose.py" in capsys.readouterr().err
