"""The push-to-main guard must actually be installed in this clone.

`block-direct-push-to-main.py` was a wired hook: `hooks.json` named it and
`test_hooks_wiring.py` asserted every named script resolved, so enforcement was
structurally guaranteed. Its replacement, `hooks/git/pre-push`, is a **git** hook
— strictly better at its job (git hands it the refspec it already resolved, so
no `git.exe` / `-C` / quoting spelling can evade it) but a plugin cannot write to
`.git/hooks`, so it only exists if somebody ran the copy command.

Nothing verified that. Absence looks exactly like compliance: no error, no
warning, and the first sign is a push to `main` that succeeds. This repo has no
CI, so a local check is the only thing that can notice.

Scoped to `consistency-checks` (never synced) because it is a fact about THIS
clone, not portable procedure — a consuming repo installs its own copy and its
own check would be its own business.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
_REPO_ROOT = _PLUGIN_ROOT.parents[2]
_SOURCE = _PLUGIN_ROOT / "hooks" / "git" / "pre-push"


def _hooks_dir() -> Path | None:
    """Where git will ACTUALLY look for hooks, asked of git itself.

    `git rev-parse --git-path hooks` is authoritative: it resolves the worktree
    `gitdir:` pointer AND honours `core.hooksPath`. Hardcoding `<gitdir>/hooks`
    gets both wrong — and `core.hooksPath` is not exotic, since Husky,
    pre-commit and lefthook all set it, often `--global`. With it set, git
    ignores `.git/hooks` entirely, so a check that looks there passes on a file
    git will never execute.

    Returns None only when git cannot answer at all.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "rev-parse", "--git-path", "hooks"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    path = Path(out.stdout.strip())
    return path if path.is_absolute() else (_REPO_ROOT / path)


def test_the_source_hook_still_exists():
    """Non-vacuity partner: if the source moved, every assertion below compares
    against nothing and the check would pass by accident."""
    assert _SOURCE.is_file(), f"{_SOURCE} is missing — the guard has no source"
    assert _SOURCE.read_bytes().strip(), "the source hook is empty"


def test_the_repo_root_resolved_correctly():
    """The other non-vacuity partner. `_REPO_ROOT` is a fixed `parents[N]` hop;
    if the plugin's depth ever changes it silently points somewhere else, git
    answers about the wrong tree or not at all, and every test here skips green."""
    assert (_REPO_ROOT / ".claude").is_dir(), (
        f"_REPO_ROOT resolved to {_REPO_ROOT}, which has no .claude/ — the "
        "parents[] hop is wrong and these guards are inspecting nothing"
    )


def test_the_pre_push_guard_is_installed_in_this_clone():
    hooks = _hooks_dir()
    if hooks is None:
        pytest.skip("git could not answer where hooks live (not a working tree)")
    installed = hooks / "pre-push"
    assert installed.is_file(), (
        f"{installed} is missing, so NOTHING stops a direct push to main in this "
        f"clone — the Python hook that used to was deleted, and a plugin cannot "
        f"write to .git/hooks. Install it:\n"
        f"  cp '{_SOURCE}' '{installed}' && chmod +x '{installed}'"
    )


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits only")
def test_the_installed_guard_is_executable():
    """git's `find_hook()` tests `access(path, X_OK)` and treats a
    non-executable hook as ABSENT — with no message. Somebody who runs the `cp`
    from the failure message above but drops the `&& chmod +x` gets a green
    install and zero protection."""
    hooks = _hooks_dir()
    if hooks is None:
        pytest.skip("git could not answer where hooks live")
    installed = hooks / "pre-push"
    if not installed.is_file():
        pytest.skip("covered by the installation test above")
    assert os.access(installed, os.X_OK), (
        f"{installed} is not executable, so git skips it silently. "
        f"Run: chmod +x '{installed}'"
    )


def test_the_installed_guard_matches_the_source():
    """A stale copy is the quieter failure: it exists, so the check above passes,
    while missing whatever the source learned since it was copied."""
    hooks = _hooks_dir()
    if hooks is None:
        pytest.skip("git could not answer where hooks live")
    installed = hooks / "pre-push"
    if not installed.is_file():
        pytest.skip("covered by the installation test above")
    assert installed.read_bytes() == _SOURCE.read_bytes(), (
        f"{installed} has drifted from {_SOURCE}. Re-copy it:\n"
        f"  cp '{_SOURCE}' '{installed}' && chmod +x '{installed}'"
    )
