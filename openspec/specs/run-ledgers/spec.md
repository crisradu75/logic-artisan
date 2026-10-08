# run-ledgers Specification

## Purpose

The run records skills append under a repo's `cla.io/retro/`, and the retro reports read from them.

## Requirements

### Requirement: Ledger files

Skills that record their runs SHALL append one JSON object per line to a ledger in the repo's `cla.io/retro/` directory, or in the directory `CLAUDE_RETRO_DIR` names, and a record that is not a single JSON object SHALL be refused, leaving the ledger unchanged.

#### Scenario: A run is recorded

- **WHEN** a skill records a run
- **THEN** the ledger gains exactly one line holding that run's JSON object

#### Scenario: A broken record

- **WHEN** a skill hands the writer something that is not a JSON object
- **THEN** the writer refuses it and the ledger is unchanged

### Requirement: The spec-to-pr run record

Each `/cla:spec-to-pr` run SHALL append one record to `cla.io/retro/spec-to-pr-runs.jsonl` giving its time, change and mode, the flags it was invoked with, how many times it escalated to `/cla:diagnose`, and, for each phase, its status, the reason for a warning or failure, and the rounds used, with the pull request review phase also giving the Critical and Important findings each round found.

#### Scenario: A run with two pull request review rounds

- **WHEN** a run's pull request review takes two rounds
- **THEN** its record lists both rounds in order with the findings each found

#### Scenario: A run invoked with flags

- **WHEN** a run is invoked with `--inherits` and `--pr-rounds 1`
- **THEN** its record lists both flag names, without their values

### Requirement: Summarising recent spec-to-pr runs

`/cla:spec-to-pr-retro [N]` SHALL summarise the last N runs of each spec-to-pr ledger, 10 by default, reading every repo the repo's fleet file lists or, when none of them exists on the machine, only the repo's own ledger and saying so, naming each ledger read, counting a record it cannot read as skipped instead of failing, and reporting how many of those runs' changes had a second pull request review round and how many of those found a Critical or Important finding in it.

#### Scenario: One unreadable record

- **WHEN** a ledger holds one record with a field of the wrong shape
- **THEN** the summary covers every other record and counts the skipped one

#### Scenario: No fleet on this machine

- **WHEN** the fleet file is missing or lists no repo that exists on the machine
- **THEN** the summary reads only the repo's own ledger and says why

#### Scenario: Second-round yield

- **WHEN** three changes in the summarised runs had a second pull request review round and two of those rounds found a Critical or Important finding
- **THEN** the summary reports three such changes, two of which found one

### Requirement: Handoff suggests a retro on repeated trouble

After recording its run, `/cla:spec-to-pr` SHALL print one line suggesting `/cla:spec-to-pr-retro` when, among the repo's last five run records, the test phase used its whole round cap in at least three, the pull request review phase ended at its round cap with a warning or failure in at least three, or one warning reason appears in at least two, and SHALL print nothing otherwise, never blocking the run.

#### Scenario: Revise keeps ending at its cap with a warning or failure

- **WHEN** the pull request review phase ended at its round cap with a warning or failure in three of the last five runs
- **THEN** Handoff prints one line naming that and suggesting the retro

#### Scenario: Revise reaches its cap cleanly

- **WHEN** the pull request review phase used its whole round cap in each of the last five runs and never warned or failed
- **THEN** Handoff prints nothing for it

#### Scenario: A quiet ledger

- **WHEN** no phase hit its cap in three of the last five runs and no warning reason repeats
- **THEN** Handoff prints nothing extra and the run ends as before

### Requirement: Summarising flag use and diagnose escalations

`/cla:spec-to-pr-retro` SHALL report, over the summarised runs whose records carry them, how many runs used each flag, and how many runs escalated to `/cla:diagnose` and how many times in all.

#### Scenario: Flags across runs

- **WHEN** three summarised runs record their flags, two of them `--inherits`, and a fourth record predates flags
- **THEN** the summary reports `--inherits` used in two of the three runs that recorded flags

#### Scenario: Diagnose escalations

- **WHEN** of three summarised runs one escalated twice, one once and one never
- **THEN** the summary reports two escalating runs and three escalations

### Requirement: Only checked spec-to-pr run records are written

The writer SHALL append only to the spec-to-pr ledger, refusing a record for any other ledger or one whose fields or field values do not match the spec-to-pr record shape, printing one line that names the ledger it accepts or every field that does not match and leaving the ledger unchanged, and a skill whose record is refused SHALL correct it and try once more, then finish its run whether or not the record was written.

#### Scenario: Phases written as an object

- **WHEN** a spec-to-pr record gives its phases as an object instead of a list
- **THEN** the writer refuses it with a line naming `phases`, and the ledger is unchanged

#### Scenario: The retired codify ledger

- **WHEN** a skill writes to the codify-learnings ledger
- **THEN** the writer refuses it with a line naming the spec-to-pr ledger, and writes nothing

#### Scenario: A record refused twice

- **WHEN** a skill's corrected record is refused again
- **THEN** the skill reports that the record was not written and its run still finishes

### Requirement: The spec-to-pr run record rides its pull request

`/cla:spec-to-pr` SHALL commit its run record only on the branch of the pull request it opened, never on the base branch, and when it opened none SHALL leave the record uncommitted and say so in its report.

#### Scenario: A run that opened a pull request

- **WHEN** a run ends with its pull request open
- **THEN** its run record is committed on that pull request's branch

#### Scenario: A run that opened none

- **WHEN** a run ends without opening a pull request
- **THEN** its run record stays uncommitted and its report says so

### Requirement: Chain run notes stay local

`/cla:multi-lite` and `/cla:multi-pr` SHALL keep their run notes as local working state that no step adds, commits or pushes, and a resume that cannot find them SHALL fall back to the state of the pull requests on GitHub.

#### Scenario: A chain ends with a pull request open

- **WHEN** a chain finishes with some of its pull requests still open
- **THEN** its run notes stay uncommitted on the machine that ran it and no branch gets a notes commit

#### Scenario: Resuming where the notes are missing

- **WHEN** a chain is re-run on another machine, or after its notes file was deleted
- **THEN** it reads each change's state from GitHub instead
