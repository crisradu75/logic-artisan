"""Mutation batch for test_run_record_examples.py.

The mutants put back into each example the kinds of value a template carries and
a record cannot: the alternatives-as-one-string `mode` the review found, a
placeholder where a count belongs, a retired agent name in Revise `agents`, and,
in the codify example, a rung from the retired artifact-type list and a re-offense
keyed by slug instead of artifact. Each is a record the writer refuses, so a
recipe that says "build from the example" would spend its one retry on it.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_run_record_examples.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
SKILLS = DEV.parent / ".claude" / "plugins" / "cla" / "skills"
SCHEMA = SKILLS / "_shared" / "references" / "run-log-schema.md"
CODIFY = SKILLS / "codify-learnings" / "SKILL.md"
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
        "the codify example's rung is an artifact type, not a rung",
        CODIFY,
        '"target": "hooks/block-cd-in-bash.py", "rung": "hook"}',
        '"target": "hooks/block-cd-in-bash.py", "rung": "skill_md"}',
        TARGETS,
    ),
    (
        "the codify example keys its re-offense by slug again",
        CODIFY,
        '[{"artifact": "CLAUDE.md", "escalated_to": "hook"}]',
        '[{"lesson": "stale-port", "escalated_to": "hook"}]',
        TARGETS,
    ),
]
