"""Mutation batch for test_run_records_ride_the_work_pr.py.

Each mutant edits one recipe so a run record or run-notes file lands on the base
branch, a chain commits notes that are not its own, pushes after its last PR
merged, a run with nothing open stops saying its notes are uncommitted, a re-run
finds the wrong doc's notes or stays on the PR branch after taking them out, or
the head check forgives a move that is not the run's own notes commit.

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
PR_LOOP = SKILLS / "multi-pr" / "references" / "change-loop.md"
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
        "`git checkout <branch>`, `git pull`, `gh pr view",
        "`git checkout <base-branch>`, `git pull`, `gh pr view",
        TARGETS,
    ),
    (
        "multi-lite adds every notes file again, another doc's included",
        LITE_PHASE4,
        "  git add -- <notes>\n",
        "  git add -- cla.io/retro/multi-lite-run-notes-*.md\n",
        TARGETS,
    ),
    (
        "multi-pr adds every notes file again",
        PR_CLEANUP,
        "`git add -- <notes-path>` (this run's file only, never a glob)",
        "`git add -- cla.io/retro/multi-pr-run-notes-*.md`",
        TARGETS,
    ),
    (
        "multi-lite commits without checking the last PR is still open",
        LITE_PHASE4,
        "  gh pr view <pr-number> --json state\n",
        "",
        TARGETS,
    ),
    (
        "multi-lite pushes after the last PR merged, recreating its branch",
        LITE_PHASE4,
        "and never push, which would recreate a deleted branch",
        "and push anyway",
        TARGETS,
    ),
    (
        "multi-pr pushes after the last PR merged, recreating its branch",
        PR_CLEANUP,
        "never push, which would recreate a deleted branch.",
        "push anyway.",
        TARGETS,
    ),
    (
        "multi-lite's commit message is spelled out again beside its definition",
        LITE_PHASE4,
        '  git commit -m "<notes-message>"\n',
        '  git commit -m "chore: multi-lite run notes"\n',
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
        "a multi-lite re-run takes the newest notes commit of any doc",
        LITE_BOOT,
        "`git log --remotes --format='%H %s' --fixed-strings --grep='<notes-message>'`",
        "`git log --remotes -1 --format=%D --grep='^chore: multi-lite run notes'`",
        TARGETS,
    ),
    (
        "a multi-lite re-run accepts a subject that only contains its message",
        LITE_BOOT,
        "take the first line whose subject is exactly `<notes-message>`",
        "take the first line",
        TARGETS,
    ),
    (
        "a multi-lite re-run stays on the PR branch after taking the notes out",
        LITE_BOOT,
        "verify the push, then `git checkout <base-branch>`",
        "verify the push",
        TARGETS,
    ),
    (
        "a multi-pr re-run takes the newest notes commit only",
        PR_LOOP,
        "`git log --remotes --format='%H %s' --grep='^chore: multi-pr run notes '`",
        "`git log --remotes -1 --format=%D --grep='^chore: multi-pr run notes '`",
        TARGETS,
    ),
    (
        "a multi-pr re-run looks up only the newest notes file",
        PR_LOOP,
        "For each `<notes-path>` missing from the working tree, take its newest `%H`",
        "Take the newest `%H`",
        TARGETS,
    ),
    (
        "a multi-pr re-run stays on the PR branch after taking the notes out",
        PR_LOOP,
        "verify the push, then `git checkout <base-branch>`",
        "verify the push",
        TARGETS,
    ),
    (
        "the head check follows renames, so a source file renamed to the notes path passes",
        LITE_LOOP,
        "`git diff --no-renames --name-only <head_sha> <headRefOid>`",
        "`git diff --name-only <head_sha> <headRefOid>`",
        TARGETS,
    ),
    (
        "the head check accepts any notes file, not this run's",
        LITE_LOOP,
        "lists nothing but this run's notes path",
        "lists nothing outside `cla.io/retro/multi-lite-run-notes-*.md`",
        TARGETS,
    ),
    (
        "the head check stops reading commit subjects, so a foreign notes-only commit passes",
        LITE_LOOP,
        ", and every subject `git log --format=%s <head_sha>..<headRefOid>` prints is `<notes-message>`",
        "",
        TARGETS,
    ),
]
