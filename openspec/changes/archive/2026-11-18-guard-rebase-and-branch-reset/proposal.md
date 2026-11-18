# Proposal

## Why

The rule-enforcement audit of 2026-11-18 ("Gaps in what is enforced today") names two holes in
`ask-destructive-git`: a plain `git rebase`, which rewrites history, and a branch change that could
lose work. Shipped skills say "never a rebase or force-push" for a chain's pull requests, and a
rebase of pushed commits is exactly what leads to a force-push, whose guarded `--force-with-lease`
form does not ask. `git switch -C` and `git checkout -B` reset an existing branch without a word,
orphaning commits the way a force-delete does, and a merging switch is documented to lose staged
changes.

## What Changes

- `ask-destructive-git` asks before a `git rebase` that would rewrite a commit already on any
  remote-tracking branch. A rebase of local-only commits, one on a dirty tree (git refuses it or
  autostashes) and the actions on a rebase under way (`--continue`, `--abort`, `--skip`, `--quit`)
  stay silent. `git pull --rebase` is out of scope.
- It asks before `git switch -C` / `git checkout -B` over an existing branch whose commits are on no
  other branch, tag, remote-tracking branch or the start point.
- It asks before a merging branch change (`-m`, `--merge`, `--conflict`) while changes are staged.
- The three fail open, and their git calls only spend what the hook's existing probes left of its
  budget, so the enforcing hooks' worst case does not grow.

## Capabilities

### Modified Capabilities

- `git-guards`: three requirements, one per new ask.

## Impact

The hook and its `run_git` helper (an optional timeout), tests and the mutation batch under
`plugin-tests/`, and the guard tables in the plugin README and the developer guide. No new
dependency.
