"""Mutation batch for test_reviewed_change_trigger.py.

Each mutant breaks one side of the review-record contract between multi-spec,
which writes `review.json`, and spec-to-pr's Review, which skips the checklist
on it. A broken side reads fine on its own and either stops the skip firing or,
worse, lets a change skip that multi-spec did not pass.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_reviewed_change_trigger.py
"""

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
DEV = Path(__file__).resolve().parents[2]
SKILLS = PLUGIN / "skills"
SPEC_TO_PR = SKILLS / "spec-to-pr" / "SKILL.md"
REVIEW_GATE = SKILLS / "multi-spec" / "references" / "review-gate.md"
RUN_LOG_SCHEMA = SKILLS / "_shared" / "references" / "run-log-schema.md"
CHECKLIST = SKILLS / "review-change" / "references" / "checklist.md"

TARGETS = [DEV / "tests" / "consistency" / "test_reviewed_change_trigger.py"]

MUTANTS = [
    (
        "multi-spec writes a record only for a change it fixed, so a READY change "
        "is reviewed twice",
        REVIEW_GATE,
        "**Write a review record into every reviewed change, whatever its verdict**",
        "**Write a review record into every change this gate fixed**",
        TARGETS,
    ),
    (
        "multi-spec renames the record file, so spec-to-pr never finds it",
        REVIEW_GATE,
        "as `openspec/changes/<name>/review.json`.",
        "as `openspec/changes/<name>/verdict.json`.",
        TARGETS,
    ),
    (
        "multi-spec renames a field in its example, so the reader's `all_applied` "
        "is never present",
        REVIEW_GATE,
        '{"verdict": "FIX FIRST", "all_applied": true,',
        '{"verdict": "FIX FIRST", "applied": true,',
        TARGETS,
    ),
    (
        "spec-to-pr reads a different file from the one multi-spec writes",
        SPEC_TO_PR,
        "recorded each change's result in `openspec/changes/<change-name>/review.json`",
        "recorded each change's result in `openspec/changes/<change-name>/review.md`",
        TARGETS,
    ),
    (
        "spec-to-pr also skips on RETHINK",
        SPEC_TO_PR,
        "its `verdict` is `READY` or `FIX FIRST`, `all_applied`",
        "its `verdict` is `READY`, `FIX FIRST` or `RETHINK`, `all_applied`",
        TARGETS,
    ),
    (
        "spec-to-pr skips a FIX FIRST change whose fixes were not all applied",
        SPEC_TO_PR,
        "`all_applied` is `true`, and `deferred` is empty.",
        "and `deferred` is empty.",
        TARGETS,
    ),
    (
        "spec-to-pr skips a change with a deferred Critical or Important finding",
        SPEC_TO_PR,
        "`all_applied` is `true`, and `deferred` is empty.",
        "and `all_applied` is `true`.",
        TARGETS,
    ),
    (
        "spec-to-pr skips when the record is missing",
        SPEC_TO_PR,
        "anything else, including a missing or unreadable record, runs the full checklist:",
        "anything else runs the full checklist; a missing record counts as READY:",
        TARGETS,
    ),
    (
        "spec-to-pr stops comparing the artifact digest, so an edit squashed in "
        "after the review skips unseen",
        SPEC_TO_PR,
        " equals the record's `artifacts`",
        " is recorded",
        TARGETS,
    ),
    (
        "spec-to-pr digests the whole directory, record included, so the digest "
        "can never match and every change is reviewed twice",
        SPEC_TO_PR,
        "`git ls-files -s -- openspec/changes/<change-name>/ "
        "':(exclude)openspec/changes/<change-name>/review.json' | git hash-object --stdin`",
        "`git ls-files -s -- openspec/changes/<change-name>/ | git hash-object --stdin`",
        TARGETS,
    ),
    (
        "multi-spec digests a different file set from the one spec-to-pr checks",
        REVIEW_GATE,
        "':(exclude)openspec/changes/<name>/review.json' | git hash-object --stdin`",
        "':(exclude)openspec/changes/<name>/tasks.md' | git hash-object --stdin`",
        TARGETS,
    ),
    (
        "multi-spec digests the working tree instead of the staged fixes",
        REVIEW_GATE,
        "Stage the fixes first, `git add -- openspec/changes/`, because `artifacts` digests the staged files.",
        "Write it before staging anything.",
        TARGETS,
    ),
    (
        "multi-spec's batch-of-one path never reaches the record",
        REVIEW_GATE,
        "Then go to Step 7 with that change's verdict, so it still gets its fixes applied and its review record written.",
        "Then go to Phase 5.",
        TARGETS,
    ),
    (
        "the checklist renames a verdict, so a record's `FIX FIRST` matches nothing "
        "the rubric emits",
        CHECKLIST,
        "**Verdict: READY / FIX FIRST / RETHINK**",
        "**Verdict: READY / FIX-FIRST / RETHINK**",
        TARGETS,
    ),
    (
        "spec-to-pr drops the deferred findings from a full Review",
        SPEC_TO_PR,
        "When a readable record lists `deferred` findings, the full checklist takes each one as a known issue",
        "A readable record's `deferred` findings are informational",
        TARGETS,
    ),
    (
        "the run log stops naming the verdict the skip trusted",
        RUN_LOG_SCHEMA,
        '`reason: "reviewed by multi-spec: <verdict>"`',
        '`reason: "reviewed by multi-spec"`',
        TARGETS,
    ),
]
