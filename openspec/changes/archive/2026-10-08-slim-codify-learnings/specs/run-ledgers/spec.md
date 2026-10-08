## ADDED Requirements

### Requirement: The spec-to-pr retro report

`/cla:spec-to-pr-retro [N]` SHALL summarise the last N runs of the spec-to-pr ledger, 10 by default, and propose improvements, reading several ledgers together when given several and naming each one read, and counting a malformed record as lost instead of failing the report.

#### Scenario: One malformed record

- **WHEN** a ledger holds one record with a field of the wrong shape
- **THEN** the report covers every other record and counts the damaged one

#### Scenario: Ledgers from several repos

- **WHEN** the report is given the ledgers of several repos
- **THEN** it summarises their runs together and names every ledger it read

## REMOVED Requirements

### Requirement: Retro reports

**Reason**: `/cla:codify-retro` is deleted. `/cla:codify-learnings` now finds a lesson that failed again by itself, checking each session failure against the rules earlier runs wrote.

**Migration**: The spec-to-pr half is restated as run-ledgers / The spec-to-pr retro report.
