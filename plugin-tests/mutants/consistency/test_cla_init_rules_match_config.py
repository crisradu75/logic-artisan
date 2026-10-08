"""Mutation batch for test_cla_init_rules_match_config.py.

Each mutant edits one copy of the OpenSpec `rules:` block — the one cla-init
seeds into consuming repos, or the one this repo's `openspec/config.yaml`
carries — so the two drift, or an item loses the quotes YAML needs; or breaks
the seed script's report on an existing config; or puts a third copy of the
spec rules in a skill.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_cla_init_rules_match_config.py
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEV = Path(__file__).resolve().parents[2]
SKILL = REPO / ".claude" / "plugins" / "cla" / "skills" / "cla-init" / "SKILL.md"
CHECKLIST = REPO / ".claude" / "plugins" / "cla" / "skills" / "review-change" / "references" / "checklist.md"
CONFIG = REPO / "openspec" / "config.yaml"
GUARD = DEV / "tests" / "consistency" / "test_cla_init_rules_match_config.py"

TARGETS = [GUARD]

_TASKS_RULE = (
    "Give each requirement this change adds or modifies a test task whose test carries a "
    "`requirement: <spec> / <heading>` comment line above it, or a line "
    "`manual: <heading>: <reason>`. Scenarios are examples, not one test each."
)

MUTANTS = [
    (
        "cla-init stops checking config.yml, so a seeded config.yaml hides the user's file",
        SKILL,
        ' && [ ! -e "$ROOT/openspec/config.yml" ]; then',
        "; then",
        [f"{GUARD}::test_the_seed_treats_config_yml_as_existing"],
    ),
    (
        "cla-init loosens the requirement limit, so consumers author under another rule",
        SKILL,
        "as one sentence of 500 characters or fewer",
        "as one sentence of 800 characters or fewer",
        [f"{GUARD}::test_cla_init_seeds_the_block_this_repo_carries"],
    ),
    (
        # One line, no line ending in the anchor: the config has no eol
        # attribute, so a fresh clone may check it out CRLF.
        "this repo's config drops the scenarios-are-examples clause cla-init still seeds",
        CONFIG,
        '`manual: <heading>: <reason>`. Scenarios are examples, not one test each."',
        '`manual: <heading>: <reason>`."',
        [f"{GUARD}::test_cla_init_seeds_the_block_this_repo_carries"],
    ),
    (
        "cla-init stops seeding the unique-heading rule, so a consumer's specs "
        "can name two scenarios at once",
        SKILL,
        '    - "Keep every scenario heading unique within its spec, so `<spec> / <heading>` '
        'names exactly one scenario."',
        "",
        [f"{GUARD}::test_cla_init_seeds_the_block_this_repo_carries"],
    ),
    (
        "cla-init unquotes an item containing ': ', so YAML reads it as a mapping",
        SKILL,
        f'    - "{_TASKS_RULE}"',
        f"    - {_TASKS_RULE}",
        # Only the quoting test: the equality test would kill this one too,
        # which would prove nothing about the quoting check.
        [f"{GUARD}::test_an_item_with_a_colon_is_quoted"],
    ),
    (
        "the seed writes no blank line after the schema",
        SKILL,
        "printf 'schema: spec-driven\\n\\n%s\\n' \"$RULES\"",
        "printf 'schema: spec-driven\\n%s\\n' \"$RULES\"",
        [f"{GUARD}::test_the_seed_creates_a_missing_config"],
    ),
    (
        "the comparison stops ignoring indentation, so every rule reads as outdated",
        SKILL,
        "| sed 's/^[[:space:]]*//')\"",
        "| cat)\"",
        [f"{GUARD}::test_a_config_with_every_rule_is_reported_current"],
    ),
    (
        "the comparison stops stripping CR, so a CRLF config reads as all outdated",
        SKILL,
        "HAVE=\"$(tr -d '\\r' < \"$OLD\"",
        "HAVE=\"$(cat < \"$OLD\"",
        [f"{GUARD}::test_an_outdated_rule_is_listed_and_the_file_left_alone"],
    ),
    (
        "the report stops naming the artifact a missing rule belongs under",
        SKILL,
        "|| printf '%s %s\\n' \"$KEY\" \"${line#    }\"",
        "|| printf '%s\\n' \"${line#    }\"",
        [f"{GUARD}::test_an_outdated_rule_is_listed_and_the_file_left_alone"],
    ),
    (
        "the report appends the shipped block to an existing config",
        SKILL,
        "OLD=\"$CFG\"; [ -e \"$OLD\" ] || OLD=\"$ROOT/openspec/config.yml\"",
        "OLD=\"$CFG\"; [ -e \"$OLD\" ] || OLD=\"$ROOT/openspec/config.yml\"; printf '%s\\n' \"$RULES\" >> \"$OLD\"",
        [f"{GUARD}::test_a_config_with_every_rule_is_reported_current",
         f"{GUARD}::test_an_outdated_rule_is_listed_and_the_file_left_alone"],
    ),
    (
        "the comparison ignores config.yml and reads a config.yaml that is not there",
        SKILL,
        "[ -e \"$OLD\" ] || OLD=\"$ROOT/openspec/config.yml\"",
        "true",
        [f"{GUARD}::test_a_config_yml_is_compared_and_no_config_yaml_is_created"],
    ),
    (
        "a skill restates a spec limit beside its pointer to the rules",
        CHECKLIST,
        "Apply `openspec/config.yaml` `rules.specs` to every requirement",
        "Apply `openspec/config.yaml` `rules.specs` (500 characters or fewer) to every requirement",
        [f"{GUARD}::test_no_skill_carries_a_third_copy_of_the_spec_rules"],
    ),
    (
        "the third-copy scan stops exempting cla-init, whose seed copy it must then find",
        GUARD,
        "if p != _SKILL and any(",
        "if p != _CONFIG and any(",
        [f"{GUARD}::test_no_skill_carries_a_third_copy_of_the_spec_rules"],
    ),
]
