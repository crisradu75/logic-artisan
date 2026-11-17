# Spec Delta

## ADDED Requirements

### Requirement: Loop metadata is optional
The base schema SHALL allow `questions` and `links` as optional note fields, the checks SHALL treat `hubs/` and `archive/` as note folders like any other, and a domain schema MAY carry a `mnemo_schema_version` key, so that no existing note or schema needs rewriting.

#### Scenario: Existing note without the new fields
- **WHEN** a note written before this change, with only base fields, is edited
- **THEN** `schema` passes it

#### Scenario: Note in hubs
- **WHEN** a changed note in `hubs/` lacks `summary`
- **THEN** `schema` fails it as it would anywhere else

#### Scenario: Schema version key
- **WHEN** a domain schema carries `mnemo_schema_version: 1`
- **THEN** the schema reader accepts it
