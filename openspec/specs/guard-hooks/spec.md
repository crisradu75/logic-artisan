# guard-hooks Specification

## Purpose

**Serves:** maintainers whose agents run commands in a repo that installs the plugin.

The safety checks the plugin applies to an agent's tool calls in a repo that installs it.

## Requirements

### Requirement: Guard hooks load with the plugin

Loading the plugin SHALL turn on its guard hooks in every session, with no settings change in the repo and no warning at session start.

#### Scenario: A session starts with the plugin installed

- **WHEN** a session starts in a repo with the plugin installed
- **THEN** the guard hooks run on matching tool calls
- **AND** no hook configuration warning is printed

### Requirement: A recursive delete through a link is blocked

The guard hooks SHALL block, with the reason, a recursive force delete whose target is a symbolic link or junction.

#### Scenario: Deleting through a link

- **WHEN** an agent runs `rm -rf` on a path that is a symbolic link to another directory
- **THEN** the command is blocked and the agent is told why

#### Scenario: Deleting an ordinary directory

- **WHEN** an agent runs `rm -rf` on an ordinary directory
- **THEN** the command runs

### Requirement: A cd inside a shell command is blocked

The guard hooks SHALL block, with the reason, a `cd` inside a shell command.

#### Scenario: A command that changes directory

- **WHEN** an agent runs a shell command that holds `cd`
- **THEN** the command is blocked and the agent is told to use absolute paths

### Requirement: A command too large to scan asks first

The Bash and PowerShell dispatcher SHALL ask the user, naming the command's size and the limit, instead of running any guard on a command longer than 500,000 characters, so a scan that outlasts the hook timeout cannot let it through unchecked.

#### Scenario: A command over the limit

- **WHEN** an agent runs a command longer than 500,000 characters
- **THEN** the user is asked before it runs, and no guard scanned it

#### Scenario: A command at the limit

- **WHEN** an agent runs a command of exactly 500,000 characters
- **THEN** the guards scan it as they would a shorter one

### Requirement: A write from a linked worktree into the main clone is blocked

The guard hooks SHALL block, with the reason, a file write made from a linked worktree into the main clone or another worktree inside it, unless `ALLOW_WORKTREE_PATH_ESCAPE=1` is set.

#### Scenario: Writing back into the main clone

- **WHEN** an agent working in a linked worktree writes a file at a path in the main clone
- **THEN** the write is blocked and the agent is told why

#### Scenario: A deliberate escape

- **WHEN** `ALLOW_WORKTREE_PATH_ESCAPE=1` is set
- **THEN** the same write goes through
