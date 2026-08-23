"""The `pre-push` guard that replaced `block-direct-push-to-main.py`.

The hook it replaces guessed a push's destination by parsing the command
string, and lost to every spelling variant git accepts. These tests assert the
property that made the replacement worth the swap: the guard reads the REFSPEC
git resolved, so the command's spelling is irrelevant by construction — there
is no `git.exe` / `-C` / quoting case to test, because none of them can reach
this code path differently.

What IS worth testing is the ref parsing itself: which refs are refused, that
a normal feature push is untouched, that a multi-ref push is refused if ANY of
its refs targets the default branch, and that the documented override works.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_PRE_PUSH = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "hooks" / "git" / "pre-push"
_SH = shutil.which("sh")

# Every hook here is a POSIX sh script; git runs it under its bundled sh even
# on Windows. A machine without `sh` cannot run the real hook either, so
# skipping is honest rather than a hidden gap.
pytestmark = pytest.mark.skipif(_SH is None, reason="no POSIX sh on PATH")

_ZERO = "0" * 40
_SHA = "a" * 40


def _run(stdin_text: str, env_extra: dict | None = None):
    import os

    env = {**os.environ, **(env_extra or {})}
    env.pop("ALLOW_PUSH_TO_MAIN", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [_SH, str(_PRE_PUSH)],
        input=stdin_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def _line(remote_ref: str, local_sha: str = _SHA) -> str:
    return f"refs/heads/x {local_sha} {remote_ref} {_ZERO}\n"


@pytest.mark.parametrize("branch", ["main", "master"])
def test_refuses_a_push_to_the_default_branch(branch):
    r = _run(_line(f"refs/heads/{branch}"))
    assert r.returncode == 1
    assert branch in r.stderr
    assert "refusing to push" in r.stderr


def test_allows_a_feature_branch_push():
    r = _run(_line("refs/heads/feature/thing"))
    assert r.returncode == 0
    assert r.stderr.strip() == ""


def test_allows_a_branch_whose_name_merely_contains_main():
    # `refs/heads/maintenance` must not be caught by a substring match — the
    # case-arm is an exact ref comparison, and this pins it.
    r = _run(_line("refs/heads/maintenance"))
    assert r.returncode == 0


def test_refuses_a_deletion_of_the_default_branch():
    # A delete arrives with an all-zero LOCAL sha and the same remote ref.
    r = _run(_line("refs/heads/main", local_sha=_ZERO))
    assert r.returncode == 1


def test_refuses_a_multi_ref_push_when_any_ref_targets_main():
    r = _run(_line("refs/heads/feature/a") + _line("refs/heads/main"))
    assert r.returncode == 1


def test_allows_a_multi_ref_push_of_only_feature_branches():
    r = _run(_line("refs/heads/feature/a") + _line("refs/heads/feature/b"))
    assert r.returncode == 0


def test_the_documented_override_works():
    r = _run(_line("refs/heads/main"), {"ALLOW_PUSH_TO_MAIN": "1"})
    assert r.returncode == 0


def test_an_override_of_anything_but_1_does_not_disarm_the_guard():
    # A guard that treats any non-empty value as "on" disarms on a stray
    # `ALLOW_PUSH_TO_MAIN=0`, which reads as the opposite of what it does.
    r = _run(_line("refs/heads/main"), {"ALLOW_PUSH_TO_MAIN": "0"})
    assert r.returncode == 1


def test_empty_stdin_is_allowed():
    # `git push` with nothing to do hands the hook no lines at all.
    r = _run("")
    assert r.returncode == 0
