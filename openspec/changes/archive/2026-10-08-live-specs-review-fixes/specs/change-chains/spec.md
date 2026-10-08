## ADDED Requirements

### Requirement: Running a batch of OpenSpec changes in dependency order

`/cla:multi-pr [change ...]` SHALL run each named change, or every open change when none is named, through `/cla:spec-to-pr` in dependency order, fixing every Critical and Important finding before a change counts as done and recording unfixed Suggestions in `TODO.md` unless the user chose to fix them too.

#### Scenario: A change with only Suggestions left

- **WHEN** a change's review leaves only Suggestions and the user did not choose to fix them
- **THEN** the change counts as done and its Suggestions are recorded in `TODO.md`

#### Scenario: A change that depends on another

- **WHEN** one change in the batch depends on another
- **THEN** the change it depends on runs first

### Requirement: What an OpenSpec change chain merges

`/cla:multi-pr` SHALL merge a pull request only under the merge policy confirmed at the start of the run, whose default merges each change before a later change that depends on it starts and leaves open the pull request of a change that nothing later needs merged.

#### Scenario: A change later in the order

- **WHEN** one change depends on another in the batch and the run uses the default merge policy
- **THEN** the dependency is merged before the dependent starts

#### Scenario: An independent change

- **WHEN** a change that nothing later depends on, and that moves no shared environment state, is done under the default merge policy
- **THEN** its pull request is left open for the user to merge

### Requirement: A failed OpenSpec change stops the chain

`/cla:multi-pr` SHALL stop before any later change when a change fails to open or archive its pull request or leaves the live specs failing validation, and SHALL report each change in the batch as shipped, halted with its reason, or never attempted.

#### Scenario: A pull request that never opens

- **WHEN** a change in a `/cla:multi-pr` chain fails to open its pull request
- **THEN** no later change starts
- **AND** the report names each change in the batch as shipped, halted with its reason, or never attempted

### Requirement: A later change is held to what an earlier one owes it

When an earlier change in a `/cla:multi-pr` chain adds a field or behaviour for a later change, the later change's review SHALL report each such obligation the later change ignores, and the later change SHALL not count as ready while one is ignored.

#### Scenario: A field the later change ignores

- **WHEN** a later change's artifacts never mention a field an earlier change added for it
- **THEN** its review reports the ignored obligation and the change is not ready

## REMOVED Requirements

### Requirement: Running a batch of OpenSpec changes

**Reason**: Its second scenario relied on a default merge policy no requirement defined, and merging is now its own requirement.

**Migration**: Restated as change-chains / Running a batch of OpenSpec changes in dependency order; merging is change-chains / What an OpenSpec change chain merges.

### Requirement: Running a batch of small changes

**Reason**: change-chains is full; the small-change chain's requirements move to their own capability.

**Migration**: Restated unchanged as small-change-chains / Running a batch of small changes.

### Requirement: What a small-change chain merges

**Reason**: Moved to its own capability, restoring the promises the outcome-level rewrite dropped: findings that cannot be recounted count as open, a pre-confirmed run that names no policy gets the narrower one, and a resumed run never merges an unchecked head.

**Migration**: Restated as small-change-chains / What a small-change chain merges and small-change-chains / A resumed small-change chain never merges unchecked commits.

### Requirement: A failure stops only what depends on it

**Reason**: It joined two opposite behaviours under one heading: a small-change chain skips only the failed change's dependents, while an OpenSpec change chain stops every later change.

**Migration**: Split into change-chains / A failed OpenSpec change stops the chain and small-change-chains / A failed small change skips its dependents.

### Requirement: Obligations reach the change that owes them

**Reason**: It named the internal hand-off between two skills rather than the outcome.

**Migration**: Restated as change-chains / A later change is held to what an earlier one owes it.
