"""Mutation batch for test_run_record_examples.py.

The mutants put back into each example the kinds of value a template carries and
a record cannot: the alternatives-as-one-string `mode` the review found, a
placeholder where a count belongs, a `true|false` where a boolean belongs, and a
retired agent name in Revise `agents`. Each is a record the writer refuses, so a
recipe that says "build from the example" would spend its one retry on it.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_run_record_examples.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
SKILLS = DEV.parent / ".claude" / "plugins" / "cla" / "skills"
SCHEMA = SKILLS / "_shared" / "references" / "run-log-schema.md"
STEPS = SKILLS / "codify-learnings" / "references" / "steps.md"
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
        "the spec-to-pr example's Revise names an agent by its dispatch form",
        SCHEMA,
        '     "agents": ["code-reviewer", "silent-failure-hunter"],',
        '     "agents": ["pr-review-toolkit:code-reviewer", "silent-failure-hunter"],',
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
        "the codify example's `trimmed` is a template, not a boolean",
        STEPS,
        '"live_log_entries": 30, "trimmed": false}',
        '"live_log_entries": 30, "trimmed": "true|false"}',
        TARGETS,
    ),
    (
        "the codify example's rung is one the ladder does not have",
        STEPS,
        '"failing_artifact": "CLAUDE.md", "escalated_to": "hook"}',
        '"failing_artifact": "CLAUDE.md", "escalated_to": "doc"}',
        TARGETS,
    ),
]
