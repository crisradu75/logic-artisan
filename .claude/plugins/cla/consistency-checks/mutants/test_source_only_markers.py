"""Mutant batch for `tests/test_source_only_markers.py`.

Run: `python3 <plugin>/mutate.py <plugin>/consistency-checks/mutants/test_source_only_markers.py`

The always-True mutant is the one that matters: it survived the first version of
the guard, which greped for the detector's name instead of calling it. Paths
resolve from this file, never from an absolute developer path.
"""

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
RUNNER = PLUGIN / "run_tests.py"
TARGETS = [PLUGIN / "consistency-checks" / "tests"]

ANCHOR = "def _is_source_repo() -> bool:"
FORCE_FALSE = ANCHOR + "\n    return False"
FORCE_TRUE = ANCHOR + "\n    return True"

MUTANTS = [
    (
        "_is_source_repo always False - silently skips every source-only scope here",
        RUNNER,
        ANCHOR,
        FORCE_FALSE,
        TARGETS,
    ),
    (
        "_is_source_repo always True - marked scopes never skip in a consumer",
        RUNNER,
        ANCHOR,
        FORCE_TRUE,
        TARGETS,
    ),
    (
        "the marker constant is renamed, making every marker file inert",
        RUNNER,
        'SOURCE_ONLY_MARKER = "SOURCE-REPO-ONLY.md"',
        'SOURCE_ONLY_MARKER = "SOURCE-REPO-ONLY-RENAMED.md"',
        TARGETS,
    ),
]
