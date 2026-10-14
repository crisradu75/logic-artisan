## REMOVED Requirements

### Requirement: Summarising recent spec-to-pr runs

**Migration**: Replaced by "Summarising recent spec-to-pr runs and their second rounds", the same sentence with the two second-round scenarios merged into one so the requirement holds three scenarios.

## ADDED Requirements

### Requirement: Summarising recent spec-to-pr runs and their second rounds

`/cla:spec-to-pr-retro [N]` SHALL summarise the last N runs of each spec-to-pr ledger, 10 by default, reading every repo the fleet file lists or, when the file is missing or none of its repos exists, only the repo's own ledger and saying so, naming each ledger read, counting an unreadable record as skipped, and reporting how many of those runs' changes had a second PR review round and how many found a Critical or Important finding there, in total and by what started that round.

#### Scenario: One unreadable record

- **WHEN** a ledger holds one record with a field of the wrong shape
- **THEN** the summary covers every other record and counts the skipped one

#### Scenario: No fleet on this machine

- **WHEN** the fleet file is missing or lists no repo that exists on the machine
- **THEN** the summary reads only the repo's own ledger and says why

#### Scenario: Second-round yield, in total and by what started the round

- **WHEN** three changes had a second pull request review round, two following a fixed Critical and finding something, one following only Important fixes on a high-risk pull request and finding nothing
- **THEN** the summary reports three such changes, two of which found one, and reports each kind apart so the empty kind is visible next to the one still finding defects
