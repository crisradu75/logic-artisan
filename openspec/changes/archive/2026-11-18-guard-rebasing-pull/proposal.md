# Proposal

## Why

Review of the rebase guard found that `git pull --rebase origin main` on a pushed branch rewrites
its pushed commits with no prompt, because the guard left every rebasing pull out of scope. It also
found that the guard passed command text to git where git could read it as an option; that fix
changes no requirement and is covered by tests.

## What Changes

- `ask-destructive-git` asks before a `git pull` that rebases (by `-r`, `--rebase`, or the
  `branch.<name>.rebase` / `pull.rebase` settings) when the commits it would rewrite include one
  already on a remote-tracking branch, using the rebase guard's probe.
- A pull onto its own upstream, a merging pull and a pull it cannot check stay silent.

## Capabilities

### Modified Capabilities

- `git-guards`: one requirement for a rebasing pull.

## Impact

The hook, its tests and mutation batch, and the guard tables. No new dependency.
