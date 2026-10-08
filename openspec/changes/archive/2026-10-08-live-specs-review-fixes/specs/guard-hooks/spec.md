## MODIFIED Requirements

### Requirement: Unsafe commands are blocked

The guard hooks SHALL block, with the reason, a recursive force delete whose target is a symbolic link or junction, a `cd` inside a shell command, and a file write made from a linked worktree into the main clone or another worktree inside it unless `ALLOW_WORKTREE_PATH_ESCAPE=1` is set.

#### Scenario: Deleting through a link

- **WHEN** an agent runs `rm -rf` on a path that is a symbolic link to another directory
- **THEN** the command is blocked and the agent is told why

#### Scenario: Deleting an ordinary directory

- **WHEN** an agent runs `rm -rf` on an ordinary directory
- **THEN** the command runs

#### Scenario: Writing back into the main clone

- **WHEN** an agent working in a linked worktree writes a file at a path in the main clone
- **THEN** the write is blocked and the agent is told why

### Requirement: Destructive git commands ask first

The guard hooks SHALL ask the user before a force-push, a hard reset, a forced branch delete, a pull request merge, or a checkout, restore or clean that would discard uncommitted work, and SHALL drop only the merge prompt when `ALLOW_PR_MERGE=1` is set and every one of these prompts when `ALLOW_DESTRUCTIVE_GIT=1` is set.

#### Scenario: A force-push

- **WHEN** an agent runs `git push --force`
- **THEN** the user is asked before it runs

#### Scenario: A checkout on a clean tree

- **WHEN** an agent runs `git checkout <path>` with no uncommitted changes to lose
- **THEN** no prompt is shown

## ADDED Requirements

### Requirement: Risky actions warn

The guard hooks SHALL warn, without blocking, when a write replaces a tracked file with a much shorter one, `gh pr merge --delete-branch` would delete a branch that other open pull requests are based on, a commit may pick up a stray scratch file in the repo root, a Python or shell comment carries a date, or a heredoc holds an escape the shell would change.

#### Scenario: A file is rewritten much shorter

- **WHEN** an agent writes a tracked file with far less content than it had
- **THEN** the write goes through with a warning asking what was dropped

#### Scenario: Merging the base of a stacked pull request

- **WHEN** an agent runs `gh pr merge --delete-branch` on a pull request whose branch another open pull request is based on
- **THEN** the merge goes ahead with a warning that the other pull request will be closed

## REMOVED Requirements

### Requirement: Risky edits warn

**Reason**: Its stacked-merge trigger was worded as any merge into a shared base, while the warning fires only on `gh pr merge --delete-branch`, and the heading named edits where two triggers are commands.

**Migration**: Restated as guard-hooks / Risky actions warn.
