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
    "ALLOW_UNSAFE_RM",             # block-unsafe-recursive-delete.py:244
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
