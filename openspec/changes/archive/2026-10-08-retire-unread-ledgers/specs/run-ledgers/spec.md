## MODIFIED Requirements

### Requirement: The spec-to-pr run record

Each `/cla:spec-to-pr` run SHALL append one record to `cla.io/retro/spec-to-pr-runs.jsonl` giving its time, change and mode, the flags it was invoked with, how many times it escalated to `/cla:diagnose`, and, for each phase, its status, the reason for a warning or failure, and the rounds used, with the pull request review phase also giving the Critical and Important findings each round found.

#### Scenario: A run with two pull request review rounds

- **WHEN** a run's pull request review takes two rounds
- **THEN** its record lists both rounds in order with the findings each found

#### Scenario: A run invoked with flags

- **WHEN** a run is invoked with `--inherits` and `--pr-rounds 1`
- **THEN** its record lists both flag names, without their values

## REMOVED Requirements

### Requirement: Run records are checked when written

**Reason**: Rewritten as "Only checked run records are written": the writer now also refuses a ledger with no record shape, which this requirement's scenario said it accepted.
**Migration**: A skill writing any ledger other than the two gets a refusal line and finishes its run; `/cla:cla-init` offers to delete the retired files.

## ADDED Requirements

### Requirement: Only checked run records are written

The writer SHALL append only to the spec-to-pr and codify-learnings ledgers, refusing a record for any other ledger or one whose fields or field values do not match that ledger's record shape, printing one line that names the ledgers it accepts or every field that does not match and leaving the ledger unchanged, and a skill whose record is refused SHALL correct it and try once more, then finish its run whether or not the record was written.

#### Scenario: Phases written as an object

- **WHEN** a spec-to-pr record gives its phases as an object instead of a list
- **THEN** the writer refuses it with a line naming `phases`, and the ledger is unchanged

#### Scenario: Any other ledger

- **WHEN** a skill writes to a ledger other than those two
- **THEN** the writer refuses it with a line naming the two it accepts, and writes nothing

#### Scenario: A record refused twice

- **WHEN** a skill's corrected record is refused again
- **THEN** the skill reports that the record was not written and its run still finishes

### Requirement: Summarising flag use and diagnose escalations

`/cla:spec-to-pr-retro` SHALL report, over the summarised runs whose records carry them, how many runs used each flag, and how many runs escalated to `/cla:diagnose` and how many times in all.

#### Scenario: Flags across runs

- **WHEN** three summarised runs record their flags, two of them `--inherits`, and a fourth record predates flags
- **THEN** the summary reports `--inherits` used in two of the three runs that recorded flags

#### Scenario: Diagnose escalations

- **WHEN** of three summarised runs one escalated twice, one once and one never
- **THEN** the summary reports two escalating runs and three escalations

### Requirement: Run records ride the work's pull request

A skill's run record and a chain's run notes SHALL be committed on the branch of a pull request the run opened and never pushed directly to the base branch, and a chain with no pull request left open SHALL leave its run notes uncommitted and say so in its report.

#### Scenario: A chain ends with a pull request open

- **WHEN** a chain finishes with at least one of its pull requests open
- **THEN** its run notes are committed on the last open one's branch

#### Scenario: Every pull request merged

- **WHEN** a chain finishes with all its pull requests merged
- **THEN** its run notes stay uncommitted and its report says so
