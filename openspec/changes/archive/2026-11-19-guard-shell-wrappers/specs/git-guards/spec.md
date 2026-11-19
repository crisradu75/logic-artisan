## ADDED Requirements

### Requirement: A destructive git command run through a shell wrapper asks first

The guard hooks SHALL ask the user before a git command they would ask about when that command is handed to another shell as text, by `bash -c`, `sh -c`, `zsh -c`, `eval`, `pwsh -Command`, `Invoke-Expression` or `cmd /c`, and SHALL stay silent when the wrapped command is one they would not ask about.

#### Scenario: A force-push inside bash -c

- **WHEN** an agent runs `bash -c "git push -f origin x"`
- **THEN** the user is asked before it runs

#### Scenario: A harmless wrapped command

- **WHEN** an agent runs `bash -c "git status"` or `eval "$(ssh-agent)"`
- **THEN** no prompt is shown

### Requirement: A git subcommand or flag from an unresolved expansion asks first

The guard hooks SHALL read a git subcommand, or a push, reset or branch option, that is quoted, or that a variable assigned a plain value in the same command supplies, as its value, and SHALL ask the user when the subcommand, an option whose literal start is `-`, or an unquoted option of a push, reset or branch before its first operand comes from an expansion they cannot resolve.

#### Scenario: A subcommand from a variable

- **WHEN** an agent runs `X=push; git $X -f origin x`, or `git $SUB -f origin x` where nothing in the command sets `SUB`
- **THEN** the user is asked before it runs

#### Scenario: A quoted or partly expanded force flag

- **WHEN** an agent runs `git push "-f" origin x`, or `git push --force$X origin x` where nothing in the command sets `X`
- **THEN** the user is asked before it runs

#### Scenario: A branch name from a variable

- **WHEN** an agent runs `git push origin "$BRANCH"`
- **THEN** no prompt is shown

### Requirement: A long command is read within the guard's time

The guard hooks SHALL finish reading any command up to the dispatcher's scan limit well inside the hook handler's timeout, and SHALL ask the user when a command needs more reading than they allow, rather than run into the timeout, which lets the call run unchecked.

#### Scenario: A long run of shell wrappers

- **WHEN** an agent runs a command of hundreds of thousands of characters of repeated `eval` words followed by `git push -f origin x`
- **THEN** the user is asked before it runs, within two seconds of the guard's processing time
