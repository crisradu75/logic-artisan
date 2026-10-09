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
# a new folder in the developer's real %TEMP% — 817 in one day of gate and
# mutation runs. The fix is not per test: the whole run's temp dir is pointed at
# a pytest-managed one, in process and for every subprocess.

TEMP_ENV = ("TMP", "TEMP", "TMPDIR")

# What the code under test creates directly under the temp dir. Watched in the
# REAL temp dir for the whole run; anything new there is a leak.
WATCHED_TEMP_ENTRIES = ("cla-annotate", "cla-annotate-profile")


@pytest.fixture(scope="session", autouse=True)
def _temp_dir_inside_the_run(tmp_path_factory):
    """Point `tempfile` and the TMP/TEMP/TMPDIR variables at a dir pytest owns.

    Session-scoped and autouse, so it is in force before any test or fixture
    runs; under xdist each worker has its own session, so each gets its own
    dir. `tempfile.tempdir` covers this process; the variables cover every
    subprocess a test starts, which inherit `os.environ`. pytest's own
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


def _watched_entries(temp_root):
    out = set()
    for name in WATCHED_TEMP_ENTRIES:
        p = os.path.join(temp_root, name)
        if not os.path.isdir(p):
            continue
        if name == "cla-annotate":
            out |= {os.path.join(name, e) for e in os.listdir(p)}
        else:
            out.add(name)
    return out


def pytest_sessionstart(session):
    """Snapshot the REAL temp dir's watched entries before any test runs. Under
    xdist this runs in the controller, which runs no tests and so never
    redirects; the workers' snapshots are never read."""
    import tempfile
    real = tempfile.gettempdir()
    session.config._cla_real_temp = (real, _watched_entries(real))


def pytest_sessionfinish(session, exitstatus):
    """Fail the run if the real temp dir gained a watched entry.

    Checked once, in the process that owns the whole run: the controller under
    xdist, the only process otherwise. Another pytest run on the same machine
    writing there at the same time would also trip it; the message names the
    entries, so that case is easy to tell apart.
    """
    if hasattr(session.config, "workerinput"):
        return
    snap = getattr(session.config, "_cla_real_temp", None)
    if snap is None:
        return
    real, before = snap
    leaked = sorted(_watched_entries(real) - before)
    if leaked:
        tr = session.config.pluginmanager.get_plugin("terminalreporter")
        msg = ("TEMP LEAK: this run created %d entr%s in the real temp dir %s, "
               "outside the run's own: %s"
               % (len(leaked), "y" if len(leaked) == 1 else "ies", real,
                  ", ".join(leaked[:10])))
        if tr is not None:
            tr.write_line(msg, red=True)
        else:
            print(msg)
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
