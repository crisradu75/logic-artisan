# loop-metadata

## Purpose

**Serves:** the improvement loop and the recall skill, which read and write the loop's notes and test set. It sets the rules for hub notes, archived notes and the test-set file.

## ADDED Requirements

### Requirement: Hub notes
A note in the top-level `hubs` folder SHALL carry `type: hub` and the base fields, SHALL need no type declared in the domain schema, and SHALL name the notes it gathers in its `links` field.

#### Scenario: Hub passes without a declared type
- **GIVEN** a domain schema that declares no `hub` type, and a changed note in `hubs` with `type: hub`, valid base fields and a `links` list of existing notes
- **WHEN** the `schema` check runs
- **THEN** it does not report the note

#### Scenario: Wrong type in the hubs folder
- **GIVEN** a changed note in `hubs` whose `type` is a declared domain type
- **WHEN** the `schema` check runs
- **THEN** it reports the note and says notes in `hubs` have `type: hub`

### Requirement: Archived notes
A note in the top-level `archive` folder SHALL carry `status: archived` and a type the domain schema declares, and SHALL meet that type's field and file-name rules but not its folder rule.

#### Scenario: Archived note passes
- **GIVEN** a changed note in `archive` with `status: archived`, a declared type and that type's required fields
- **WHEN** the `schema` check runs
- **THEN** it does not report the note

#### Scenario: Active note in the archive
- **GIVEN** a changed note in `archive` with `status: active`
- **WHEN** the `schema` check runs
- **THEN** it reports the note and names `status`

### Requirement: Test-set file
The test set SHALL be a list in `_meta/tests/questions.yml` whose entries each give the question, the notes expected to answer it as paths from the repo root, the date it was added and the query-log line it came from.

#### Scenario: Entry read back
- **WHEN** the plugin's tests read the template test set and an invented one-entry example
- **THEN** the template holds no entry, and the example's entry has exactly the four keys with a date in year-month-day form
