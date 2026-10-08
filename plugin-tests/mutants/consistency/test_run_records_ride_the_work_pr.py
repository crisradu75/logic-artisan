"""Mutation batch for test_run_records_ride_the_work_pr.py.

Each mutant edits one recipe so a run record or run-notes file lands on the base
branch, a run with nothing open stops saying its notes are uncommitted, a re-run
deletes the notes instead of untracking them, or the notes-only head check stops
comparing the recorded head with the PR's.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_run_records_ride_the_work_pr.py
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEV = Path(__file__).resolve().parents[2]
SKILLS = REPO / ".claude" / "plugins" / "cla" / "skills"
HANDOFF = SKILLS / "spec-to-pr" / "references" / "handoff.md"
LITE_PHASE4 = SKILLS / "multi-lite" / "references" / "phase4-and-log.md"
LITE_BOOT = SKILLS / "multi-lite" / "references" / "bootstrap-and-tracking.md"
LITE_LOOP = SKILLS / "multi-lite" / "references" / "candidate-loop.md"
PR_CLEANUP = SKILLS / "multi-pr" / "references" / "cleanup.md"
GUARD = DEV / "tests" / "consistency" / "test_run_records_ride_the_work_pr.py"

TARGETS = [GUARD]

MUTANTS = [
    (
        "spec-to-pr commits its ledger line even when Ship opened no PR",
        HANDOFF,
        "Do this ONLY when Ship opened a PR",
        "Do this whenever the run ends",
        TARGETS,
    ),
    (
        "multi-lite commits its notes on the base branch again",
        LITE_PHASE4,
        "  git checkout <branch>\n",
        "  git checkout <base-branch>\n",
        TARGETS,
    ),
    (
        "multi-lite stops saying its notes were left uncommitted",
        LITE_PHASE4,
        "leave the file uncommitted and say so",
        "leave the file uncommitted",
        TARGETS,
    ),
    (
        "multi-pr commits its notes on the base branch",
        PR_CLEANUP,
        "`git checkout <branch>`, `git pull`, `python3",
        "`git checkout <base-branch>`, `git pull`, `python3",
        TARGETS,
    ),
    (
        "a multi-lite re-run deletes the committed notes instead of untracking them",
        LITE_BOOT,
        "`git rm --cached -q -- <notes>`",
        "`git rm -q -- <notes>`",
        TARGETS,
    ),
    (
        "the notes-only head check reads the last commit instead of every commit since "
        "the recorded head",
        LITE_LOOP,
        "`git diff --name-only <head_sha> <headRefOid>`",
        "`git log -1 --name-only <headRefOid>`",
        TARGETS,
    ),
]
