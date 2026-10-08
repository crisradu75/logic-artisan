## ADDED Requirements

### Requirement: Run records are checked when written

The writer SHALL refuse a spec-to-pr or codify-learnings run record whose fields or field values do not match that ledger's record shape, printing one line that names the field and leaving the ledger unchanged, and a skill whose record is refused SHALL correct it and try once more, then finish its run whether or not the record was written.

#### Scenario: Phases written as an object

- **WHEN** a spec-to-pr record gives its phases as an object instead of a list
- **THEN** the writer refuses it with a line naming `phases`, and the ledger is unchanged

#### Scenario: A ledger with no record shape

- **WHEN** a skill writes to any other ledger
- **THEN** the writer checks only that the record is one JSON object within the size limit

#### Scenario: A record refused twice

- **WHEN** a skill's corrected record is refused again
- **THEN** the skill reports that the record was not written and its run still finishes
