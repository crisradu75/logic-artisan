# Spec Delta

## ADDED Requirements

### Requirement: A broad git add that would stage untracked files asks first

The guard hooks SHALL ask the user before a `git add` of the whole tree or a whole directory (`-A`, `--all`, `.`, `:/`, `*` or a bare `openspec/`) when it would stage untracked files, naming up to ten of them, and SHALL stay silent when it would stage none or cannot check.

#### Scenario: A broad add over an untracked file

- **WHEN** an agent runs `git add -A` and an untracked file `notes.tmp` is in the tree
- **THEN** the user is asked before it runs, and the prompt names `notes.tmp`

#### Scenario: A broad add over tracked changes only

- **WHEN** an agent runs `git add .` and the only changes are to tracked files
- **THEN** no prompt is shown

#### Scenario: An add of named paths

- **WHEN** an agent runs `git add -A src/app.py` or `git add -u`
- **THEN** no prompt is shown
