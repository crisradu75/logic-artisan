# note-schema

## MODIFIED Requirements

### Requirement: Optional and extra fields
The `schema` check SHALL accept a note that leaves out any of the optional base fields `updated`, `tags`, `aliases`, `source`, `questions` and `links`, and a note that carries a field no schema names.

#### Scenario: Optional fields left out
- **GIVEN** a changed note with the five required fields and none of the optional ones
- **WHEN** the `schema` check runs
- **THEN** it does not report the note

#### Scenario: Extra field
- **GIVEN** a changed note that also carries a field named `mood`
- **WHEN** the `schema` check runs
- **THEN** it does not report the note for that field

### Requirement: Base field values
The `schema` check SHALL report a note whose `created` or `updated` is not a date written as year-month-day, whose `tags`, `aliases`, `questions` or `links` is not a list, or whose `status` is not `inbox`, `active` or `archived`.

#### Scenario: Date in another format
- **GIVEN** a changed note with `created: 15/11/2026`
- **WHEN** the `schema` check runs
- **THEN** it reports the note and names `created`

#### Scenario: Tags not a list
- **GIVEN** a changed note with `tags: roadmap`
- **WHEN** the `schema` check runs
- **THEN** it reports the note and names `tags`

#### Scenario: Unknown status
- **GIVEN** a changed note with `status: draft`
- **WHEN** the `schema` check runs
- **THEN** it reports the note and lists the allowed statuses

### Requirement: Domain type rules
Outside the top-level `inbox`, `hubs` and `archive` folders, a note's `type` SHALL name a type its repo's schema file declares, and the note SHALL carry that type's required fields, sit under that type's folder, and have a file name that matches that type's name pattern.

#### Scenario: Undeclared type
- **GIVEN** a changed note outside `inbox` whose `type` the domain schema does not declare
- **WHEN** the `schema` check runs
- **THEN** it reports the note and names its type

#### Scenario: Missing type field
- **GIVEN** a domain type that requires `date`, and a changed note of that type without it
- **WHEN** the `schema` check runs
- **THEN** it reports the note and names `date`

#### Scenario: Wrong folder or name
- **GIVEN** a changed note of a declared type that sits outside the type's folder, or whose file name breaks the type's name pattern
- **WHEN** the `schema` check runs
- **THEN** it reports the note and names the expected folder or pattern
