# codify-learnings — rules for this repo

## Memory index glob

`~/.claude/projects/C--code-logic-artisan/memory/` — index file `MEMORY.md`, one fact per
sibling `*.md`. On Windows that resolves to
`C:\Users\<user>\.claude\projects\C--code-logic-artisan\memory\`.

There is exactly one such directory for this repo; if a glob ever matches more than one,
prefer the one whose slug matches this repo's path (`C--code-logic-artisan`).

## Verification

A change is not "done" until the gate in `cla.io/project-facts.md` passes. A skipped test has not
run, so treat a skip line as a finding rather than noise.

Earlier incidents from this file: `cla.io/lessons-learned/lessons-learned.md`, "2026-10-08 —
incidents moved out of the overlays by cla-setup".
