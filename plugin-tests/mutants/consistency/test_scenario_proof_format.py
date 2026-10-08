"""Mutation batch for test_scenario_proof_format.py.

Each mutant drifts one site of the requirement-to-test convention away from the
others: back to a per-scenario rule, back to a retired marker or manual form,
or a marker left naming no live requirement.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_scenario_proof_format.py
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEV = Path(__file__).resolve().parents[2]
SKILLS = REPO / ".claude" / "plugins" / "cla" / "skills"
BRIEF = SKILLS / "multi-spec" / "references" / "authoring-brief.md"
CHECKLIST = SKILLS / "review-change" / "references" / "checklist.md"
DISPATCH = SKILLS / "review-change" / "references" / "dispatch.md"
TEST_QUALITY = SKILLS / "_shared" / "references" / "test-quality.md"
CONFIG = REPO / "openspec" / "config.yaml"
GUARD = DEV / "tests" / "consistency" / "test_scenario_proof_format.py"
REVIEW_SPEC = REPO / "openspec" / "specs" / "change-review" / "spec.md"
PROBE_TEST = DEV / "tests" / "skills" / "spec-to-pr" / "test_probe_state.py"

TARGETS = [GUARD]

MUTANTS = [
    (
        "the rules go back to one test per scenario",
        CONFIG,
        "Scenarios are examples, not one test each.",
        "Each scenario needs its own test.",
        TARGETS,
    ),
    (
        "the rules ask for the retired per-scenario marker",
        CONFIG,
        "carries a `requirement: <spec> / <heading>` comment line above it",
        "carries a `scenario: <spec> / <heading>` comment line above it",
        TARGETS,
    ),
    (
        "the brief stops pointing at the rules",
        BRIEF,
        "**Apply `openspec/config.yaml` `rules:`**",
        "**Follow the stock limits**",
        TARGETS,
    ),
    (
        "the brief restates a limit the rules own, so the two can drift",
        BRIEF,
        "**Apply `openspec/config.yaml` `rules:`** as step 3's",
        "**Apply `openspec/config.yaml` `rules:`** (each requirement in 500 characters or fewer) as step 3's",
        TARGETS,
    ),
    (
        "the rules drop the unique-heading rule",
        CONFIG,
        "Keep every scenario heading unique within its spec",
        "Prefer descriptive scenario headings within its spec",
        TARGETS,
    ),
    (
        "the checklist goes back to proving scenarios",
        CHECKLIST,
        "A requirement with neither is the finding.",
        "A scenario with neither is the finding.",
        TARGETS,
    ),
    (
        "the checklist reverts its proof check to the old manual form",
        CHECKLIST,
        "or a tasks.md line `manual: <heading>: <reason>`. A requirement with neither is the finding.",
        "or a `manual: <reason>` note. A requirement with neither is the finding.",
        TARGETS,
    ),
    (
        "the dispatched task reviewer goes back to proving scenarios",
        DISPATCH,
        "A requirement with neither is **Important**.",
        "A scenario with neither is **Important**.",
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
        "the dispatched task reviewer makes a missing marker block the verdict",
        DISPATCH,
        "marker is a **Suggestion**.",
        "marker is **Important**.",
        TARGETS,
    ),
    (
        "a shipped reference keeps the old manual form",
        TEST_QUALITY,
        "`manual: <heading>: <reason>` (`openspec/config.yaml` `rules.tasks`)",
        "`manual: <reason>` (`openspec/config.yaml` `rules.tasks`)",
        TARGETS,
    ),
    (
        "a shipped reference keeps the per-scenario marker",
        TEST_QUALITY,
        "`requirement: <spec> / <heading>` comment line above it",
        "`scenario: <spec> / <heading>` comment line above it",
        TARGETS,
    ),
    (
        "the live-spec scan stops matching any spec",
        GUARD,
        'return sorted(_LIVE_SPECS.glob("*/spec.md"))',
        'return sorted(_LIVE_SPECS.glob("*/nope.md"))',
        TARGETS,
    ),
    (
        "the requirement-heading pattern stops matching",
        GUARD,
        'r"^### Requirement: (.+)$"',
        'r"^### Requirements: (.+)$"',
        TARGETS,
    ),
    (
        # Mutates the INPUT: a live spec reintroduces the retired form.
        "a live spec reintroduces the old manual form",
        REVIEW_SPEC,
        "### Requirement: A scenario with no proof is an Important finding\n",
        "### Requirement: A scenario with no proof is an Important finding\n\nOr write `manual: <reason>`.\n",
        TARGETS,
    ),
    (
        # Mutates the INPUT: a marker left naming the wrong capability, the
        # residue a spec move leaves behind.
        "a requirement marker names a capability its requirement is not in",
        GUARD,
        "# requirement: change-review / A repeated scenario heading is an Important finding",
        "# requirement: change-authoring / A repeated scenario heading is an Important finding",
        TARGETS,
    ),
    (
        # Mutates the INPUT: a test keeps a retired per-scenario marker, which
        # the requirement check above does not read.
        "a test keeps a retired per-scenario marker",
        PROBE_TEST,
        '    """Scenario: Required artifact not done."""',
        "    # scenario: orchestration / Required artifact not done",
        TARGETS,
    ),
]
