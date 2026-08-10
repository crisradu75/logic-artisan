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

from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = _PLUGIN_ROOT.parents[2]
_SOURCE = _PLUGIN_ROOT / "hooks" / "git" / "pre-push"


def _git_dir() -> Path | None:
    """`.git` as a directory, resolving the worktree pointer file.

    In a linked worktree `.git` is a FILE containing `gitdir: <path>`, and hooks
    live in the shared common dir — so a worktree must resolve through to the
    same `hooks/` the primary clone uses, not report a missing guard.
    """
    dot_git = _REPO_ROOT / ".git"
    if dot_git.is_dir():
        return dot_git
    if dot_git.is_file():
        line = dot_git.read_text(encoding="utf-8").strip()
        if not line.startswith("gitdir: "):
            return None
        target = Path(line[len("gitdir: "):])
        if not target.is_absolute():
            target = (_REPO_ROOT / target).resolve()
        # A worktree's gitdir is <common>/worktrees/<name>; hooks are two up.
        if target.parent.name == "worktrees":
            target = target.parent.parent
        return target if target.is_dir() else None
    return None


def test_the_source_hook_still_exists():
    """Non-vacuity partner: if the source moved, every assertion below compares
    against nothing and the check would pass by accident."""
    assert _SOURCE.is_file(), f"{_SOURCE} is missing — the guard has no source"
    assert _SOURCE.read_bytes().strip(), "the source hook is empty"


def test_the_pre_push_guard_is_installed_in_this_clone():
    git_dir = _git_dir()
    if git_dir is None:
        pytest.skip("not a git working tree (a tarball or export) — nothing to install into")
    installed = git_dir / "hooks" / "pre-push"
    assert installed.is_file(), (
        f"{installed} is missing, so NOTHING stops a direct push to main in this "
        f"clone — the Python hook that used to was deleted, and a plugin cannot "
        f"write to .git/hooks. Install it:\n"
        f"  cp '{_SOURCE}' '{installed}' && chmod +x '{installed}'"
    )


def test_the_installed_guard_matches_the_source():
    """A stale copy is the quieter failure: it exists, so the check above passes,
    while missing whatever the source learned since it was copied."""
    git_dir = _git_dir()
    if git_dir is None:
        pytest.skip("not a git working tree")
    installed = git_dir / "hooks" / "pre-push"
    if not installed.is_file():
        pytest.skip("covered by the installation test above")
    assert installed.read_bytes() == _SOURCE.read_bytes(), (
        f"{installed} has drifted from {_SOURCE}. Re-copy it:\n"
        f"  cp '{_SOURCE}' '{installed}' && chmod +x '{installed}'"
    )
