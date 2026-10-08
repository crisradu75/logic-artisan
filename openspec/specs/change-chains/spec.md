# change-chains Specification

## Purpose

What the plugin promises when a batch of changes from one decisions doc is proposed, run and merged without a person in the loop.

## Requirements

### Requirement: Proposing a batch of changes

`/cla:multi-spec [decisions-file]` SHALL turn a decisions file, by default the newest under `cla.io/decisions/`, into a batch of OpenSpec change proposals committed one change at a time, reviewed together and opened as one pull request, without implementing them.

#### Scenario: A decisions file with three decisions

- **WHEN** a user runs `/cla:multi-spec` on a decisions file describing three changes
- **THEN** one pull request opens holding three reviewed change proposals and no implementation

### Requirement: Running a batch of OpenSpec changes

`/cla:multi-pr [change ...]` SHALL run each named change, or every open change when none is named, through `/cla:spec-to-pr` in dependency order, fixing every Critical and Important finding before a change counts as done and recording unfixed Suggestions in `TODO.md` unless the user chose to fix them too.

#### Scenario: A change with only Suggestions left

- **WHEN** a change's review leaves only Suggestions under the default policy
- **THEN** the change counts as done and its Suggestions are recorded in `TODO.md`

#### Scenario: A change later in the order

- **WHEN** one change depends on another in the batch
- **THEN** the dependency runs first, and under the default merge policy it is merged before the dependent starts

### Requirement: Running a batch of small changes

`/cla:multi-lite [doc]` SHALL take every small change a decisions or feedback doc describes, by default the newest under `cla.io/decisions/`, confirm the order and the merge policy once at the start, and run `/cla:lite-pr` on each in dependency order.

#### Scenario: A feedback doc with several small fixes

- **WHEN** a user runs `/cla:multi-lite` on a doc listing several small fixes and confirms the plan
- **THEN** each fix gets its own pull request, in dependency order, with no further question

### Requirement: What a small-change chain merges

`/cla:multi-lite` SHALL merge a pull request only under the merge policy confirmed for that run, and only when its review left no Critical or Important finding open, its full test suite passed on the exact commit being merged with no uncommitted changes, and the host reports it merged rather than queued.

#### Scenario: A fix committed after the tests ran

- **WHEN** a review fix was committed after a candidate's test run
- **THEN** the full suite runs again on that commit before any merge, and a failure leaves the pull request open with its reason

#### Scenario: A queued merge

- **WHEN** the host accepts the merge command but reports the pull request still open or queued
- **THEN** the candidate is not counted as merged and the changes that depend on it are skipped

### Requirement: A failure stops only what depends on it

`/cla:multi-lite` SHALL skip a failed change and every change that depends on it and continue with the rest, `/cla:multi-pr` SHALL stop before any later change when a change fails to open or archive its pull request or leaves the live specs failing validation, and both SHALL report each skipped or stopped change with its reason.

#### Scenario: A failed small change

- **WHEN** one change in a `/cla:multi-lite` chain fails its tests
- **THEN** it and its dependents are skipped with a reason and the independent changes still run

### Requirement: Shared environment state merges first

A change that migrates a shared environment, seeds shared data or provisions shared infrastructure SHALL be merged before the next change in its chain starts, even when nothing depends on its code, and when it cannot be merged every later change SHALL be skipped.

#### Scenario: A migration with no code dependents

- **WHEN** a chain holds a change that applies a database migration and nothing depends on its code
- **THEN** it is merged before the next change starts

### Requirement: Obligations reach the change that owes them

When an earlier change in a `/cla:multi-pr` chain adds a field or behaviour for a later change, the later change SHALL receive it through `/cla:spec-to-pr --inherits`, and its review SHALL answer each one as honoured, violated or not addressed and return no READY verdict while any is not honoured.

#### Scenario: A field the later change ignores

- **WHEN** a later change's artifacts never mention a field an earlier change added for it
- **THEN** its review reports that obligation as not addressed and the verdict is not READY

### Requirement: An unattended chain keeps running

A chain confirmed at its start SHALL keep running without the user until every change is done, skipped or stopped with a reported reason, asking the user only about a blocker it cannot resolve itself.

#### Scenario: Between two changes

- **WHEN** one change finishes and another is still to run
- **THEN** the chain starts the next change without waiting for the user
