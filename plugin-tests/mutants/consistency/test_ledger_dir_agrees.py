"""Mutation batch for test_ledger_dir_agrees.py.

Breaks the directory resolver on each side of the writer/reader pair, once for
the git-root path and once for the `CLAUDE_RETRO_DIR` override, so each of the
test's two parametrized cases has to fire on its own.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_ledger_dir_agrees.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
WRITER = PLUGIN / "lib" / "log_run.py"
READER = PLUGIN / "skills" / "spec-to-pr-retro" / "scripts" / "spec_to_pr_aggregate.py"
TARGETS = [DEV / "tests" / "consistency" / "test_ledger_dir_agrees.py"]

MUTANTS = [
    (
        "the writer puts the ledger under a different directory than the reader",
        WRITER,
        'return root / "cla.io" / "retro"',
        'return root / "cla.io" / "runs"',
        TARGETS,
    ),
    (
        "the reader looks under a different directory than the writer",
        READER,
        'return root / "cla.io" / "retro"',
        'return root / "cla.io" / "runs"',
        TARGETS,
    ),
    (
        "the writer ignores CLAUDE_RETRO_DIR while the reader honours it",
        WRITER,
        'override = os.environ.get("CLAUDE_RETRO_DIR")',
        "override = None",
        TARGETS,
    ),
    (
        "the reader ignores CLAUDE_RETRO_DIR while the writer honours it",
        READER,
        'override = os.environ.get("CLAUDE_RETRO_DIR")',
        "override = None",
        TARGETS,
    ),
]
