## MODIFIED Requirements

### Requirement: Only permissions approved at a prompt are collected

`/cla:save-permissions` SHALL collect only tool calls the user approved at a permission prompt, since a call the settings already allowed was never granted in the session, and SHALL propose a Bash entry as the exact command unless the user confirms a wildcard.

#### Scenario: A call the settings already allowed

- **WHEN** a tool call ran without a prompt because an existing rule allowed it
- **THEN** it is not listed as a new permission

#### Scenario: A Bash command approved once

- **WHEN** the user approved one Bash command at a prompt
- **THEN** the proposed entry is that exact command, not a wildcard family
