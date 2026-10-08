"""Fixtures shared across test areas.

`make_dir_alias` used to be copied into three test modules (two hook guards and
`new-worktree`); it lives here so there is one copy.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


def _make_dir_alias(link: Path, real: Path) -> None:
    """Create `link` -> `real` as a directory alias, or skip if neither works.

    A real symlink where permitted, else an NTFS junction (`mklink /J`), which
    needs no elevated privileges on Windows -- unlike a symlink, which raises
    WinError 1314 for every unprivileged account. Without the fallback these
    tests skipped on the ONE platform whose path handling they exist to check,
    while the suite still reported green.

    `os.path.realpath` resolves a junction exactly like a symlink, and every
    caller goes through `realpath`, so the substitution is exact.
    (`os.path.islink()` is False for a junction -- irrelevant here, and exactly
    why `block-unsafe-recursive-delete` does its own reparse-point check rather
    than trusting `islink`.)
    """
    try:
        link.symlink_to(real, target_is_directory=True)
        return
    except (OSError, NotImplementedError, AttributeError):
        pass
    if os.name != "nt":
        # The junction fallback is Windows-only. Without this gate, ANY
        # non-privilege symlink failure on Linux/macOS -- FileExistsError, an
        # overlayfs or SMB mount that disallows symlinks -- spawned `cmd`, which
        # does not exist there, and `FileNotFoundError` propagated: the test
        # ERRORED where it previously skipped.
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


@pytest.fixture
def make_dir_alias():
    """The directory-alias helper above, as a fixture: `make_dir_alias(link, real)`."""
    return _make_dir_alias
