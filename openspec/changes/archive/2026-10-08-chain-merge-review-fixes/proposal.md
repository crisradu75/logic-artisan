## Why

A review of the shared chain-merge change found that a `multi-pr` chain resumed after a crash could
merge a pull request whose Critical and Important findings were never fixed: the head was recorded
before the fix steps, and a resume read that head as ready. It also found rules the move to
`skills/_shared/references/chain-merge.md` dropped.

## What Changes

- `multi-pr` writes `status: enforced` once a change's findings are fixed and the live specs
  validate. A resume merges only from that status; without it the findings are lost, so a needed
  change halts the chain and an independent one stays open.
- A resumed change's head is compared with the recorded one before `spec-to-pr` runs again; the
  head is recorded again after every `spec-to-pr` call; a failed commit check in the fix step
  halts or leaves the PR open.
- `multi-pr`'s running-notes row is defined, and its final report lists every merge note and every
  PR left open with its reason.
- Restored: a failed base pull halts the run, `BEHIND`'s explanation, the `git log` check after a
  pull, `ALLOW_PR_MERGE=1` not covering `branch -D`, why the gate runs before the merge-state check,
  and how a hand-built stack lands (now in `spec-to-pr`'s `branch-and-pr-base.md`).

## Impact

- `change-chains`: "Running a batch of OpenSpec changes in dependency order" gains a scenario for a
  resume that cannot show a change's findings were fixed.
