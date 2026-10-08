# guard-hooks Specification

## Purpose

The safety checks the plugin applies to an agent's tool calls and to git pushes in a repo that installs it.

## Requirements

### Requirement: Guard hooks load with the plugin

Loading the plugin SHALL turn on its guard hooks in every session, with no settings change in the repo and no warning at session start.

#### Scenario: A session starts with the plugin installed

- **WHEN** a session starts in a repo with the plugin installed
- **THEN** the guard hooks run on matching tool calls
- **AND** no hook configuration warning is printed

### Requirement: Unsafe commands are blocked

The guard hooks SHALL block, with the reason, a recursive force delete whose target is a symbolic link or junction, a file write from inside a linked worktree to a path outside it, and a `cd` inside a shell command.

#### Scenario: Deleting through a link

- **WHEN** an agent runs `rm -rf` on a path that is a symbolic link to another directory
- **THEN** the command is blocked and the agent is told why

#### Scenario: Deleting an ordinary directory

- **WHEN** an agent runs `rm -rf` on an ordinary directory
- **THEN** the command runs

### Requirement: Destructive git commands ask first

The guard hooks SHALL ask the user before a force-push, a hard reset, a forced branch delete, a pull request merge, or a checkout, restore or clean that would discard uncommitted work, and setting `ALLOW_PR_MERGE=1` SHALL drop only the merge prompt.

#### Scenario: A force-push

- **WHEN** an agent runs `git push --force`
- **THEN** the user is asked before it runs

#### Scenario: A checkout on a clean tree

- **WHEN** an agent runs `git checkout <path>` with no uncommitted changes to lose
- **THEN** no prompt is shown

### Requirement: Risky edits warn

The guard hooks SHALL warn, without blocking, when a write replaces a tracked file with a much shorter one, a merge targets a branch that other open pull requests are based on, a scratch file is left in the repo root, a comment carries a date, or a heredoc holds an escape the shell would change.

#### Scenario: A file is rewritten much shorter

- **WHEN** an agent writes a tracked file with far less content than it had
- **THEN** the write goes through with a warning asking what was dropped

### Requirement: Direct pushes to main are refused

The plugin SHALL ship a git `pre-push` hook that, once copied into a clone's `.git/hooks/`, refuses any push that updates or deletes `main` or `master` on the remote, from any tool, unless `ALLOW_PUSH_TO_MAIN=1` is set.

#### Scenario: Pushing to main

- **WHEN** a push from a clone with the hook installed would update the remote's `main`
- **THEN** git refuses the push and suggests a branch and a pull request

#### Scenario: An emergency override

- **WHEN** the push is run with `ALLOW_PUSH_TO_MAIN=1`
- **THEN** the push goes through
