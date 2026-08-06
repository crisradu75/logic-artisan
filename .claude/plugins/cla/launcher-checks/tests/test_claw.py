"""Tests for the repo-root `claw` launcher.

`claw` runs BEFORE Claude exists, so a bug in it has no agent to diagnose it —
and its failure mode is launching in the primary clone, which is the exact
thing it was written to prevent. It had no test at all, and that gap shipped a
real bug in its `.cmd` twin (`shift` does not affect `%*`, so the worktree name
reached `claude` as an initial prompt).

Approach: run the real script in a synthetic repo, with `claude` and the
worktree script replaced by stubs that record their argv. Nothing here touches
the real repo or creates a real worktree.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[5]
_CLAW = _REPO_ROOT / "claw"
_CLAW_CMD = _REPO_ROOT / "claw.cmd"

_BASH = shutil.which("bash")
needs_bash = pytest.mark.skipif(_BASH is None, reason="bash not available")


@pytest.fixture
def harness(tmp_path: Path):
    """A fake repo containing a copy of `claw`, with stubbed `claude`/python.

    Returns a callable: run(*args) -> (returncode, stdout, stderr, launched_argv)
    where `launched_argv` is what the stub `claude` was invoked with, or None if
    it was never reached.
    """
    repo = tmp_path / "repo"
    plugin = repo / ".claude" / "plugins" / "cla"
    scripts = plugin / "skills" / "new-worktree" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy(_CLAW, repo / "claw")
    os.chmod(repo / "claw", 0o755)

    # The worktree the stub will "create": a real linked worktree is not needed,
    # but it MUST look like one to claw's git assertion, so build a real repo
    # plus a real `git worktree` — that assertion is the point of the script.
    primary = tmp_path / "primary"
    primary.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=primary, check=True)
    subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=primary, check=True)
    subprocess.run(["git", "config", "user.name", "a"], cwd=primary, check=True)
    (primary / "seed.txt").write_text("s\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=primary, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "s"], cwd=primary, check=True)
    worktree = tmp_path / "wt"
    subprocess.run(
        ["git", "worktree", "add", "-q", str(worktree), "-b", "feature/x"],
        cwd=primary, check=True,
    )
    # claw requires the worktree to carry its own plugin dir.
    (worktree / ".claude" / "plugins" / "cla").mkdir(parents=True)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    argv_log = tmp_path / "claude-argv.json"

    claude_stub = bin_dir / "claude"
    claude_stub.write_text(
        "#!/usr/bin/env bash\n"
        f'python3 -c "import json,sys; json.dump(sys.argv[1:], open(r\'{argv_log}\', \'w\'))" "$@"\n'
        "echo STUB-CLAUDE\n",
        encoding="utf-8",
    )
    os.chmod(claude_stub, 0o755)

    def _set_worktree_script(body: str) -> None:
        (scripts / "manual_worktree.py").write_text(body, encoding="utf-8")

    # Default stub: succeed, print the worktree path, exactly as --print-path does.
    _set_worktree_script(
        "import sys\n"
        f"print(r'{worktree}')\n"
        "sys.exit(0)\n"
    )

    def run(*args: str, env_extra: dict | None = None):
        env = dict(os.environ)
        env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
        env.update(env_extra or {})
        if argv_log.exists():
            argv_log.unlink()
        proc = subprocess.run(
            [_BASH, str(repo / "claw"), *args],
            capture_output=True, text=True, env=env, cwd=str(tmp_path),
        )
        launched = json.loads(argv_log.read_text(encoding="utf-8")) if argv_log.exists() else None
        return proc.returncode, proc.stdout, proc.stderr, launched

    run.set_worktree_script = _set_worktree_script  # type: ignore[attr-defined]
    run.worktree = worktree  # type: ignore[attr-defined]
    run.primary = primary  # type: ignore[attr-defined]
    return run


# --------------------------------------------------------------------------- #
# Argument handling — a missing name must never fall through to a launch
# --------------------------------------------------------------------------- #


@needs_bash
def test_no_name_refuses_without_launching(harness):
    rc, _out, err, launched = harness()
    assert rc == 1
    assert launched is None, "must not launch claude without a worktree name"
    assert "name is required" in err


@needs_bash
def test_a_leading_dash_is_treated_as_a_missing_name(harness):
    rc, _out, err, launched = harness("--help")
    assert rc == 1
    assert launched is None
    assert "expected a worktree name" in err


# --------------------------------------------------------------------------- #
# The argv contract — this is the assertion that catches the `%*` class of bug
# --------------------------------------------------------------------------- #


@needs_bash
def test_the_worktree_name_is_NOT_passed_through_to_claude(harness):
    """The name is consumed by the launcher. Leaking it into claude's argv makes
    it a trailing positional, which Claude Code reads as an initial prompt — so
    every session would auto-submit the worktree name as a user turn. This is
    the bug that shipped in claw.cmd for want of exactly this assertion."""
    _rc, _out, _err, launched = harness("myfeature")
    assert launched is not None, "expected claude to be launched"
    assert "myfeature" not in launched, f"worktree name leaked into argv: {launched}"


@needs_bash
def test_extra_args_after_the_name_ARE_forwarded(harness):
    _rc, _out, _err, launched = harness("myfeature", "--resume", "--verbose")
    assert launched is not None
    assert "--resume" in launched and "--verbose" in launched
    assert "myfeature" not in launched


@needs_bash
def test_the_launch_carries_the_expected_flag_vector(harness):
    _rc, _out, _err, launched = harness("myfeature")
    assert launched is not None
    assert "--plugin-dir" in launched
    assert "--permission-mode" in launched and "auto" in launched
    plugin_dir = launched[launched.index("--plugin-dir") + 1]
    assert plugin_dir.startswith(str(harness.worktree)), (
        "must load the plugin from the WORKTREE, not the primary clone"
    )


# --------------------------------------------------------------------------- #
# Failure paths — every one of these must refuse to launch
# --------------------------------------------------------------------------- #


@needs_bash
def test_a_failing_worktree_script_does_not_launch(harness):
    harness.set_worktree_script("import sys; sys.stderr.write('boom\\n'); sys.exit(1)")
    rc, _out, err, launched = harness("myfeature")
    assert rc == 1
    assert launched is None, "a failed worktree creation must never reach claude"
    assert "not launching" in err


@needs_bash
def test_an_empty_path_from_the_script_does_not_launch(harness):
    """Empty stdout with exit 0 — the shape that would `cd` to nowhere."""
    harness.set_worktree_script("import sys; print(''); sys.exit(0)")
    rc, _out, _err, launched = harness("myfeature")
    assert rc == 1
    assert launched is None


@needs_bash
def test_a_nonexistent_path_from_the_script_does_not_launch(harness):
    harness.set_worktree_script("import sys; print(r'/definitely/not/here'); sys.exit(0)")
    rc, _out, _err, launched = harness("myfeature")
    assert rc == 1
    assert launched is None


@needs_bash
def test_a_path_in_the_PRIMARY_CLONE_is_refused(harness):
    """The core invariant. If the script ever returned a primary-clone path,
    launching there would write the presence heartbeat claw exists to avoid —
    so the launcher asserts git_dir != git_common_dir rather than trusting it."""
    primary = harness.primary
    (primary / ".claude" / "plugins" / "cla").mkdir(parents=True)
    harness.set_worktree_script(f"import sys; print(r'{primary}'); sys.exit(0)")
    rc, _out, err, launched = harness("myfeature")
    assert rc == 1
    assert launched is None, "must never launch in the primary clone"
    assert "PRIMARY CLONE" in err


@needs_bash
def test_a_worktree_without_its_own_plugin_dir_does_not_launch(harness, tmp_path):
    shutil.rmtree(harness.worktree / ".claude" / "plugins" / "cla")
    rc, _out, err, launched = harness("myfeature")
    assert rc == 1
    assert launched is None
    assert "plugins" in err


# --------------------------------------------------------------------------- #
# Parity between the two launchers
# --------------------------------------------------------------------------- #


def _final_claude_flags(text: str) -> set[str]:
    """The flag vector on the line that actually invokes claude."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("exec claude", "call claude")):
            return {tok for tok in stripped.split() if tok.startswith("--")}
    raise AssertionError("no claude invocation line found")


def test_both_launchers_pass_the_same_flag_vector():
    """Both files say 'keep the two in sync' — and shipped out of sync. A
    textual parity check is the cheapest thing that would have noticed."""
    assert _final_claude_flags(_CLAW.read_text(encoding="utf-8")) == _final_claude_flags(
        _CLAW_CMD.read_text(encoding="utf-8")
    )


def test_neither_launcher_passes_the_raw_arg_list_after_shifting():
    """`%*` in batch ignores `shift`, and `$*` in bash loses the caller's
    quoting. Both launchers must forward an explicitly-collected tail."""
    cmd_text = _CLAW_CMD.read_text(encoding="utf-8")
    call_line = next(
        ln for ln in cmd_text.splitlines() if ln.strip().startswith("call claude")
    )
    assert "%*" not in call_line, (
        "claw.cmd must not pass %* after shift — it still holds the worktree name"
    )
    sh_text = _CLAW.read_text(encoding="utf-8")
    exec_line = next(
        ln for ln in sh_text.splitlines() if ln.strip().startswith("exec claude")
    )
    assert '"$@"' in exec_line, "claw must forward \"$@\", not $*"
