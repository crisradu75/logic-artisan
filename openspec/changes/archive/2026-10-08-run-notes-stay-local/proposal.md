## Why

The chains' run notes rode the last open pull request (`retire-unread-ledgers`, then
`harden-run-notes-drop-codify-ledger`). Each review added machinery to make that safe — a fixed
commit message, a lookup by it, a take-back-out commit, a restore from the run's own write, an edit
check, a head-move exemption for notes-only commits — and the result still trusted anyone with push
access to the branch. The owner decided on 2026-10-08 that the notes are local working state
(`cla.io/decisions/retro-and-learning-loop-simplification-2026-10-08.md`, D10).

## What Changes

- `multi-lite` and `multi-pr` never add, commit or push their run notes; every step that did, and
  the re-run machinery that took them back out and restored them, is deleted.
- A `multi-lite` resume merges only the head its local notes recorded; with no notes it falls back
  to GitHub state, where it finds no recorded head and so merges nothing. The notes-only head-move
  exemption is gone.
- `multi-pr`'s historical timing reads only this machine's notes.
- `cla-init` adds `cla.io/retro/*-run-notes-*.md` to a repo's `.gitignore` when the line is
  absent. This repo's `.gitignore` gets the same line; notes files it already tracks stay tracked.

## Impact

- `run-ledgers`: the ride-the-PR notes requirement replaced by one saying the notes stay local.
  `small-change-chains`: the resume requirement rewritten without the notes exemption.
  `repo-context`: cla-init's setup requirement gains the ignore line.
- Lost: resuming on another machine uses the GitHub fallback (multi-lite leaves every open PR it
  finds that way unmerged), and multi-pr's timing estimates are per machine.
