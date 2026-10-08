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

Each `/cla:spec-to-pr` run SHALL append one record to `cla.io/retro/spec-to-pr-runs.jsonl` giving its time, change, mode and arguments and, for each phase, its status, the reason for a warning or failure, and the rounds used, with the pull request review phase also giving the Critical and Important findings each round found.

#### Scenario: A run with two pull request review rounds

- **WHEN** a run's pull request review takes two rounds
- **THEN** its record lists both rounds in order with the findings each found

### Requirement: Run records are checked when written

The writer SHALL refuse a spec-to-pr or codify-learnings run record whose fields or field values do not match that ledger's record shape, printing one line that names every field that does not match and leaving the ledger unchanged, and a skill whose record is refused SHALL correct it and try once more, then finish its run whether or not the record was written.

#### Scenario: Phases written as an object

- **WHEN** a spec-to-pr record gives its phases as an object instead of a list
- **THEN** the writer refuses it with a line naming `phases`, and the ledger is unchanged

#### Scenario: A ledger with no record shape

- **WHEN** a skill writes to any other ledger
- **THEN** the writer checks only that the record is one JSON object within the size limit

#### Scenario: A record refused twice

- **WHEN** a skill's corrected record is refused again
- **THEN** the skill reports that the record was not written and its run still finishes

### Requirement: The spec-to-pr retro summary

`/cla:spec-to-pr-retro [N]` SHALL summarise the last N runs of each spec-to-pr ledger, 10 by default, reading every repo the repo's fleet file lists or, when none of them exists on the machine, only the repo's own ledger and saying so, naming each ledger read, counting a record it cannot read as skipped instead of failing, and stating whether the `--pr-rounds` reversal condition holds over every record read.

#### Scenario: One unreadable record

- **WHEN** a ledger holds one record with a field of the wrong shape
- **THEN** the summary covers every other record and counts the skipped one

#### Scenario: No fleet on this machine

- **WHEN** the fleet file is missing or lists no repo that exists on the machine
- **THEN** the summary reads only the repo's own ledger and says why

#### Scenario: The reversal condition holds

- **WHEN** at least eight changes across at least two chains ran a second pull request review round, and on most of them that round found a Critical or Important finding
- **THEN** the summary states that the condition is met

### Requirement: Handoff suggests a retro

After recording its run, `/cla:spec-to-pr` SHALL print one line suggesting `/cla:spec-to-pr-retro` when, among the repo's last five run records, the test or pull request review phase used its whole round cap in at least three, or one warning reason appears in at least two, and SHALL print nothing otherwise, never blocking the run.

#### Scenario: Revise keeps exhausting its cap

- **WHEN** the pull request review phase used its whole round cap in three of the last five runs
- **THEN** Handoff prints one line naming that and suggesting the retro

#### Scenario: A quiet ledger

- **WHEN** no phase hit its cap in three of the last five runs and no warning reason repeats
- **THEN** Handoff prints nothing extra and the run ends as before
