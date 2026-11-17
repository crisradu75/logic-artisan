# note-schema

## Purpose

**Serves:** the owner's notes and every skill that writes or searches them. It defines the fields every note carries and how a domain repo declares its own note types.

## ADDED Requirements

### Requirement: Required base fields
Every note SHALL carry the five required base fields `type`, `title`, `created`, `summary` and `status`, each with a non-empty value, or the `schema` check SHALL report the note and name each missing field.

#### Scenario: Missing summary
- **GIVEN** a changed note with no `summary` field
- **WHEN** the `schema` check runs
- **THEN** it reports the note and names `summary`

#### Scenario: Empty title
- **GIVEN** a changed note whose `title` has an empty value
- **WHEN** the `schema` check runs
- **THEN** it reports the note and names `title`

### Requirement: Optional and extra fields
The `schema` check SHALL accept a note that leaves out any of the optional base fields `updated`, `tags`, `aliases` and `source`, and a note that carries a field no schema names.

#### Scenario: Optional fields left out
- **GIVEN** a changed note with the five required fields and none of the optional ones
- **WHEN** the `schema` check runs
- **THEN** it does not report the note

#### Scenario: Extra field
- **GIVEN** a changed note that also carries a field named `mood`
- **WHEN** the `schema` check runs
- **THEN** it does not report the note for that field

### Requirement: Base field values
The `schema` check SHALL report a note whose `created` or `updated` is not a date written as year-month-day, whose `tags` or `aliases` is not a list, or whose `status` is not `inbox`, `active` or `archived`.

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

### Requirement: Inbox notes
A note in the top-level `inbox` folder SHALL have `status: inbox`, and the `schema` check SHALL apply only the base-field rules to it, never the domain type rules, while every other check, the secret scan included, still covers it.

#### Scenario: Unclassified note in the inbox
- **GIVEN** a changed note in `inbox` with valid base fields and a `type` the domain schema does not declare
- **WHEN** the `schema` check runs
- **THEN** it does not report the note

#### Scenario: Wrong status in the inbox
- **GIVEN** a changed note in `inbox` with `status: active`
- **WHEN** the `schema` check runs
- **THEN** it reports the note and names `status`

#### Scenario: Secret scan still covers the inbox
- **GIVEN** a changed note in `inbox` holding a card number
- **WHEN** the `secrets` check runs
- **THEN** it reports the note

### Requirement: Domain type rules
Outside the `inbox` folder, a note's `type` SHALL name a type its repo's schema file declares, and the note SHALL carry that type's required fields, sit under that type's folder, and have a file name that matches that type's name pattern.

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

### Requirement: Domain schema file
A domain repo SHALL declare its note types in a `mnemo.schema.yml` file at its top level, where each type names a folder and may give a name pattern and lists of required and optional fields, and a type named `inbox` or a key the format does not define SHALL make every check exit 2.

#### Scenario: Type named inbox
- **GIVEN** a domain schema that declares a type named `inbox`
- **WHEN** the `schema` check runs
- **THEN** it exits 2 and says `inbox` is a status and a folder, not a type

#### Scenario: Unknown key
- **GIVEN** a domain schema whose type carries a key the format does not define
- **WHEN** the `schema` check runs
- **THEN** it exits 2 and names the file, line and key

#### Scenario: Unlisted type field is optional
- **GIVEN** a domain type whose schema lists `location` only as optional
- **WHEN** the `schema` check covers a note of that type without `location`
- **THEN** it does not report the note

### Requirement: YAML subset
Note front matter and schema files SHALL be read as a small YAML subset, made of `key: value` lines and inline lists, with block nesting two levels deep in schema files only, and any construct outside it SHALL be reported with the file, the line and a fix, never guessed at.

#### Scenario: Value with a colon
- **GIVEN** a changed note with `source: https://example.org/a`
- **WHEN** the `schema` check runs
- **THEN** it reads the whole web address as the value and does not report the note

#### Scenario: Quoted value with quotes and a colon
- **GIVEN** a changed note whose title is a double-quoted value holding an escaped double quote and a colon followed by a space
- **WHEN** the `schema` check runs
- **THEN** it reads the title exactly, without the outer quotes, and does not report the note

#### Scenario: Block list
- **GIVEN** a changed note whose `tags` is written as a block list of `- item` lines
- **WHEN** the `schema` check runs
- **THEN** it reports the note's line and suggests the inline list form

### Requirement: Add-only base schema
The base schema SHALL only grow by optional fields, so its required fields stay exactly `type`, `title`, `created`, `summary` and `status`, and no field it has listed is ever removed.

#### Scenario: Required set is fixed
- **WHEN** the plugin's tests read the base schema
- **THEN** its required fields are exactly the five base fields, and its optional fields include `updated`, `tags`, `aliases` and `source`
