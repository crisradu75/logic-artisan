"""Mutation batch for test_run_record_values_agree.py.

Each mutant moves ONE side of a pair the test keeps equal — the writer's
`SHAPES` lists in `lib/log_run.py`, or the copies the retro's aggregator holds —
so the kill proves the test reads that pair and not merely that both files
parse. The writer-side mutants also redden `tests/lib/`; `TARGETS` is this one
guard file, so a kill here is attributed to the agreement test.

The test imports the aggregator's constants rather than reading its source with
regexes, so there is no "pattern stopped matching" branch left to mutate.

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
        "the reader's cap metrics stop counting a phase that must carry the pair",
        AGG,
        'CAPPED_PHASES = ("Review", "Test", "Revise")',
        'CAPPED_PHASES = ("Review", "Revise")',
        TARGETS,
    ),
    (
        "the nudge reads a phase whose rounds pair is optional",
        AGG,
        'NUDGE_PHASES = ("Revise", "Test")',
        'NUDGE_PHASES = ("Revise", "Test", "Review")',
        TARGETS,
    ),
    (
        "the reader's findings phase is a name the writer refuses",
        AGG,
        'FINDINGS_PHASE = "Revise"',
        'FINDINGS_PHASE = "PR-Revise"',
        TARGETS,
    ),
    (
        "the reader ranks the reasons of a status the writer does not require one on",
        AGG,
        'REASON_STATUSES = ("warn", "fail")',
        'REASON_STATUSES = ("warn", "fail", "skip")',
        TARGETS,
    ),
    (
        "the writer requires a reason on a status the reader does not read one from",
        LOG_RUN,
        '    if status in ("warn", "fail") and "reason" not in phase:',
        '    if status in ("warn", "fail", "skip") and "reason" not in phase:',
        TARGETS,
    ),
    (
        "the migration's placeholder and the reader's copy drift apart",
        MIG,
        'NO_REASON = "reason not recorded (migrated record)"',
        'NO_REASON = "reason not recorded (migrated)"',
        TARGETS,
    ),
    (
        "the residue rule names a phase the cap metrics do not count",
        AGG,
        'RESIDUE_PHASES = ("Revise",)',
        'RESIDUE_PHASES = ("Revise", "Ship")',
        TARGETS,
    ),
]
