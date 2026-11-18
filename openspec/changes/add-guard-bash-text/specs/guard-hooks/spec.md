# Spec Delta

## ADDED Requirements

### Requirement: An unresolved plugin root in a command is blocked

The guard hooks SHALL block, with the reason, a shell command holding `${CLAUDE_PLUGIN_ROOT}` or `$CLAUDE_PLUGIN_ROOT` followed by a path where the shell would expand it, and SHALL stay silent for single-quoted or escaped text, a quoted-delimiter heredoc, a comment, and a command that sets the variable itself.

#### Scenario: Running a script through the placeholder

- **WHEN** an agent runs `python3 "${CLAUDE_PLUGIN_ROOT}/skills/x/scripts/check.py"`
- **THEN** the command is blocked and the agent is told the shell does not set the variable and to use the plugin's absolute path

#### Scenario: Searching for the placeholder as text

- **WHEN** an agent runs `grep -rn '${CLAUDE_PLUGIN_ROOT}/' skills`
- **THEN** the command runs

### Requirement: A write outside the checkout through .. asks first

The guard hooks SHALL ask the user, naming the path, before a shell command whose write redirect, `tee` or `mkdir` file, or `cp` or `mv` destination starts with `..` and resolves outside the checkout that holds the working directory, and SHALL stay silent for `cd ..`, a `..` path in any other argument, and a `..` path that stays inside the checkout.

#### Scenario: Copying a file next to the checkout

- **WHEN** an agent runs `cp notes.md ../notes.md.bak` from the root of a checkout
- **THEN** the user is asked before it runs, and is told to write to the session scratchpad instead

#### Scenario: Reading from outside the checkout

- **WHEN** an agent runs `cp ../shared/config.json config.json`
- **THEN** no prompt is shown

#### Scenario: A parent directory inside the checkout

- **WHEN** an agent working in a subdirectory of a checkout runs `echo x > ../out.txt`
- **THEN** no prompt is shown
