## Why

Review of `revise-defaults-from-ledger` found its Handoff nudge requirement names only a warning,
while the nudge has counted a Revise that ended at its cap `fail` since that change.

## What Changes

- **Revise**: a last allowed round that committed fixes ends `ok`, and Handoff says those fixes
  were not reviewed again; `warn` at the cap only for Critical/Important left open.
- **`comment-analyzer`**: back to the pre-change bar (a substantial prose block, or a comment
  asserting a load-bearing invariant), never when no comment, docstring or `.md` hunk changed.
- **Round ≥ 2 on a resume**: the pre-fix SHA is the parent of the previous `fix: review round`
  commit; the sibling question is skipped on the empty-diff fallback too.
- **Nudge, retro and spec** name `fail` alongside `warn`.

## Impact

- `run-ledgers`: one requirement removed and restated under a new heading.
