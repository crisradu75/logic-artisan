# Proposal

## Why

About fifteen shipped rules tell the agent to run a list of git commands around a push and compare
the output by eye: that a new branch collides with nothing, that a renamed branch holds no commits
to lose, that a stacked parent is on the remote, that a push reached the remote, and that the
`Measured-by:` trailers parsed. Principle 3 of the foundation decision says a comparison left to
the reader is the step that fails. The harms are lost work (a reused branch) and false claims (a
push or trailer reported as done when it was not).

## What Changes

- Add a shipped, stdlib-only script, `ship_check.py`, with three subcommands: `preflight` (before a
  branch is made), `pushed` (after a push) and `trailers` (before a push). Each exits 0 on a pass, 1
  on a problem and 2 when it could not check, which is never a pass.
- Replace the command lists in the Ship, Revise and Archive references, the lite-pr trailer
  check, and the multi-spec and multi-lite push checks with one call each, keeping each rule, its
  reason and the reaction to each exit code.
- The pull request commit check in Archive (`gh pr view --json commits`) stays prose, so the
  script needs no `gh`.

## Capabilities

### Modified Capabilities

- `change-workflow`: add requirements for the branch preflight, the push check and the trailer
  check.

## Impact

The new script and its tests, seven shipped skill files, the rule ledger, the developer guide's
script table and the changelog. No new dependency.
