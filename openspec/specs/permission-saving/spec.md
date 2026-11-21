# permission-saving Specification

## Purpose

**Serves:** users who want a session's tool permissions kept for later sessions.

What the save-permissions skill writes to the project's local settings.

## Requirements

### Requirement: Only new permissions are listed

`/cla:save-permissions` SHALL list the tool permissions granted in the conversation that the project's local settings do not already allow, and when there are none SHALL say so and write nothing.

#### Scenario: Nothing new

- **WHEN** every granted permission is already in the allowlist
- **THEN** the skill says so and the settings file is not written

### Requirement: Saving keeps the rest of the settings file

`/cla:save-permissions` SHALL write only the project's local settings file, SHALL add the new entries to its allowlist and leave every other setting as it was, SHALL create the allowlist when the file has none, and SHALL leave the file unchanged and report why when it is not valid JSON or its permissions or allowlist is not the expected object or list.

#### Scenario: A settings file with other keys and no allowlist

- **WHEN** the file holds only a hooks setting
- **THEN** the allowlist is created with the new entries and the hooks setting is unchanged

#### Scenario: A file that is not valid JSON

- **WHEN** the settings file cannot be parsed
- **THEN** it is left unchanged and the skill reports the failure

#### Scenario: An allowlist that is not a list

- **WHEN** the allowlist holds a single string instead of a list
- **THEN** the file is left unchanged and the skill reports the failure

### Requirement: A wildcard permission needs the user's yes

`/cla:save-permissions` SHALL write an exact entry without asking, SHALL ask for explicit confirmation before writing any entry that contains a wildcard, whatever the command, and SHALL NOT retry another phrasing after a refusal.

#### Scenario: A broad command pattern

- **WHEN** the new entries include a wildcard pattern for a command family
- **THEN** the skill asks and writes it only on the user's yes

### Requirement: A path rule uses the form that matches

`/cla:save-permissions` SHALL save a file-path permission in gitignore path syntax as a `Read` rule, and SHALL save no `Glob` or `Grep` path rule, because Claude Code never matches one.

#### Scenario: Files read under one folder

- **WHEN** the user approved reads of several files under one absolute folder
- **THEN** the proposed entry is a `Read` rule in gitignore path syntax, and no `Glob` entry is proposed

### Requirement: Only permissions approved at a prompt are collected

`/cla:save-permissions` SHALL collect only tool calls the user approved at a permission prompt, since a call the settings already allowed was never granted in the session, and SHALL propose a Bash entry as the exact command unless the user confirms a wildcard.

#### Scenario: A call the settings already allowed

- **WHEN** a tool call ran without a prompt because an existing rule allowed it
- **THEN** it is not listed as a new permission

#### Scenario: A Bash command approved once

- **WHEN** the user approved one Bash command at a prompt
- **THEN** the proposed entry is that exact command, not a wildcard family
