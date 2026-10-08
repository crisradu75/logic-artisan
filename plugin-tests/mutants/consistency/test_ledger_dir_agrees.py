"""Mutation batch for test_ledger_dir_agrees.py.

Breaks the directory resolver on each side of the writer/readers contract, once
for the git-root path and once for the `CLAUDE_RETRO_DIR` override, so each
parametrized case has to fire on its own and every reader is covered. The
working-directory mutants prove the test runs from a subdirectory: from the
repo root, a resolver that used `Path.cwd()` would agree with git and survive.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_ledger_dir_agrees.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
WRITER = PLUGIN / "lib" / "log_run.py"
READERS = {
    "spec_to_pr_aggregate": PLUGIN / "skills" / "spec-to-pr-retro" / "scripts" / "spec_to_pr_aggregate.py",
    "ledger_summary": PLUGIN / "lib" / "ledger_summary.py",
}
TARGETS = [DEV / "tests" / "consistency" / "test_ledger_dir_agrees.py"]

_SIDES = [("the writer", WRITER)] + [(f"the reader {n}", p) for n, p in READERS.items()]

MUTANTS = []
for _who, _path in _SIDES:
    MUTANTS += [
        (
            f"{_who} resolves a different directory under the git root",
            _path,
            'return root / "cla.io" / "retro"',
            'return root / "cla.io" / "runs"',
            TARGETS,
        ),
        (
            f"{_who} ignores CLAUDE_RETRO_DIR",
            _path,
            'override = os.environ.get("CLAUDE_RETRO_DIR")',
            "override = None",
            TARGETS,
        ),
        (
            f"{_who} resolves from the working directory instead of the git root",
            _path,
            "root = _git_toplevel()",
            "root = Path.cwd()",
            TARGETS,
        ),
    ]
