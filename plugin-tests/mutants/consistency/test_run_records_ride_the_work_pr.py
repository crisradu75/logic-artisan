"""Mutation batch for test_run_records_ride_the_work_pr.py.

Each mutant edits one recipe so a run record or run-notes file lands on the base
branch, a chain commits notes that are not its own, pushes after its last PR
merged, a run with nothing open stops saying its notes are uncommitted, a re-run
finds the wrong doc's notes or stays on the PR branch after taking them out, a
re-run restores the tip's notes instead of its own write, misses an edit made on
the PR since, or touches another chain's notes, or the head check forgives a move
that is not the run's own notes commit.

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
        "`git log --remotes=origin --format='%H %s' --fixed-strings --grep='<notes-message>'`",
        "`git log --remotes -1 --format=%D --grep='^chore: multi-lite run notes'`",
        TARGETS,
    ),
    (
        "a multi-lite re-run accepts a subject that only contains its message",
        LITE_BOOT,
        "the write is the first line whose subject is exactly `<notes-message>`",
        "the write is the first line",
        TARGETS,
    ),
    (
        "a multi-lite re-run stays on the PR branch after taking the notes out",
        LITE_BOOT,
        "Then `git checkout <base-branch>` and restore: ",
        "Then restore: ",
        TARGETS,
    ),
    (
        "a multi-pr re-run takes the newest notes commit only",
        PR_LOOP,
        "`git log --remotes=origin --format='%H %s' --grep='^chore: multi-pr run notes '`",
        "`git log --remotes -1 --format=%D --grep='^chore: multi-pr run notes '`",
        TARGETS,
    ),
    (
        "a multi-pr re-run looks up only the newest notes file",
        PR_LOOP,
        "For each `<notes-path>` missing from the working tree, its write is the newest `%H`",
        "Its write is the newest `%H`",
        TARGETS,
    ),
    (
        "a multi-pr re-run stays on the PR branch after taking the notes out",
        PR_LOOP,
        "Then `git checkout <base-branch>` and restore: ",
        "Then restore: ",
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
    (
        "a multi-lite re-run restores the tip's notes again (B1: a forged row passes)",
        LITE_BOOT,
        " and restore: `git show <sha>:<notes> > <notes>`.",
        ".",
        TARGETS,
    ),
    (
        "a multi-pr re-run restores the tip's notes again",
        PR_LOOP,
        " and restore: `git show <sha>:<notes-path> > <notes-path>`, which drops",
        ", which keeps",
        TARGETS,
    ),
    (
        "a multi-lite re-run takes the newest subject match, which may be a removal or an edit",
        LITE_BOOT,
        " and whose `git show --name-status --format= <sha>` prints one line, `A` and the notes path `<notes>`",
        "",
        TARGETS,
    ),
    (
        "a multi-lite re-run reads writes from any remote, a contributor's fork included",
        LITE_BOOT,
        "`git log --remotes=origin --format='%H %s' --fixed-strings",
        "`git log --remotes --format='%H %s' --fixed-strings",
        TARGETS,
    ),
    (
        "a multi-pr re-run reads writes from any remote",
        PR_LOOP,
        "`git log --remotes=origin --format='%H %s' --grep=",
        "`git log --remotes --format='%H %s' --grep=",
        TARGETS,
    ),
    (
        "the multi-lite edit check misses a commit that modifies the notes",
        LITE_BOOT,
        "`git log --format=%H --diff-filter=AM <sha>..origin/<branch> -- <notes>`",
        "`git log --format=%H --diff-filter=A <sha>..origin/<branch> -- <notes>`",
        TARGETS,
    ),
    (
        "the multi-lite edit check flags the re-run's own take-back-out, so an interrupted re-run trusts nothing",
        LITE_BOOT,
        "`git log --format=%H --diff-filter=AM <sha>..origin/<branch> -- <notes>`",
        "`git log --format=%H <sha>..origin/<branch> -- <notes>`",
        TARGETS,
    ),
    (
        "the multi-pr edit check misses a commit that modifies the notes",
        PR_LOOP,
        "`git log --format=%H --diff-filter=AM <sha>..origin/<branch> -- <notes-path>`",
        "`git log --format=%H --diff-filter=A <sha>..origin/<branch> -- <notes-path>`",
        TARGETS,
    ),
    (
        "multi-lite keeps trusting recorded heads when the notes were edited on the PR",
        LITE_BOOT,
        "blank every row's `head_sha`, `review` and `merge_commit`, so step 2",
        "keep the restored rows, so step 2",
        TARGETS,
    ),
    (
        "a multi-pr re-run takes another chain's notes out of its PR",
        PR_LOOP,
        " Go on only when `git show <sha>:<notes-path>` names a change of this run's sequence under `## Sequence`; never touch another chain's notes.",
        "",
        TARGETS,
    ),
    (
        "a multi-lite take-back-out pushes after a failed pull or a merged PR",
        LITE_BOOT,
        "only if the pull succeeded, the state is `OPEN` and `git ls-files -- <notes>` prints the path: ",
        "",
        TARGETS,
    ),
    (
        "a multi-pr take-back-out pushes after a failed pull or a merged PR",
        PR_LOOP,
        "only if the pull succeeded, the state is `OPEN` and `git ls-files -- <notes-path>` prints the path: ",
        "",
        TARGETS,
    ),
    (
        "the head check runs with no recorded head",
        LITE_LOOP,
        "**`OPEN`, `head_sha` is set but is not `headRefOid`",
        "**`OPEN`, `head_sha` is not `headRefOid`",
        TARGETS,
    ),
    (
        "the head check passes when one of its commands fails",
        LITE_LOOP,
        " A command that fails means this arm does not match.",
        "",
        TARGETS,
    ),
    (
        "the notes path in a commit subject may be spelled any way",
        LITE_BOOT,
        "exactly, the path repo-relative with forward slashes, on every commit",
        "exactly, on every commit",
        TARGETS,
    ),
]
