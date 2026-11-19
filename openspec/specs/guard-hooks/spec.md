# guard-hooks Specification

## Purpose

**Serves:** maintainers whose agents run commands in a repo that installs the plugin.

The safety checks the plugin applies to an agent's tool calls in a repo that installs it.

## Requirements

### Requirement: Guard hooks load with the plugin

Loading the plugin SHALL turn on its guard hooks in every session, with no settings change in the repo and no warning at session start.

#### Scenario: A session starts with the plugin installed

- **WHEN** a session starts in a repo with the plugin installed
- **THEN** the guard hooks run on matching tool calls
- **AND** no hook configuration warning is printed

### Requirement: A recursive delete through a link is blocked

The guard hooks SHALL block, with the reason, a recursive force delete whose target is a symbolic link or junction.

#### Scenario: Deleting through a link

- **WHEN** an agent runs `rm -rf` on a path that is a symbolic link to another directory
- **THEN** the command is blocked and the agent is told why

#### Scenario: Deleting an ordinary directory

- **WHEN** an agent runs `rm -rf` on an ordinary directory
- **THEN** the command runs

### Requirement: A cd inside a shell command is blocked

The guard hooks SHALL block, with the reason, a `cd` inside a shell command.

#### Scenario: A command that changes directory

- **WHEN** an agent runs a shell command that holds `cd`
- **THEN** the command is blocked and the agent is told to use absolute paths

### Requirement: A command too large to scan asks first

The Bash and PowerShell dispatcher SHALL ask the user, naming the command's size and the limit, instead of running any guard on a command longer than 500,000 characters, so a scan that outlasts the hook timeout cannot let it through unchecked.

#### Scenario: A command over the limit

- **WHEN** an agent runs a command longer than 500,000 characters
- **THEN** the user is asked before it runs, and no guard scanned it

#### Scenario: A command at the limit

- **WHEN** an agent runs a command of exactly 500,000 characters
- **THEN** the guards scan it as they would a shorter one

### Requirement: A write from a linked worktree into the main clone is blocked

The guard hooks SHALL block, with the reason, a file write made from a linked worktree into the main clone or another worktree inside it, unless `ALLOW_WORKTREE_PATH_ESCAPE=1` is set.

#### Scenario: Writing back into the main clone

- **WHEN** an agent working in a linked worktree writes a file at a path in the main clone
- **THEN** the write is blocked and the agent is told why

#### Scenario: A deliberate escape

- **WHEN** `ALLOW_WORKTREE_PATH_ESCAPE=1` is set
- **THEN** the same write goes through

### Requirement: A write into an installed plugin copy asks first

The guard hooks SHALL ask the user, naming the copy, before an Edit or Write whose resolved target lies in the `cache/` or `marketplaces/` part of the plugins directory, or inside the plugin's own root when that root lies in the plugins directory, and SHALL stay silent for a plugin run from a working tree and for the plugin's data directory.

#### Scenario: Editing the installed copy

- **WHEN** an agent edits a file under `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`, directly or through a symbolic link
- **THEN** the user is asked before it runs, and is told the edit is lost on the next update and that a repo's rules go in `cla.io/overlays/<skill>.md` or `cla.io/project-facts.md`

#### Scenario: Editing a plugin run from its working tree

- **WHEN** the plugin was loaded with `--plugin-dir` from a git working tree and an agent edits a file in that tree
- **THEN** no prompt is shown

#### Scenario: Writing the plugin's data directory

- **WHEN** an agent writes a file under `~/.claude/plugins/data/<plugin-id>/`
- **THEN** no prompt is shown

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
