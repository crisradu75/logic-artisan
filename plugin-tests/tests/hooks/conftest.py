"""Scope-wide fixtures for the hook tests.

ONE JOB: start every test from a known environment.

Several guards in this tree ship a documented escape hatch read from the
environment, and each one turns its guard into a no-op that exits 0 having
printed to stderr only. A test helper that reads stdout then sees nothing and
reports "the guard stayed silent" — so with the variable exported, every
"must stay silent" assertion in the scope passes for EVERY input, destructive
ones included. Those are exactly the assertions that prove a guard does not
over-match, so they are the half that must never be able to pass vacuously.

This is not hypothetical housekeeping. Measured with `ALLOW_DESTRUCTIVE_GIT=1`
exported: 64 tests failed and
`test_an_alternative_spelling_of_a_safe_command_still_stays_silent` passed
vacuously — a test shipped AS a non-vacuity guarantee, guaranteeing nothing.
The variables are not obscure either: `ask-destructive-git`'s own ask message
recommends exporting one for unattended batches, and this harness runs
`--permission-mode auto` for exactly those.

Individual tests that want a hatch ON still set it themselves; `monkeypatch`
runs this fixture at setup, before the test body, so a later `setenv` wins.
"""

from __future__ import annotations

import pytest

# Every environment-read escape hatch in `hooks/`. Grep for `environ.get` there
# before adding a guard with a new one — an unlisted hatch reintroduces exactly
# the vacuity described above, silently.
_ESCAPE_HATCHES = (
    "ALLOW_DESTRUCTIVE_GIT",       # ask-destructive-git.py:253
    "ALLOW_PR_MERGE",              # ask-destructive-git.py:315
    "ALLOW_WORKTREE_PATH_ESCAPE",  # block-worktree-path-escape.py:149
)
# Not listed: CLAUDE_PROJECT_DIR (warn-wholesale-rewrite.py:210). It is
# configuration the tests set for themselves, not a guard-disabling flag, and
# clearing it would silently reroute the guard to the process cwd.


@pytest.fixture(autouse=True)
def _neutralise_escape_hatches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Autouse deliberately: the dependency is invisible at the call site, so a
    test added later would inherit the vacuity without anyone opting in."""
    for name in _ESCAPE_HATCHES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def _isolate_the_probe_cache(monkeypatch: pytest.MonkeyPatch,
                             tmp_path_factory: pytest.TempPathFactory) -> None:
    """Keep the interpreter probe's cache out of the developer's real HOME.

    `probe-python.sh` resolves its cache to `${CLA_PROBE_CACHE:-$HOME/.cache/cla/pyexe}`,
    and `test_hooks_wiring.py`'s `_inherited_env` builds environments from
    `dict(os.environ)` — so every test using it pointed the probe at the REAL
    `~/.cache/cla/pyexe` and, on a miss, wrote it.

    Measured: `rm -f ~/.cache/cla/pyexe && pytest plugin-tests/tests/hooks/test_hooks_wiring.py`
    recreates the file. Two costs, and the second is the one that bit. Writing a
    developer's home directory from a test suite is wrong on its own. Worse, it
    is ONE shared mutable file with several xdist workers reading and rewriting
    it, and on 2026-09-05 a plain `-n auto` run failed 3 of that file's tests
    which serial and `--dist loadfile` both passed, then went green on the next
    invocation. `loadfile` keeps the file's tests on one worker, which fits.
    Recorded as the leading candidate rather than a proven cause — the failure
    did not reproduce on demand, which is exactly why the shared state goes
    rather than being reasoned about further.

    Autouse for the same reason as the fixture above: the dependency is invisible
    at the call site. A test added later that shells out to the probe inherits
    isolation without knowing it needed to ask.

    `tmp_path_factory` rather than `tmp_path` so this composes with tests that
    take `tmp_path` themselves and build their own trees under it — the cache
    must not appear inside a directory a test is about to assert the contents of.

    OPTING OUT: the two tests that exercise the cache deliberately want the
    HOME-derived path. They pass `CLA_PROBE_CACHE=""` in their own env, which the
    probe's `:-` expansion treats as unset, restoring the fallback. Empty is the
    opt-out; unset here would mean the real HOME.
    """
    cache = tmp_path_factory.mktemp("probe-cache") / "pyexe"
    monkeypatch.setenv("CLA_PROBE_CACHE", str(cache).replace("\\", "/"))
