# Proposal

## Why

A project review found that the git guards read only the text a shell sees outside quotes. A
force-push, hard reset or forced branch delete handed to another shell inside quotes
(`bash -c "..."`, `sh -c`, `eval "..."`, `pwsh -Command`, `cmd /c`) ran with no prompt, and so did one
whose git subcommand came from a variable (`X=push; git $X -f origin x`). Each was measured allowed
while its bare form asked.

## What Changes

- `ask-destructive-git` reads the body of a shell wrapper as part of the command, up to three levels
  deep, so a wrapped command reaches the decision its bare form reaches.
- A git subcommand, or a push, reset or branch option, that a variable assigned a literal in the same
  command supplies is read as that literal. One that comes from an expansion the guard cannot resolve
  asks.
- Harmless wrapped commands (`bash -c "git status"`, `eval "$(ssh-agent)"`) stay silent.
- Not in the specs, because no user sees them: the dispatchers measure the time spent before they
  start from a stamp the interpreter probe sets; the Copilot adapter reads a flag rather than message
  words to tell a guard that did not run; the two dispatchers share one copy of the ask reader.

## Capabilities

### Modified Capabilities

- `git-guards`: two requirements, for wrapped commands and for expanded subcommands and flags.

## Impact

The hook, the shared dispatch library, both dispatchers, the Copilot adapter, the interpreter probe,
their tests and mutation batches. No new dependency.
