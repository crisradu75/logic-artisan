## ADDED Requirements

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

Setting `ALLOW_DESTRUCTIVE_GIT=1` SHALL drop every prompt the guard hooks raise before a destructive git command.

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
