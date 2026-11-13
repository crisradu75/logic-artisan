# guard-warnings Specification

## Purpose

**Serves:** maintainers whose agents run commands and writes in a repo that installs the plugin.

The risky actions the plugin warns about without blocking them.

## Requirements

### Requirement: A much shorter rewrite of a tracked file warns

The guard hooks SHALL warn, without blocking, when a write replaces a tracked file with a much shorter one.

#### Scenario: A file is rewritten much shorter

- **WHEN** an agent writes a tracked file with far less content than it had
- **THEN** the write goes through with a warning asking what was dropped

### Requirement: Deleting the base of a stacked pull request warns

The guard hooks SHALL warn, without blocking, when `gh pr merge --delete-branch` would delete a branch that other open pull requests are based on.

#### Scenario: Merging the base of a stacked pull request

- **WHEN** an agent runs `gh pr merge --delete-branch` on a pull request whose branch another open pull request is based on
- **THEN** the merge goes ahead with a warning that the other pull request will be closed

### Requirement: A commit that may include a stray scratch file warns

The guard hooks SHALL warn, without blocking, when a commit may pick up a stray scratch file in the repo root.

#### Scenario: A scratch file sits untracked in the repo root

- **WHEN** an agent stages or commits while an untracked file with a scratch-like name sits in the repo root
- **THEN** the command goes ahead with a warning naming the file

### Requirement: A dated comment warns

The guard hooks SHALL warn, without blocking, when a write adds a Python or shell comment that carries a date.

#### Scenario: A comment with a date

- **WHEN** an agent writes a Python or shell file with a comment that holds a date
- **THEN** the write goes through with a warning quoting the comment

#### Scenario: A comment line millions of characters long

- **WHEN** an agent writes a Python file with a single comment line of millions of `#` characters
- **THEN** the check finishes within seconds, before the hook's time limit, and the write goes through

### Requirement: A heredoc holding an escape the shell would change warns

The guard hooks SHALL warn, without blocking, when a shell command's heredoc holds a backslash escape that the shell would change before the program reads it.

#### Scenario: A backslash n in a heredoc

- **WHEN** an agent runs a command whose heredoc writes `\n` inside a string
- **THEN** the command runs with a warning naming the escape
