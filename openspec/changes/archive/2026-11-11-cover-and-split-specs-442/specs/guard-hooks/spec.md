## ADDED Requirements

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

### Requirement: A write from a linked worktree into the main clone is blocked

The guard hooks SHALL block, with the reason, a file write made from a linked worktree into the main clone or another worktree inside it, unless `ALLOW_WORKTREE_PATH_ESCAPE=1` is set.

#### Scenario: Writing back into the main clone

- **WHEN** an agent working in a linked worktree writes a file at a path in the main clone
- **THEN** the write is blocked and the agent is told why

#### Scenario: A deliberate escape

- **WHEN** `ALLOW_WORKTREE_PATH_ESCAPE=1` is set
- **THEN** the same write goes through

## REMOVED Requirements

### Requirement: Unsafe commands are blocked

**Reason**: Three outcomes in one requirement, against one outcome per requirement.

**Migration**: Replaced by "A recursive delete through a link is blocked", "A cd inside a shell command is blocked" and "A write from a linked worktree into the main clone is blocked".

### Requirement: Destructive git commands ask first

**Reason**: Several outcomes in one requirement, and the spec had no room to split them.

**Migration**: Moved to the new `git-guards` capability as five requirements.

### Requirement: Risky actions warn

**Reason**: Five warnings in one requirement.

**Migration**: Moved to the new `guard-warnings` capability, one requirement each.

### Requirement: Direct pushes to main are refused

**Reason**: The git-push guards form their own capability.

**Migration**: Moved unchanged to `git-guards`.

### Requirement: Copilot CLI enforces session guards

**Reason**: Copilot CLI support forms its own capability.

**Migration**: Moved unchanged to `copilot-cli`.

### Requirement: Copilot hook failures have an explicit policy

**Reason**: Copilot CLI support forms its own capability.

**Migration**: Moved unchanged to `copilot-cli`.
