## Why

Review of `harden-run-notes-drop-codify-ledger` showed a forged notes row still passes: anyone who
can push adds a notes-only commit on the carrying branch rewriting another candidate's row
(`review: clean`, an unreviewed `head_sha`), and the re-run's take-back-out restored that tip
content. The resume requirement also promised "the run's own" notes commits, which nothing can
authenticate (`cla.io/decisions/retro-and-learning-loop-simplification-2026-10-08.md`, D10).

## What Changes

- Both chains restore earlier notes from the commit that added them, never from a branch tip.
- A `multi-lite` re-run whose notes were edited on the PR after that commit takes no recorded head
  from them, so no open PR merges on them; `multi-pr` drops the edit and reports it.
- `multi-pr` takes back out only notes naming a change of its own sequence; a failed pull or a PR
  no longer open pushes nothing.

## Impact

- `small-change-chains`: the resume requirement rewritten under a new heading to say what the
  check can know: commits changing nothing but the notes file, and no head from edited notes.
