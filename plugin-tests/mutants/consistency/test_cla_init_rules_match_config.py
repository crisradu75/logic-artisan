"""Mutation batch for test_cla_init_rules_match_config.py.

Each mutant edits one copy of the OpenSpec `rules:` block — the one cla-init
seeds into consuming repos, or the one this repo's `openspec/config.yaml`
carries — so the two drift, or an item loses the quotes YAML needs.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_cla_init_rules_match_config.py
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEV = Path(__file__).resolve().parents[2]
SKILL = REPO / ".claude" / "plugins" / "cla" / "skills" / "cla-init" / "SKILL.md"
CONFIG = REPO / "openspec" / "config.yaml"

TARGETS = [DEV / "tests" / "consistency" / "test_cla_init_rules_match_config.py"]

MUTANTS = [
    (
        "cla-init stops checking config.yml, so a seeded config.yaml hides the user's file",
        SKILL,
        ' && [ ! -e "$ROOT/openspec/config.yml" ]; then',
        "; then",
        [f"{TARGETS[0]}::test_the_seed_treats_config_yml_as_existing"],
    ),
    (
        "cla-init loosens the requirement limit, so consumers author under another rule",
        SKILL,
        "per ADDED requirement in 500 characters or fewer",
        "per ADDED requirement in 800 characters or fewer",
        TARGETS,
    ),
    (
        "this repo's config drops the scenario-proof rule cla-init still seeds",
        CONFIG,
        '  tasks:\n    - "Give each ADDED or MODIFIED scenario a test task, or a `manual: <reason>` note."\n',
        "",
        TARGETS,
    ),
    (
        "cla-init unquotes an item containing ': ', so YAML reads it as a mapping",
        SKILL,
        '    - "Give each ADDED or MODIFIED scenario a test task, or a `manual: <reason>` note."',
        "    - Give each ADDED or MODIFIED scenario a test task, or a `manual: <reason>` note.",
        # Only the quoting test: the equality test would kill this one too,
        # which would prove nothing about the quoting check.
        [f"{TARGETS[0]}::test_an_item_with_a_colon_is_quoted"],
    ),
]
