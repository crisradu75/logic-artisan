## MODIFIED Requirements

### Requirement: A command run through a shell wrapper is checked as typed bare

The guard hooks SHALL check the command a shell wrapper hands to another shell as text, by `bash -c`, `sh -c`, `eval`, `pwsh -Command`, `Invoke-Expression` or `cmd /c`, as they check that command typed bare, and SHALL ask when they cannot read all of it, except that a `cd` inside a wrapper's own shell, wrapper names in heredoc text and a wrapper run in a container or on another host stay allowed.

#### Scenario: A write outside the checkout inside bash -c

- **WHEN** an agent runs `bash -c "echo hi > ../../outside.txt"` or `bash -c 'cp a ../../b'` from a checkout
- **THEN** the user is asked before it runs

#### Scenario: A dishonest commit inside eval

- **WHEN** an agent runs `eval 'git commit -m x -m "Measured-by: none"'`
- **THEN** the command is blocked

#### Scenario: A harmless wrapped command

- **WHEN** an agent runs `bash -c "echo hi > out.txt"`, `bash -c "cd sub && ls"`, `eval "$(ssh-agent)"`, or a commit whose heredoc message names `bash -c 'rm -rf link'`
- **THEN** no prompt is shown and nothing is blocked
