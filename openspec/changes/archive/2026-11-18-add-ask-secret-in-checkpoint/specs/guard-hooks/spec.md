# Spec Delta

## ADDED Requirements

### Requirement: A secret written into a committed briefing asks first

The guard hooks SHALL ask the user, naming the kind of secret and its line but not its value, before an Edit or Write puts a well-known API key, a private-key header, a JWT or a connection URL with a real password into a checkpoint, decision, feedback or lessons-learned file, and SHALL stay silent for placeholders, ordinary prose and other files.

#### Scenario: A checkpoint with a connection string

- **WHEN** an agent writes a checkpoint whose text holds a database URL with its real password
- **THEN** the user is asked before it runs, is told the kind and the line, and is told to name the file, not its value
- **AND** the prompt does not contain the password

#### Scenario: A placeholder in a briefing

- **WHEN** an agent writes a checkpoint whose connection URL shows its password as `<password>` or `${DB_PASSWORD}`
- **THEN** no prompt is shown

#### Scenario: A secret in an ordinary file

- **WHEN** an agent writes an API key into a file outside those briefing directories
- **THEN** this guard shows no prompt
