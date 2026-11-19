## ADDED Requirements

### Requirement: A command run through a shell wrapper is checked as typed bare

The guard hooks SHALL check the command a shell wrapper hands to another shell as text, by `bash -c`, `sh -c`, `eval`, `pwsh -Command`, `Invoke-Expression` or `cmd /c`, as they check a command typed bare, blocking or asking where the bare form would, except that a `cd` run inside a wrapper's own shell and wrapper names in a quoted heredoc's text stay allowed.

#### Scenario: A write outside the checkout inside bash -c

- **WHEN** an agent runs `bash -c "echo hi > ../../outside.txt"` from a checkout
- **THEN** the user is asked before it runs

#### Scenario: A dishonest commit inside eval

- **WHEN** an agent runs `eval 'git commit -m x -m "Measured-by: none"'`
- **THEN** the command is blocked

#### Scenario: A harmless wrapped command

- **WHEN** an agent runs `bash -c "echo hi > out.txt"`, `bash -c "cd sub && ls"` or `eval "$(ssh-agent)"`
- **THEN** no prompt is shown and nothing is blocked
