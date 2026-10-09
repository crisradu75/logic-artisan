"""Fixtures shared across test areas.

`make_dir_alias` used to be copied into several test modules (hook guards and
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


# ---------------------------------------------------------------- the temp dir
#
# Code under test writes to the system temp dir on its own: `render_doc.page_dir`
# puts every rendered page under `<temp>/cla-annotate/<hash of the repo root>`,
# and a test's repo root is a fresh tmp path each time, so every such test left
# a new folder in the developer's real temp dir. The fix is not per test: the
# whole run's temp dir is pointed at a pytest-managed one, in process and for
# every subprocess. tests/skills/annotate/test_temp_dir_isolation.py checks
# that the redirect is in force — it asserts where temp paths resolve, so no
# other process writing to the real temp dir can fail it.

TEMP_ENV = ("TMP", "TEMP", "TMPDIR")


@pytest.fixture(scope="session", autouse=True)
def run_temp_dir(tmp_path_factory):
    """Point `tempfile` and the TMP/TEMP/TMPDIR variables at a dir pytest owns,
    and yield that dir.

    Session-scoped and autouse, so it is in force before any test or fixture
    runs; under xdist each worker has its own session, so each gets its own
    dir. `tempfile.tempdir` covers this process; the variables cover every
    subprocess a test starts with the inherited environment. pytest's own
    basetemp is already resolved by the `mktemp` call below, so tmp_path keeps
    working exactly as before.
    """
    import tempfile
    redirected = str(tmp_path_factory.mktemp("systemp"))
    saved_dir = tempfile.tempdir
    saved_env = {k: os.environ.get(k) for k in TEMP_ENV}
    tempfile.tempdir = redirected
    for k in TEMP_ENV:
        os.environ[k] = redirected
    yield redirected
    tempfile.tempdir = saved_dir
    for k, v in saved_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

