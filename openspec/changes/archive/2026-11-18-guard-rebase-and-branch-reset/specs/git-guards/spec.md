# Spec Delta

## ADDED Requirements

### Requirement: A rebase of pushed commits asks first

The guard hooks SHALL ask the user before a `git rebase` that would rewrite a commit already on a remote-tracking branch, and SHALL stay silent for a rebase of local-only commits, for continuing, skipping or aborting a rebase under way, and when they cannot check.

#### Scenario: A rebase of a pushed branch onto main

- **WHEN** an agent runs `git rebase main` on a branch whose commits are on `origin/feat`
- **THEN** the user is asked before it runs

#### Scenario: A rebase of local commits

- **WHEN** an agent runs `git rebase origin/feat` and only unpushed commits would move
- **THEN** no prompt is shown

#### Scenario: Continuing a rebase

- **WHEN** an agent runs `git rebase --continue`
- **THEN** no prompt is shown

### Requirement: A branch reset that would orphan commits asks first

The guard hooks SHALL ask the user before `git switch -C` or `git checkout -B` resets an existing branch holding commits that no other branch, tag, remote-tracking branch or the start point reaches, and SHALL stay silent when the branch is new or nothing would be orphaned.

#### Scenario: A reset of a branch with a commit nowhere else

- **WHEN** an agent runs `git switch -C topic` and `topic` holds a commit no other ref reaches
- **THEN** the user is asked before it runs

#### Scenario: Creating a branch

- **WHEN** an agent runs `git switch -C topic` and no branch `topic` exists
- **THEN** no prompt is shown

### Requirement: A merging branch change over staged work asks first

The guard hooks SHALL ask the user before a `git switch` or `git checkout` with `-m`, `--merge` or `--conflict` while changes are staged, and SHALL stay silent when nothing is staged.

#### Scenario: A merging switch with a staged change

- **WHEN** an agent runs `git switch -m main` with a staged change
- **THEN** the user is asked before it runs

#### Scenario: A merging switch with unstaged changes only

- **WHEN** an agent runs `git switch -m main` and its changes are unstaged
- **THEN** no prompt is shown
