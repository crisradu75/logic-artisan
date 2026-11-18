# Spec Delta

## ADDED Requirements

### Requirement: A rebasing pull of pushed commits asks first

The guard hooks SHALL ask the user before a `git pull` that rebases, by its own option or by the repository's settings, when the commits it would rewrite include one already on a remote-tracking branch, and SHALL stay silent for a pull that merges, one that moves only local commits, and when they cannot check.

#### Scenario: Pulling main into a pushed branch with rebase

- **WHEN** an agent runs `git pull --rebase origin main` on a branch whose commits are on `origin/feat`
- **THEN** the user is asked before it runs

#### Scenario: Pulling a branch's own upstream with rebase

- **WHEN** an agent runs `git pull --rebase` and only unpushed commits would move
- **THEN** no prompt is shown

#### Scenario: A merging pull

- **WHEN** an agent runs `git pull --no-rebase origin main`
- **THEN** no prompt is shown
