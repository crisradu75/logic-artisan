"""Mutation batch for test_run_record_examples.py.

The mutants put back into each example the kinds of value a template carries and
a record cannot: the alternatives-as-one-string `mode` the review found, a flag
carrying its value, and a Test phase without its rounds pair. Each is a record
the writer refuses, so a recipe that says "build from the example" would spend
its one retry on it. The next two leave a field out of the example, or put back
one the record dropped: a field the example lacks is one no run copies, and one
it keeps is one every run writes for nobody. The last drops the count at the
diagnose escalation, which leaves Handoff to rebuild it from memory.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_run_record_examples.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
SKILLS = DEV.parent / ".claude" / "plugins" / "cla" / "skills"
SCHEMA = SKILLS / "_shared" / "references" / "run-log-schema.md"
SPEC_TO_PR = SKILLS / "spec-to-pr" / "SKILL.md"
TARGETS = [DEV / "tests" / "consistency" / "test_run_record_examples.py"]

MUTANTS = [
    (
        "the spec-to-pr example's `mode` lists the alternatives again",
        SCHEMA,
        '  "mode": "description",',
        '  "mode": "description|explore-result|existing-change",',
        TARGETS,
    ),
    (
        "the spec-to-pr example's flag carries its value",
        SCHEMA,
        '  "flags": ["--inherits", "--pr-rounds"],',
        '  "flags": ["--inherits", "--pr-rounds 1"],',
        TARGETS,
    ),
    (
        "the spec-to-pr example's Test loses its rounds pair",
        SCHEMA,
        '    {"name": "Test",      "status": "warn", "rounds_used": 2, "rounds_cap": 3,',
        '    {"name": "Test",      "status": "warn",',
        TARGETS,
    ),
    (
        "the spec-to-pr example leaves out the diagnose count",
        SCHEMA,
        '  "escalated_to_diagnose": 0,\n',
        "",
        TARGETS,
    ),
    (
        "the spec-to-pr example carries a field the record dropped",
        SCHEMA,
        '  "escalated_to_diagnose": 0,\n',
        '  "escalated_to_diagnose": 0,\n  "deferred_to_todo": 0,\n',
        TARGETS,
    ),
    (
        "the escalation to diagnose no longer counts itself",
        SPEC_TO_PR,
        ", and add one to the run's `escalated_to_diagnose` count now, so Handoff reads it rather "
        "than recalling it.**",
        ".**",
        TARGETS,
    ),
]
