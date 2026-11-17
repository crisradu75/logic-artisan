# note-checks

## ADDED Requirements

### Requirement: Links field entries resolve
The `links` check SHALL report every entry in a covered note's `links` field that is not the path from the repo root of an existing note, comparing names with exact letter case, and SHALL treat each entry as a link when the change deletes or moves its target.

#### Scenario: Entry names a missing note
- **GIVEN** a changed note whose `links` field names a note path that does not exist
- **WHEN** the `links` check runs
- **THEN** it reports the note, the line and the missing target

#### Scenario: Wrong letter case
- **GIVEN** a changed note whose `links` entry names an existing note with one folder name in different letter case
- **WHEN** the `links` check runs, on any operating system
- **THEN** it reports the entry

#### Scenario: Linked note deleted
- **GIVEN** a change that deletes note A, while an unchanged note B lists A in its `links` field
- **WHEN** the `links` check runs on the change
- **THEN** it reports note B and the entry naming A
