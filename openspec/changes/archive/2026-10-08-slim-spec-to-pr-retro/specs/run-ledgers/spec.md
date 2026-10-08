## ADDED Requirements

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

## REMOVED Requirements

### Requirement: The spec-to-pr retro report

**Reason**: Rewritten to read the fleet by default, fall back to the repo's own ledger, and report the `--pr-rounds` reversal condition.

**Migration**: Restated as run-ledgers / The spec-to-pr retro summary.
