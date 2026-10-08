# change-chains Specification

## Purpose

What the plugin promises when a batch of changes from one decisions doc is proposed, run and merged without a person in the loop.

## Requirements

### Requirement: Proposing a batch of changes

`/cla:multi-spec [decisions-file]` SHALL turn a decisions file, by default the newest under `cla.io/decisions/`, into a batch of OpenSpec change proposals committed one change at a time, reviewed together and opened as one pull request, without implementing them.

#### Scenario: A decisions file with three decisions

- **WHEN** a user runs `/cla:multi-spec` on a decisions file describing three changes
- **THEN** one pull request opens holding three reviewed change proposals and no implementation

### Requirement: Running a batch of OpenSpec changes in dependency order

`/cla:multi-pr [change ...]` SHALL run each named change, or every open change when none is named, through `/cla:spec-to-pr` in dependency order, fixing every Critical and Important finding before a change counts as done and recording unfixed Suggestions in `TODO.md` unless the user chose to fix them too.

#### Scenario: A change with only Suggestions left

- **WHEN** a change's review leaves only Suggestions and the user did not choose to fix them
- **THEN** the change counts as done and its Suggestions are recorded in `TODO.md`

#### Scenario: A change that depends on another

- **WHEN** one change in the batch depends on another
- **THEN** the change it depends on runs first

#### Scenario: Resuming before a change's findings were fixed

- **WHEN** a resumed chain cannot show that a change's Critical and Important findings were fixed, and a later change needs it merged
- **THEN** it is not merged and no later change starts

### Requirement: A failed OpenSpec change stops the chain

`/cla:multi-pr` SHALL stop before any later change when a change fails to open or archive its pull request or leaves the live specs failing validation, and SHALL report each change in the batch as shipped, halted with its reason, or never attempted.

#### Scenario: A pull request that never opens

- **WHEN** a change in a `/cla:multi-pr` chain fails to open its pull request
- **THEN** no later change starts
- **AND** the report names each change in the batch as shipped, halted with its reason, or never attempted

### Requirement: Shared environment state merges first

A change that migrates a shared environment, seeds shared data or provisions shared infrastructure SHALL be merged before the next change in its chain starts, even when nothing depends on its code, and when it cannot be merged every later change SHALL be skipped.

#### Scenario: A migration with no code dependents

- **WHEN** a chain holds a change that applies a database migration and nothing depends on its code
- **THEN** it is merged before the next change starts

### Requirement: A later change is held to what an earlier one owes it

When an earlier change in a `/cla:multi-pr` chain adds a field or behaviour for a later change, the later change's review SHALL report each such obligation the later change ignores, the later change SHALL not count as ready while one is ignored, and a resumed chain that cannot read those obligations SHALL stop before starting the later change.

#### Scenario: A field the later change ignores

- **WHEN** a later change's artifacts never mention a field an earlier change added for it
- **THEN** its review reports the ignored obligation and the change is not ready

#### Scenario: Resuming without the run notes

- **WHEN** a chain is resumed where its run notes are missing and a change still to run comes after another change in the chain
- **THEN** the chain stops before that change and says how to go on

### Requirement: An unattended chain keeps running

A chain confirmed at its start SHALL keep running without the user until every change is done, skipped or stopped with a reported reason, asking the user only about a blocker it cannot resolve itself.

#### Scenario: Between two changes

- **WHEN** one change finishes and another is still to run
- **THEN** the chain starts the next change without waiting for the user

### Requirement: An OpenSpec change chain merges only a later change's prerequisite, on the head it checked

`/cla:multi-pr` SHALL merge a pull request only when the merges were confirmed at the start of the run and a later change needs it merged, and only when its head is the commit its review and full test suite covered and the host reports it merged rather than queued, leaving every other pull request open for the user and stopping the chain when a needed merge cannot happen.

#### Scenario: A change later in the order

- **WHEN** one change depends on another in the batch
- **THEN** the dependency is merged before the dependent starts

#### Scenario: An independent change

- **WHEN** a change that nothing later depends on, and that moves no shared environment state, is done
- **THEN** its pull request is left open for the user to merge

#### Scenario: Commits pushed after review

- **WHEN** a change a later change needs merged has a pull request head other than the one its review and full test suite covered
- **THEN** it is not merged and no later change starts
