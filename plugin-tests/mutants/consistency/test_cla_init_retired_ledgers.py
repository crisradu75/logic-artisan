"""Mutation batch for test_cla_init_retired_ledgers.py.

Each mutant edits cla-init's retired-ledger block so it lists the wrong files,
deletes what it should only list, or offers a live ledger for deletion.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_cla_init_retired_ledgers.py
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEV = Path(__file__).resolve().parents[2]
SKILL = REPO / ".claude" / "plugins" / "cla" / "skills" / "cla-init" / "SKILL.md"
GUARD = DEV / "tests" / "consistency" / "test_cla_init_retired_ledgers.py"

TARGETS = [GUARD]

_LIST_HEAD = "for f in codify-runs commit-provenance right-model-runs multi-pr-runs multi-spec-runs \\"
_ECHO = '  if [ -e "$ROOT/cla.io/retro/$f.jsonl" ]; then echo "retired ledger: cla.io/retro/$f.jsonl"; fi'

MUTANTS = [
    (
        "a retired ledger drops off the list, so a repo keeps it unreported",
        SKILL,
        _LIST_HEAD,
        "for f in commit-provenance right-model-runs multi-pr-runs multi-spec-runs \\",
        TARGETS,
    ),
    (
        "the live ledger is offered for deletion",
        SKILL,
        _LIST_HEAD,
        "for f in spec-to-pr-runs codify-runs commit-provenance right-model-runs multi-pr-runs "
        "multi-spec-runs \\",
        TARGETS,
    ),
    (
        "the block deletes what it lists, before anyone said yes",
        SKILL,
        _ECHO,
        '  if [ -e "$ROOT/cla.io/retro/$f.jsonl" ]; then echo "retired ledger: cla.io/retro/$f.jsonl"; '
        'rm -- "$ROOT/cla.io/retro/$f.jsonl"; fi',
        TARGETS,
    ),
    (
        "every name on the list is printed, present or not",
        SKILL,
        _ECHO,
        '  echo "retired ledger: cla.io/retro/$f.jsonl"',
        TARGETS,
    ),
]
