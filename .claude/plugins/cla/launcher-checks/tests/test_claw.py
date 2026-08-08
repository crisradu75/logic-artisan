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
import pathlib
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
            capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(tmp_path),
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


# --------------------------------------------------------------------------- #
# claw.cmd — EXECUTED, not just read
#
# Every other .cmd assertion in this file is textual (flag parity, no `%*`
# after shift). Textual checks cannot catch a cmd.exe PARSE error, and one
# shipped: three unescaped `(` inside echoes within `if (...)` blocks made the
# whole script abort with `was was unexpected at this time.` on every real
# invocation. The no-args path survived — cmd parses blocks lazily, and that
# path exits before reaching them — so any test that only ran `claw.cmd` with
# no arguments would have stayed green while the launcher was 100% broken.
#
# These therefore drive the FULL path, through to the stub `claude`.
# --------------------------------------------------------------------------- #

needs_windows = pytest.mark.skipif(
    sys.platform != "win32", reason="claw.cmd is a Windows batch file"
)


@pytest.fixture
def cmd_harness(tmp_path: Path):
    """A synthetic repo + real linked worktree, with `claude` stubbed on PATH."""
    primary = tmp_path / "primary"
    primary.mkdir()
    g = lambda *a: subprocess.run(["git", "-C", str(primary), *a], check=True,
                                  capture_output=True, text=True, encoding="utf-8", errors="replace")
    subprocess.run(["git", "init", "-q", "-b", "main", str(primary)], check=True,
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    g("config", "user.email", "a@b.c"); g("config", "user.name", "a")
    (primary / "seed.txt").write_text("s\n", encoding="utf-8")
    g("add", "-A"); g("commit", "-q", "-m", "s")

    # A REAL linked worktree, so the git_dir != git_common_dir assertion is
    # exercised for real rather than mocked — that assertion was itself dead in
    # a prior version and only a real worktree distinguishes the two states.
    worktree = tmp_path / "wt"
    g("worktree", "add", "-q", str(worktree), "-b", "feature/x")
    (worktree / ".claude" / "plugins" / "cla").mkdir(parents=True)

    plugin = primary / ".claude" / "plugins" / "cla"
    scripts = plugin / "skills" / "new-worktree" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy(_CLAW_CMD, primary / "claw.cmd")
    (scripts / "manual_worktree.py").write_text(
        f"import sys\nprint(r'{worktree}')\nsys.exit(0)\n", encoding="utf-8"
    )

    bin_dir = tmp_path / "bin"; bin_dir.mkdir()
    argv_log = tmp_path / "argv.txt"
    # A .cmd stub, because `where claude` must find it from cmd.exe.
    (bin_dir / "claude.cmd").write_text(
        "@echo off\r\n"
        f'echo %*> "{argv_log}"\r\n'
        "echo STUB-CLAUDE\r\n",
        encoding="utf-8",
    )

    def run(*args: str):
        env = dict(os.environ)
        env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
        if argv_log.exists():
            argv_log.unlink()
        proc = subprocess.run(
            ["cmd", "/c", str(primary / "claw.cmd"), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(tmp_path),
        )
        launched = argv_log.read_text(encoding="utf-8").strip() if argv_log.exists() else None
        return proc.returncode, proc.stdout, proc.stderr, launched

    run.worktree = worktree      # type: ignore[attr-defined]
    run.primary = primary        # type: ignore[attr-defined]
    return run


@needs_windows
def test_cmd_launcher_parses_and_reaches_the_launch(cmd_harness):
    """The regression test for the parse error. If any block in claw.cmd has an
    unescaped paren, cmd aborts here with 'was unexpected at this time.' and
    `launched` is None."""
    rc, out, err, launched = cmd_harness("mytask")
    assert "unexpected at this time" not in (out + err), (
        f"claw.cmd failed to PARSE — an unescaped ( inside an if block?\n{out}\n{err}"
    )
    assert launched is not None, f"claude was never reached.\nstdout={out}\nstderr={err}"


@needs_windows
def test_cmd_launcher_does_not_leak_the_worktree_name_into_argv(cmd_harness):
    """`shift` does not affect `%*`; leaking the name makes it an initial prompt."""
    _rc, _out, _err, launched = cmd_harness("mytask")
    assert launched is not None
    assert "mytask" not in launched, f"worktree name leaked into argv: {launched!r}"


@needs_windows
def test_cmd_launcher_forwards_extra_args(cmd_harness):
    _rc, _out, _err, launched = cmd_harness("mytask", "--resume")
    assert launched is not None and "--resume" in launched


@needs_windows
def test_cmd_launcher_preserves_a_bang_in_an_argument(cmd_harness):
    """Delayed expansion ate `!`: `-p "fix the bug!"` arrived as `fix the bug`,
    and `"wow! amazing! done"` silently lost a word as an undefined variable."""
    _rc, _out, _err, launched = cmd_harness("mytask", "-p", "fix the bug!")
    assert launched is not None
    assert "fix the bug!" in launched, f"the ! was mangled: {launched!r}"


@needs_windows
def test_cmd_launcher_refuses_a_name_that_resolves_to_the_primary_clone(cmd_harness):
    """The one load-bearing invariant, and it was DEAD: `--absolute-git-dir` is
    absolute while `--git-common-dir` is a bare relative `.git` in the primary
    clone, so the raw strings could never be equal and the refusal never fired.
    Asserting the refusal itself, not just that the happy path works."""
    primary = cmd_harness.primary
    scripts = primary / ".claude" / "plugins" / "cla" / "skills" / "new-worktree" / "scripts"
    (scripts / "manual_worktree.py").write_text(
        f"import sys\nprint(r'{primary}')\nsys.exit(0)\n", encoding="utf-8"
    )
    rc, out, err, launched = cmd_harness("mytask")
    assert launched is None, "must never launch in the primary clone"
    assert rc == 1
    assert "PRIMARY CLONE" in (out + err)


@needs_windows
def test_cmd_launcher_refuses_without_a_name(cmd_harness):
    rc, out, err, launched = cmd_harness()
    assert rc == 1 and launched is None
    assert "name is required" in (out + err)


def test_cmd_launcher_keeps_delayed_expansion_off():
    """Turning it back on silently reintroduces the `!`-mangling bug, which no
    textual parity check would notice."""
    text = _CLAW_CMD.read_text(encoding="utf-8", errors="replace")
    assert "enabledelayedexpansion" not in text.lower().replace("disabledelayedexpansion", "")


def test_cmd_launcher_escapes_parens_inside_if_blocks():
    """Cheap structural backstop for the parse error, so the reason is named
    even on a non-Windows machine where the execution tests skip."""
    depth = 0
    offenders = []
    for lineno, raw in enumerate(_CLAW_CMD.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        line = raw.strip()
        if line.lower().startswith("rem"):
            continue
        if depth > 0 and line.lower().startswith("echo"):
            body = line
            for i, ch in enumerate(body):
                if ch in "()" and (i == 0 or body[i - 1] != "^"):
                    offenders.append((lineno, raw.strip()))
                    break
        depth += raw.count("(") - raw.count(")") if line.endswith("(") or line == ")" else 0
        depth = max(depth, 0)
    assert not offenders, (
        "unescaped parens in an echo inside an if block — cmd aborts the whole "
        f"script at parse time: {offenders}"
    )


# --------------------------------------------------------------------------- #
# AA-9 / AA-10 — launcher defects reported by a consuming repo
#
# Both sit OUTSIDE SCAN_DIRS/SCAN_FILES' reach for review purposes: `update-cla`
# can carry the files, but nothing tested them, which is how both shipped.
# --------------------------------------------------------------------------- #

_CLA_CMD = _REPO_ROOT / "cla.cmd"


@pytest.mark.skipif(os.name != "nt", reason="cmd.exe parse semantics")
def test_cla_cmd_parses_in_real_cmd(tmp_path):
    """`cla.cmd` was UNCONDITIONALLY broken on native Windows.

    cmd parses a parenthesised block as ONE unit before executing any of it, so
    an unescaped `(` inside an echo aborts the whole script at PARSE time with
    "was was unexpected at this time." -- whether or not the branch is taken.
    Verified in real cmd.exe: EXIT=255 and no launch, in both states.

    The plugin dir is CREATED and PATH is stripped to System32, so the script
    gets past its first guard and into the `where claude` block that holds the
    defect, then exits 127 without launching anything. An earlier version of
    this test left the plugin dir missing -- the script exited at guard one, cmd
    never parsed the later block, and the test passed against the broken file.
    """
    work = tmp_path / "work"
    (work / ".claude" / "plugins" / "cla").mkdir(parents=True)
    shutil.copy(_CLA_CMD, work / "cla.cmd")

    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    env = {
        "SystemRoot": system_root,
        "PATH": os.pathsep.join([str(pathlib.Path(system_root) / "System32"), system_root]),
        "COMSPEC": os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"),
    }
    r = subprocess.run(
        ["cmd", "/c", str(work / "cla.cmd")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=work, env=env,
    )
    combined = (r.stdout or "") + (r.stderr or "")
    assert "unexpected at this time" not in combined, (
        f"cla.cmd fails to PARSE (exit={r.returncode}):\n{combined[:400]}"
    )
    assert r.returncode == 127, (
        f"expected the missing-claude guard (127), got {r.returncode}: {combined[:300]}"
    )


@pytest.mark.parametrize("var", ["GD", "GCD"])
def test_claw_cmd_pre_clears_its_git_dir_vars(var):
    """A `for /f` over a command that produces NO output leaves the variable at
    whatever it already held, so an inherited value from the parent environment
    satisfies the `if not defined` guards and feeds stale paths into the
    primary-clone assertion -- turning a fail-closed check into a launch.

    `PYEXE` and `WORKTREE_PATH` in the same file are both pre-cleared for
    exactly this reason; these two were the pair that did not follow the rule.
    """
    src = _CLAW_CMD.read_text(encoding="utf-8", errors="replace")
    clear_at = src.find(f'set "{var}="')
    use_at = src.find(f'do set "{var}=%%I"')
    assert clear_at != -1, f"{var} is never pre-cleared"
    assert use_at != -1, f"{var} assignment not found"
    assert clear_at < use_at, f"{var} must be cleared BEFORE its for /f loop"
