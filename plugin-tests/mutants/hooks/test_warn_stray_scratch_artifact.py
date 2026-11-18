"""Mutant batch for `tests/hooks/test_warn_stray_scratch_artifact.py` -- the
advisory hook that warns when a `git add` or `git commit` may sweep in a stray
scratch file, in `warn-stray-scratch-artifact.py`.

Run:
    python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_warn_stray_scratch_artifact.py

Started with #526, which moved the hook's matcher onto
`_dispatch_lib.GitInvocation`. The matcher itself is mutated in
`test_dispatch_lib.py`'s batch; this one breaks the hook's own use of it.

Anchors are single lines (the source is CRLF in a Windows checkout).
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]          # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
HOOK = PLUGIN / "hooks" / "warn-stray-scratch-artifact.py"
TARGETS = [DEV / "tests" / "hooks" / "test_warn_stray_scratch_artifact.py"]

MUTANTS = [
    (
        # Killed by the `git add` warn cases.
        "git add stops being recognised, so a stray file staged by add goes unwarned",
        HOOK,
        '_GIT_ADD_OR_COMMIT = GitInvocation(r"(?:add|commit)\\b")',
        '_GIT_ADD_OR_COMMIT = GitInvocation(r"(?:addX|commit)\\b")',
        TARGETS,
    ),
    (
        # Killed by the `git commit` warn cases.
        "git commit stops being recognised",
        HOOK,
        '_GIT_ADD_OR_COMMIT = GitInvocation(r"(?:add|commit)\\b")',
        '_GIT_ADD_OR_COMMIT = GitInvocation(r"(?:add|commitX)\\b")',
        TARGETS,
    ),
]
