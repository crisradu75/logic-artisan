## REMOVED Requirements

### Requirement: A malformed record costs one record, and the loss is counted

**Reason**: Restated at outcome level under a new heading.

**Migration**: See run-ledgers / Retro reports.

### Requirement: An aggregator reads several ledgers in one run

**Reason**: Restated at outcome level under a new heading.

**Migration**: See run-ledgers / Retro reports.

### Requirement: A declined default names the ledger evidence that would reverse it

**Reason**: Describes how the plugin's skills work internally, not an outcome or interface.

**Migration**: None; the rule stays in the skill's own files and tests.

### Requirement: The Revise record counts findings per round

**Reason**: Restated at outcome level under a new heading.

**Migration**: See run-ledgers / The spec-to-pr run record.

### Requirement: A ledger field kept for a deferred decision states when it qualifies and when it lapses

**Reason**: Describes how the plugin's skills work internally, not an outcome or interface.

**Migration**: None; the rule stays in the skill's own files and tests.

## ADDED Requirements

### Requirement: Ledger files

Skills that record their runs SHALL append one JSON object per line to a ledger in the repo's `cla.io/retro/` directory, or in the directory `CLAUDE_RETRO_DIR` names, and a record that is not a single JSON object SHALL be refused, leaving the ledger unchanged.

#### Scenario: A run is recorded

- **WHEN** a skill records a run
- **THEN** the ledger gains exactly one line holding that run's JSON object

#### Scenario: A broken record

- **WHEN** a skill hands the writer something that is not a JSON object
- **THEN** the writer refuses it and the ledger is unchanged

### Requirement: The spec-to-pr run record

Each `/cla:spec-to-pr` run SHALL append one record to `cla.io/retro/spec-to-pr-runs.jsonl` giving its time, change, mode and arguments and, for each phase, its status, the reason for a warning or failure, and the rounds used, with the pull request review phase also giving the Critical and Important findings each round found.

#### Scenario: A run with two pull request review rounds

- **WHEN** a run's pull request review takes two rounds
- **THEN** its record lists both rounds in order with the findings each found

### Requirement: Retro reports

`/cla:spec-to-pr-retro [N]` and `/cla:codify-retro [N]` SHALL summarise the last N runs of their ledger, 10 by default, and propose improvements, reading several ledgers together when given several and naming each one read, and counting a malformed record as lost instead of failing the report.

#### Scenario: One malformed record

- **WHEN** a ledger holds one record with a field of the wrong shape
- **THEN** the report covers every other record and counts the damaged one

#### Scenario: Ledgers from several repos

- **WHEN** the report is given the ledgers of several repos
- **THEN** it summarises their runs together and names every ledger it read
