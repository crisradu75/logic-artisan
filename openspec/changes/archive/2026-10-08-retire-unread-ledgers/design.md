## Context

Trigger: real ambiguity — where a chain's run notes go when no PR is left to carry them, and how a
re-run reads notes that ride a PR branch.

## Decisions

- **Notes ride the last open PR; with none open they stay uncommitted.** Nothing is left to resume
  and a base-branch commit is the direct push the pre-push guard refuses; the next run's commit
  globs them onto its own last open PR. Rejected: committing onto the last PR before it merges —
  it moves a head the merge checks already verified.
- **A re-run untracks the committed notes first** (`git rm --cached`, commit, push on that branch).
  A file tracked only on one branch vanishes when the run checks out the base branch, and an
  untracked copy blocks checking that branch out again. Rejected: seeding a new notes file from
  the branch — same-day re-runs collide on the file name.
- **multi-lite forgives a head move that touches only the notes.** Its own notes commits would
  otherwise read as unreviewed commits and leave a clean PR unmerged on every re-run.
