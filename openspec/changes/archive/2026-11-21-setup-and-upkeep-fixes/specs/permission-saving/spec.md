## ADDED Requirements

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
