# Proposal

## Why

`conflict-resolution.md` §3 tells an agent to resolve a merge conflict hunk by hunk and to take a
whole side only when the whole file is genuinely one side's. In one session an orchestrator broke
that rule four times while resolving merge conflicts, each time dropping lines the other side had
added. The rule is prose, and it was re-offended, so it moves up a rung to an advisory hook.

## What Changes

- A new warn hook, `warn-lossy-merge-resolution`, runs before a `git commit` or
  `git merge --continue` while a merge is in progress. It compares the result with what the
  merged-in side added since the merge base and, when lines are missing, names the files and up to
  five lost lines each. It never blocks; it is silent with no merge, with nothing lost, and on any
  error.
- A line replaced on purpose is reported too, since the hook cannot read intent; the message says
  to state a deliberate drop in the commit message.
- Wired into the Bash dispatcher as an advisory hook that reads wrapper bodies itself, so its git
  calls run once per command on one shared 4 s deadline. Copilot CLI reaches it through the same
  dispatcher.
- Named limit: it cannot see git commands run inside a wrapper script (`./merge.sh`).

## Capabilities

### Modified Capabilities

- `guard-warnings`: one added requirement.

## Impact

`hooks/warn-lossy-merge-resolution.py`, the Bash dispatcher's lists, `HOOK_WORST_CASE_SECONDS`, the
hook tables in the READMEs and DEVELOPER-GUIDE (17 to 18 guard hooks). No new dependency.
