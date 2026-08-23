"""Mutation batch for test_doc_facts.py — break each doc claim it pins and
confirm a test fails.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_doc_facts.py
"""

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
DEV = Path(__file__).resolve().parents[2]
REPO = PLUGIN.parents[2]
TARGETS = [DEV / "tests" / "consistency"]

MUTANTS = [
    (
        "README understates the skill count",
        REPO / "README.md",
        "20 workflow skills",
        "18 workflow skills",
        TARGETS,
    ),
    (
        "README's pytest-scope count goes stale",
        REPO / "README.md",
        "# every pytest scope (1 today)",
        "# every pytest scope (8 today)",
        TARGETS,
    ),
    (
        "CLAUDE.md's release line drifts from plugin.json",
        REPO / "CLAUDE.md",
        "**Current release: `cla--v0.10.0`.**",
        "**Current release: `cla--v0.9.9`.**",
        TARGETS,
    ),
    (
        "CLAUDE.md's skills-with-tests count goes stale",
        REPO / "CLAUDE.md",
        "— 6 areas under `skills/`, one",
        "— 9 areas under `skills/`, one",
        TARGETS,
    ),
    (
        "a doc names a plugin path that no longer exists",
        REPO / "DEVELOPER-GUIDE.md",
        "pytest plugin-tests    # all pytest scopes (1)",
        "pytest .claude/plugins/cla/gone    # all pytest scopes (1)",
        TARGETS,
    ),
]
