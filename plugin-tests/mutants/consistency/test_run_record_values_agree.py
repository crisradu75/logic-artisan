"""Mutation batch for test_run_record_values_agree.py.

Each mutant moves ONE side of a pair the test keeps equal — the writer's
`SHAPES` lists in `lib/log_run.py`, or the copies the retro's aggregator holds —
so the kill proves the test reads that pair and not merely that both files
parse. The writer-side mutants also redden `tests/lib/`; `TARGETS` is this one
guard file, so a kill here is attributed to the agreement test.

**DELIBERATELY NOT A MUTANT:** the regexes that read the aggregator's source
(`name == "..."`, `cap_hit = {...}`) each assert they found something, so a
pattern that stops matching fails the test outright rather than passing empty.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_run_record_values_agree.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
LOG_RUN = PLUGIN / "lib" / "log_run.py"
AGG = PLUGIN / "skills" / "spec-to-pr-retro" / "scripts" / "spec_to_pr_aggregate.py"
MIG = DEV / "scripts" / "migrate_run_records.py"
TARGETS = [DEV / "tests" / "consistency" / "test_run_record_values_agree.py"]

MUTANTS = [
    (
        "the writer accepts a size gate the reader counts as drift",
        LOG_RUN,
        'SIZE_GATES = ("small", "large")',
        'SIZE_GATES = ("small", "medium", "large")',
        TARGETS,
    ),
    (
        "the reader stops knowing a verdict the writer accepts",
        AGG,
        'VALID_VERDICTS = {"READY", "FIX FIRST", "RETHINK"}',
        'VALID_VERDICTS = {"READY", "FIX FIRST"}',
        TARGETS,
    ),
    (
        "the reader's agent list loses an id the writer requires",
        AGG,
        '    "pr-test-analyzer", "comment-analyzer", "plugin-dev-skill-reviewer",',
        '    "pr-test-analyzer", "comment-analyzer",',
        TARGETS,
    ),
    (
        "the writer renames a phase the reader matches by name",
        LOG_RUN,
        '                     "Revise", "Archive", "Handoff")',
        '                     "PR-Revise", "Archive", "Handoff")',
        TARGETS,
    ),
    (
        "the writer requires a rounds pair on a phase the cap metrics never read",
        LOG_RUN,
        'ROUNDS_REQUIRED_ON = ("Test", "Revise")',
        'ROUNDS_REQUIRED_ON = ("Test", "Revise", "Ship")',
        TARGETS,
    ),
    (
        "the writer accepts a status the reader's tally does not list",
        LOG_RUN,
        'STATUSES = ("ok", "warn", "skip", "fail")',
        'STATUSES = ("ok", "warn", "skip", "fail", "partial")',
        TARGETS,
    ),
    (
        "the reader ranks the reasons of a status the writer does not require one on",
        AGG,
        '            if status in ("warn", "fail") and phase.get("reason"):',
        '            if status in ("warn", "fail", "skip") and phase.get("reason"):',
        TARGETS,
    ),
    (
        "the migration's placeholder and the reader's copy drift apart",
        MIG,
        'NO_REASON = "reason not recorded (migrated record)"',
        'NO_REASON = "reason not recorded (migrated)"',
        TARGETS,
    ),
]
