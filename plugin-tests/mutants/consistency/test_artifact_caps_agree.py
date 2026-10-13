"""Mutation batch for test_artifact_caps_agree.py.

Each mutant puts back a cap wording the caps change removed, or weakens a cap the
rules state.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_artifact_caps_agree.py
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEV = Path(__file__).resolve().parents[2]
CONFIG = REPO / "openspec" / "config.yaml"
GUARD = DEV / "tests" / "consistency" / "test_artifact_caps_agree.py"

TARGETS = [GUARD]

MUTANTS = [
    (
        "config.yaml brings back the one-page cap",
        CONFIG,
        "about 400 words",
        "about 400 words, one page",
        TARGETS,
    ),
    (
        "the tasks rules lose the one-behaviour limit",
        CONFIG,
        "one behaviour",
        "one change",
        TARGETS,
    ),
]
