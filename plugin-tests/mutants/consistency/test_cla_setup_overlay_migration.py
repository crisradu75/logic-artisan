"""Mutation batch for test_cla_setup_overlay_migration.py.

Each mutant puts back one thing the review of cla-setup-and-optional-overlays
found: whole incidents moved to the lessons log with their rules, a path counted
as a fact even when only one rule uses it, codify-learnings or review-change no
longer reading that rule-owned material from the overlay, the old sync-context
pointer kept as if it were content, and the terminology format restated in
cla-setup instead of read from the shared reference.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_cla_setup_overlay_migration.py
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEV = Path(__file__).resolve().parents[2]
SKILLS = REPO / ".claude" / "plugins" / "cla" / "skills"
CLA_SETUP = SKILLS / "cla-setup" / "SKILL.md"
SHAPE = SKILLS / "shape-decision" / "SKILL.md"
GUARD = DEV / "tests" / "consistency" / "test_cla_setup_overlay_migration.py"

TARGETS = [GUARD]

MUTANTS = [
    (
        "a dated incident moves to the lessons log whole, its rules included",
        CLA_SETUP,
        "- **A dated incident's story goes to `cla.io/lessons-learned/`, and any rule it states stays in the\n  overlay** as one or two lines",
        "- **A dated incident goes to `cla.io/lessons-learned/`**",
        TARGETS,
    ),
    (
        "item 9 stops pulling rules out of incidents",
        CLA_SETUP,
        'Pull out every rule it states for this repo ("Rule here: …",',
        'Move it whole ("Rule here: …",',
        TARGETS,
    ),
    (
        "an unsure line is moved rather than kept",
        CLA_SETUP,
        "When unsure whether a line is a rule, call it one",
        "When unsure whether a line is a rule, move it",
        TARGETS,
    ),
    (
        "any path is a fact again, even one only a rule uses",
        CLA_SETUP,
        "    unless only a rule in this overlay uses it;",
        "    wherever it appears;",
        TARGETS,
    ),
    (
        "codify-learnings stops reading where memory lives from its overlay",
        SKILLS / "codify-learnings" / "SKILL.md",
        "`cla.io/overlays/codify-learnings.md`, if present, says where memory\nlives",
        "`cla.io/project-facts.md` says where memory\nlives",
        TARGETS,
    ),
    (
        "review-change stops reading its domain checks from the overlay",
        SKILLS / "review-change" / "references" / "checklist.md",
        "**Its repo-specific review checks come from `cla.io/overlays/review-change.md` when that file is present**",
        "**Its repo-specific review checks come from `cla.io/project-facts.md`**",
        TARGETS,
    ),
    (
        "the old sync-context pointer stops counting as scaffolding",
        CLA_SETUP,
        "  - **scaffolding** — headings, HTML comments, and the old pointer that sent readers to the\n    retired `sync-context` skill for repo-wide facts.",
        "  - **scaffolding** — headings and HTML comments only.",
        TARGETS,
    ),
    (
        "cla-setup restates the terminology entry format",
        CLA_SETUP,
        "What it holds and its entry format are in",
        "Entry format: `**Term**: …` then `_Avoid_: rejected-alias-1`. What it holds and its entry format are in",
        TARGETS,
    ),
    (
        "shape-decision points back at cla-setup for the terminology format",
        SHAPE,
        "Follow the entry format in `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/terminology-format.md`",
        "Follow the entry format in `${CLAUDE_PLUGIN_ROOT}/skills/cla-setup/SKILL.md`",
        TARGETS,
    ),
]
