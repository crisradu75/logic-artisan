# Proposal

## Why

About 25 shipped rules in the two chain skills, `/cla:multi-pr` and `/cla:multi-lite`, ask the
agent to compare values by eye before it merges or resumes a pull request nobody is watching: the
head the run notes recorded against the local checkout, the remote branch and the pull request; a
clean tree; the pull request's state; whether each dependency merged. Principle 3 of the
foundation decision says a comparison left to the reader is the step that fails, and here a missed
one merges commits nobody tested or reviewed (audit `rule-enforcement-2026-11-18`, check 2).

## What Changes

- Add a shipped, stdlib-only script, `chain_check.py`, with five subcommands for the moments the
  prose checks: `before-merge`, `after-merge`, `fix-pushed`, `resume` and `deps`. Each reads the
  pull request number, branch and recorded head from the chain's own run-notes row, as the run
  notes already record them, and exits 0 on a pass, 1 on a problem with the reason the chain
  writes, and 2 when it could not check, which is never a pass. It calls `gh`, which the chains
  already require.
- Replace the by-eye comparisons in the shared chain-merge reference ("Record the head", the
  pre-merge checks, the merge confirmation), `multi-lite`'s candidate loop (steps 2, 3 and 7) and
  `multi-pr`'s change loop (steps 1, 4 and 5) with one call each, keeping each rule, its reason and
  what the agent does on exit 1 and exit 2.
- No new run-notes field: the rows already carry `branch`, `pr_number`, `head_sha`, `status` and
  `merge_commit`.

## Capabilities

### Modified Capabilities

- `change-chains`: add requirements for the pre-merge check, the merge confirmation, the fix check
  and the resume check.
- `small-change-chains`: add a requirement for the dependency check.

## Impact

The new script and its tests, five shipped skill files plus the two skills' reports, the rule
ledger, the developer guide's script table, the changelog and `TODO.md`. No new dependency.
