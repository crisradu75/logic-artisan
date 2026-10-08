## ADDED Requirements

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

### Requirement: Handoff suggests a retro on recurring trouble

After recording its run, `/cla:spec-to-pr` SHALL print one line suggesting `/cla:spec-to-pr-retro` when, among the repo's last five run records, the test phase used its whole round cap in at least three, the pull request review phase ended at its round cap with a warning in at least three, or one warning reason appears in at least two, and SHALL print nothing otherwise, never blocking the run.

#### Scenario: Revise keeps ending at its cap with a warning

- **WHEN** the pull request review phase ended at its round cap with a warning in three of the last five runs
- **THEN** Handoff prints one line naming that and suggesting the retro

#### Scenario: Revise reaches its cap cleanly

- **WHEN** the pull request review phase used its whole round cap in each of the last five runs and never warned
- **THEN** Handoff prints nothing for it

#### Scenario: A quiet ledger

- **WHEN** no phase hit its cap in three of the last five runs and no warning reason repeats
- **THEN** Handoff prints nothing extra and the run ends as before

## REMOVED Requirements

### Requirement: The spec-to-pr retro summary

**Reason**: The `--pr-rounds` reversal condition it reported is settled: a second review round now runs after every fix commit, so the summary reports that round's yield instead.

**Migration**: Restated as run-ledgers / Summarising recent spec-to-pr runs.

### Requirement: Handoff suggests a retro

**Reason**: With a second review round automatic, reaching the review cap is the normal path; only a review that ends at its cap with a warning counts now.

**Migration**: Restated as run-ledgers / Handoff suggests a retro on recurring trouble.
