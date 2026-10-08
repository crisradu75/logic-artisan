## MODIFIED Requirements

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
