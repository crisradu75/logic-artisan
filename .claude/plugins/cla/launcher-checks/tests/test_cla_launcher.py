"""What survives of the launcher checks after `claw` was retired.

`claw` existed for exactly one reason: `guard-worktree-isolation.py` wrote a
presence heartbeat at SessionStart for any session whose cwd was the primary
clone, so a session that started there and only THEN ran `/cla:new-worktree`
had already registered as a contender and blocked others for an hour. That hook
is gone, so a session may now create its worktree at any point without stranding
anyone, and `claw`/`claw.cmd` went with it.

DROPPED with `test_claw.py`, deliberately and named here rather than left to be
noticed later:
  - the whole POSIX `claw` harness (arg handling, no-name refusal, worktree-name
    leak, flag vector, failing/empty/nonexistent script paths, primary-clone
    refusal, missing-plugin-dir refusal)
  - the `claw.cmd` cmd.exe suite (parse, name leak, arg forwarding, `!`
    preservation, primary-clone refusal, no-name refusal, delayed expansion,
    escaped parens)
  - `test_claw_cmd_pre_clears_its_git_dir_vars` (GD/GCD `for /f` pre-clear)
  - the two PARITY tests, which compared `claw` against `claw.cmd` — with one
    launcher pair left there is no second file to be out of sync with

`cla`/`cla.cmd` are kept for now and go when the marketplace install replaces
`--plugin-dir`; until then they are the only way to load the plugin, so their
checks stay.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[5]
_CLA = _REPO_ROOT / "cla"
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


def test_both_cla_launchers_pass_the_same_flag_vector():
    """Both files say 'keep the two in sync' — and shipped out of sync once.
    A textual parity check is the cheapest thing that would have noticed."""
    def flags(text: str) -> set[str]:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("exec claude", "call claude")):
                return {tok for tok in stripped.split() if tok.startswith("--")}
        raise AssertionError("no claude invocation line found")

    assert flags(_CLA.read_text(encoding="utf-8")) == flags(
        _CLA_CMD.read_text(encoding="utf-8")
    )


def test_the_posix_launcher_forwards_quoted_args():
    """`$*` loses the caller's quoting; the launcher must forward `"$@"`."""
    exec_line = next(
        ln for ln in _CLA.read_text(encoding="utf-8").splitlines()
        if ln.strip().startswith("exec claude")
    )
    assert '"$@"' in exec_line, 'cla must forward "$@", not $*'
