# Proposal

## Why

About nineteen shipped skill rules say "stage named paths only; never `git add -A`, never a broad
`git add openspec/`". The harm they guard is real: a broad stage sweeps stray untracked files
(scratch output, a parallel session's change folder, a secret) into a commit. Nothing enforces the
rules today; principle 3 of the foundation decision says a rule that must never bend becomes a
hook.

## What Changes

- Add a best-effort guard hook, `ask-broad-git-add`, to the Bash and PowerShell dispatcher. It asks
  before a broad `git add` (`-A`, `--all`, `.`, `:/`, `*`, a bare `openspec/`, and their spellings)
  only when that add would stage untracked files, and names up to ten of them.
- It stays silent when only tracked files changed, for `-u` and named paths, and whenever it cannot
  check (no git, not a repository, an error or a timeout).
- The dispatcher gains a best-effort tier: a hook that may ask but is skipped, like a warning, when
  the handler budget is spent. The enforcing hooks already use the whole budget.

## Capabilities

### Modified Capabilities

- `git-guards`: add a requirement that a broad `git add` that would stage untracked files asks
  first.

## Impact

The new hook file, the Bash dispatcher's lists, the budget table in `_dispatch_lib.py`, tests and a
mutation batch under `plugin-tests/`, and the guard tables in the plugin README and the developer
guide. Copilot CLI picks the guard up through the same dispatcher. No new dependency.
