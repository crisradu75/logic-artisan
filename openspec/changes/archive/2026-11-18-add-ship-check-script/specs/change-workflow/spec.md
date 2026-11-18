# Spec Delta

## ADDED Requirements

### Requirement: A new branch is checked for collisions before it is made

Before a change's branch is made, the ship check's `preflight` SHALL exit 1 when a branch of that name exists locally, as a remote-tracking ref or on the remote, when a branch to be renamed holds commits the base does not, or when a stacked parent has no upstream on the remote, and SHALL exit 2, never 0, when it cannot ask the remote.

#### Scenario: The branch is already on the remote

- **WHEN** `preflight` runs for `feature/x` and the remote already has a `feature/x` branch
- **THEN** it exits 1 and names the remote branch, and no branch is created

#### Scenario: The remote does not answer

- **WHEN** `preflight` runs and the remote cannot be reached
- **THEN** it exits 2, and the branch is not created on an unanswered question

#### Scenario: A stacked parent that was never pushed

- **WHEN** `preflight` runs with `--pr-base feature/parent` and that branch has no upstream
- **THEN** it exits 1 and names the missing upstream

### Requirement: A push is verified against the remote

After a push, the ship check's `pushed` SHALL exit 0 only when the checked-out branch is the one named, its head equals that branch's head on the remote, and its upstream is set to the same commit, and SHALL print `push not verified` on its first line otherwise.

#### Scenario: The commit did not reach the remote

- **WHEN** `pushed` runs after a push that left the remote branch behind the local head
- **THEN** it exits 1 and its first line says `push not verified`

#### Scenario: The remote does not answer

- **WHEN** `pushed` runs and the remote cannot be reached
- **THEN** it exits 2 and its first line says `push not verified`

### Requirement: Measurement trailers are checked before a push

Before a push, the ship check's `trailers` SHALL exit 1 when the number of `Measured-by:` lines in the commit message differs from the number of `Measured-by` trailers git parses from it, and SHALL exit 0 when the two agree, including when both are zero.

#### Scenario: A blank line splits the trailer block

- **WHEN** a commit's two `Measured-by:` lines are separated from its attribution lines by a blank line
- **THEN** `trailers` exits 1

#### Scenario: A change with no measurement

- **WHEN** a commit message has no `Measured-by:` line
- **THEN** `trailers` exits 0
