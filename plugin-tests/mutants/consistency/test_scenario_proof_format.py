"""Mutation batch for test_scenario_proof_format.py.

Each mutant drifts one site of the scenario-to-test convention away from the
others: back to the old `manual: <reason>` form, or dropping a rule the guard
ported from crisradu75/interoga-ro#711 will rely on.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_scenario_proof_format.py
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEV = Path(__file__).resolve().parents[2]
SKILLS = REPO / ".claude" / "plugins" / "cla" / "skills"
BRIEF = SKILLS / "multi-spec" / "references" / "authoring-brief.md"
CHECKLIST = SKILLS / "review-change" / "references" / "checklist.md"
TEST_QUALITY = SKILLS / "_shared" / "references" / "test-quality.md"
CONFIG = REPO / "openspec" / "config.yaml"

TARGETS = [DEV / "tests" / "consistency" / "test_scenario_proof_format.py"]

MUTANTS = [
    (
        "the brief drops the marker, so authored tests carry no link",
        BRIEF,
        "a comment line `scenario: <spec> / <heading>` above it",
        "a comment naming the scenario above it",
        TARGETS,
    ),
    (
        "the brief's manual line stops naming the heading, so a guard cannot match it",
        BRIEF,
        "or a tasks.md line `manual: <heading>: <reason>`, naming the heading",
        "or a tasks.md line `manual: <reason>`, naming the heading",
        TARGETS,
    ),
    (
        "the config drops the pure-rename exemption",
        CONFIG,
        "A pure heading rename, or a scenario carried forward unchanged in a MODIFIED block, needs neither.",
        "A scenario carried forward unchanged in a MODIFIED block needs neither.",
        TARGETS,
    ),
    (
        "the brief drops the unique-heading rule",
        BRIEF,
        "**Scenario headings are unique within one spec**",
        "**Scenario headings should be descriptive**",
        TARGETS,
    ),
    (
        "the checklist reverts its scenario-proof check to the old manual form",
        CHECKLIST,
        "or a tasks.md line `manual: <heading>: <reason>`. A scenario with neither is the finding.",
        "or a `manual: <reason>` note. A scenario with neither is the finding.",
        TARGETS,
    ),
    (
        "the checklist drops the repeated-heading finding",
        CHECKLIST,
        "- **Repeated scenario heading.**",
        "- **Scenario heading style.**",
        TARGETS,
    ),
    (
        "the checklist makes a missing marker block the verdict",
        CHECKLIST,
        "will carry is a **Suggestion**, not a blocker.",
        "will carry is **Important**.",
        TARGETS,
    ),
    (
        "a shipped reference keeps the old manual form",
        TEST_QUALITY,
        "`manual: <heading>: <reason>` (`multi-spec/references/authoring-brief.md`, step 4)",
        "`manual: <reason>` (`multi-spec/references/authoring-brief.md`, step 4)",
        TARGETS,
    ),
]
