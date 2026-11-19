# git-guards Specification

## Purpose

**Serves:** maintainers whose agents run git commands and pushes in a repo that installs the plugin.

When a git command asks first, and when a push to the default branch, or one that deletes or moves a tag on the remote, is refused.

## Requirements

### Requirement: A force-push, hard reset or forced branch delete asks first

The guard hooks SHALL ask the user before a force-push, a hard reset, or a forced branch delete.

#### Scenario: A force-push

- **WHEN** an agent runs `git push --force`
- **THEN** the user is asked before it runs

#### Scenario: A hard reset

- **WHEN** an agent runs `git reset --hard`
- **THEN** the user is asked before it runs

#### Scenario: A forced branch delete

- **WHEN** an agent runs `git branch -D feature/x`
- **THEN** the user is asked before it runs

### Requirement: A pull request merge asks first

The guard hooks SHALL ask the user before `gh pr merge`, and setting `ALLOW_PR_MERGE=1` SHALL drop only this prompt.

#### Scenario: A merge

- **WHEN** an agent runs `gh pr merge 27 --squash`
- **THEN** the user is asked before it runs

#### Scenario: The merge-only override

- **WHEN** `ALLOW_PR_MERGE=1` is set and the same command also holds a force-push
- **THEN** the merge is not asked about and the force-push still is

### Requirement: Discarding uncommitted work asks first

The guard hooks SHALL ask the user before a checkout, restore or clean that would discard uncommitted work.

#### Scenario: A checkout over a modified file

- **WHEN** an agent runs `git checkout <path>` on a path with uncommitted changes
- **THEN** the user is asked before it runs

#### Scenario: A checkout on a clean tree

- **WHEN** an agent runs `git checkout <path>` with no uncommitted changes to lose
- **THEN** no prompt is shown

### Requirement: A stash during an unfinished merge asks first

The guard hooks SHALL ask the user before a `git stash` that saves work while a merge, cherry-pick or revert is in progress.

#### Scenario: A stash in the middle of a merge

- **WHEN** an agent runs `git stash` while a merge is in progress
- **THEN** the user is asked before it runs

#### Scenario: A stash with nothing in progress

- **WHEN** an agent runs `git stash` and no merge, cherry-pick or revert is in progress
- **THEN** no prompt is shown

### Requirement: One override silences every git prompt

Setting `ALLOW_DESTRUCTIVE_GIT=1` SHALL drop every prompt the guard hooks raise before a destructive git command, the pull request merge prompt included.

#### Scenario: The broad override

- **WHEN** `ALLOW_DESTRUCTIVE_GIT=1` is set and an agent runs `git push --force`
- **THEN** the command runs with no prompt

### Requirement: A push that skips the pre-push guard asks first

The guard hooks SHALL ask the user before a `git push` that skips the default-branch `pre-push` guard, by `--no-verify`, a different `core.hooksPath`, or `ALLOW_PUSH_TO_MAIN=1` typed into the command.

#### Scenario: A push with no-verify

- **WHEN** an agent runs `git push --no-verify origin main`
- **THEN** the user is asked before it runs

#### Scenario: An ordinary push

- **WHEN** an agent runs `git push origin feature/x`
- **THEN** no prompt about the pre-push guard is shown

### Requirement: Direct pushes to main are refused

The plugin SHALL ship a git `pre-push` hook that, once copied into a clone's `.git/hooks/`, refuses any push that updates or deletes `main` or `master` on the remote, from any tool, unless `ALLOW_PUSH_TO_MAIN=1` is set.

#### Scenario: Pushing to main

- **WHEN** a push from a clone with the hook installed would update the remote's `main`
- **THEN** git refuses the push and suggests a branch and a pull request

#### Scenario: An emergency override

- **WHEN** the push is run with `ALLOW_PUSH_TO_MAIN=1`
- **THEN** the push goes through

### Requirement: A push to the remote's own default branch is refused

The `pre-push` hook SHALL also refuse a push that updates or deletes the branch the remote names as its default, whatever its name, unless `ALLOW_PUSH_TO_MAIN=1` is set.

#### Scenario: A default branch that is not main

- **WHEN** the remote's default branch is `develop` and a push would update it
- **THEN** git refuses the push

#### Scenario: A remote with no recorded default

- **WHEN** the remote has no recorded default branch and a push would update `develop`
- **THEN** the push goes through, while a push to `main` is still refused

### Requirement: A broad git add that would stage untracked files asks first

The guard hooks SHALL ask the user before a `git add` of the current directory, the repo root or a bare `openspec/` (`-A`, `--all`, `.`, `:/` or `*`) when it would stage untracked files, naming up to ten of them, and SHALL stay silent when it would stage none or cannot check.

#### Scenario: A broad add over an untracked file

- **WHEN** an agent runs `git add -A` and an untracked file `notes.tmp` is in the tree
- **THEN** the user is asked before it runs, and the prompt names `notes.tmp`

#### Scenario: A broad add over tracked changes only

- **WHEN** an agent runs `git add .` and the only changes are to tracked files
- **THEN** no prompt is shown

#### Scenario: An add of named paths

- **WHEN** an agent runs `git add -A src/app.py` or `git add -u`
- **THEN** no prompt is shown

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

### Requirement: A commit message carrying Measured-by none is refused

The guard hooks SHALL refuse a `git commit` whose message holds a `Measured-by: none` trailer, and SHALL stay silent for a line that only mentions it.

#### Scenario: A none trailer

- **WHEN** an agent commits with a `Measured-by: none` trailer
- **THEN** the commit is refused

#### Scenario: A line that mentions the trailer

- **WHEN** a message says "never Measured-by: none" mid-line
- **THEN** no prompt is shown

### Requirement: An empty review-round commit is refused

The guard hooks SHALL refuse `git commit --allow-empty` with a review-round subject, and SHALL only warn on any other `--allow-empty`.

#### Scenario: An empty review-round commit

- **WHEN** an agent runs `git commit --allow-empty -m "fix: review round 2"`
- **THEN** the commit is refused

#### Scenario: Another empty commit

- **WHEN** an agent runs `git commit --allow-empty -m "chore: init"`
- **THEN** a warning is shown and the commit runs

### Requirement: A commit that would add a debug tag asks first

The guard hooks SHALL ask before a `git commit` that would add a line holding a `/cla:diagnose` debug tag, and SHALL stay silent when no such line is added or the check cannot run.

#### Scenario: A staged debug tag

- **WHEN** an agent commits a staged diff that adds a line with a debug tag
- **THEN** the user is asked before it runs

#### Scenario: No tag added

- **WHEN** the staged diff adds no debug tag
- **THEN** no prompt is shown

### Requirement: A push that deletes or moves a tag on the remote is refused

The `pre-push` hook SHALL refuse a push that deletes any tag on the remote or points a tag the remote already has at a different object, naming the `ALLOW_TAG_REWRITE=1` override in its message, SHALL let a push that creates a new tag through, and setting `ALLOW_TAG_REWRITE=1` SHALL lift only this refusal.

#### Scenario: Deleting a tag

- **WHEN** a push from a clone with the hook installed would delete a tag on the remote
- **THEN** git refuses the push and the message names `ALLOW_TAG_REWRITE=1`

#### Scenario: Moving a tag

- **WHEN** a forced push would point a tag the remote already has at another commit or tag object
- **THEN** git refuses the push and the remote tag stays where it was

#### Scenario: A new tag

- **WHEN** a push creates a tag the remote does not have
- **THEN** the push goes through
