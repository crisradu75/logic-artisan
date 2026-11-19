# Proposal

## Why

Review round 1 of the shared shell reading found that a wrapper body still carried the wrapper's own
option words (`-c cp a ../b`), so a guard keyed on the command word missed `bash -c 'cp a ../b'`;
that prose in an unquoted heredoc was read as commands, so commit messages and notes naming
`bash -c` were blocked or asked about; and that a body run in a container or on another host was
read as local. A body too long to read was dropped silently, and the pre-push overrides set in
PowerShell's `$env:` form were not asked about.

## What Changes

- A wrapper body is checked as the command it runs: the wrapper's option words are dropped.
- Heredoc text is data; only an unquoted body's substitutions are read as commands.
- A wrapper behind `docker exec`, `ssh <host>` and the like is not read as local.
- A command whose wrapper bodies the guards cannot read in full asks.
- `$env:ALLOW_PUSH_TO_MAIN=1` and `$env:ALLOW_TAG_REWRITE=1` ask like their shell forms.

## Capabilities

### Modified Capabilities

- `guard-hooks`: the wrapped-command requirement.
- `git-guards`: the pre-push skip requirement.

## Impact

`hooks/_shell_read.py`, the Bash dispatcher, `hooks/_destructive_git_rules.py`, their tests and
mutation batches. No new dependency.
