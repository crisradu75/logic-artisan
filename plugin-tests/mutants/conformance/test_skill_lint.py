"""Mutant batch for `tests/test_skill_lint.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/conformance/test_skill_lint.py

Each entry breaks one thing the lint claims to catch. A SURVIVOR means the lint
does not actually check that thing — which has happened here twice, so these are
kept in the repo rather than in a scratch dir.

Paths resolve from this file's own location: a batch with an absolute developer
path works on one machine and leaks a repo name into synced core.
"""

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
DEV = Path(__file__).resolve().parents[2]
SKILL = PLUGIN / "skills" / "right-model" / "SKILL.md"
LINT = DEV / "tests" / "conformance" / "test_skill_lint.py"
TARGETS = [DEV / "tests" / "conformance"]

H = "# Right-model: cost-aware model + effort picker"

MUTANTS = [
    (
        "a SKILL.md names a references/ file that exists nowhere",
        SKILL,
        H,
        "Read `references/this-file-does-not-exist.md` first.\n\n" + H,
        TARGETS,
    ),
    (
        "frontmatter name no longer matches the skill's directory",
        SKILL,
        "name: right-model",
        "name: wrong-model",
        TARGETS,
    ),
    (
        "a bare references/ path silently means another skill's file",
        SKILL,
        H,
        "See `references/checklist.md`.\n\n" + H,
        TARGETS,
    ),
    (
        "the bare-reference extractor stops matching anything",
        LINT,
        r'r"(?<![\w/])references/[A-Za-z0-9._/-]+"',
        r'r"(?<![\w/])referencesZZZ/[A-Za-z0-9._/-]+"',
        TARGETS,
    ),
    (
        "the description ceiling is tightened enough to bite",
        LINT,
        "MAX_DESCRIPTION_CHARS = 1024",
        "MAX_DESCRIPTION_CHARS = 100",
        TARGETS,
    ),
]
