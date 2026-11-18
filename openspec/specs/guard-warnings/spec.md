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

### Requirement: A subagent dispatch without a model warns

The guard hooks SHALL warn, without blocking, when an agent dispatches a subagent without naming the model it runs on.

#### Scenario: A dispatch with no model

- **WHEN** an agent dispatches a subagent and passes no model
- **THEN** the subagent starts, and the agent is warned that it runs on an unplanned model

#### Scenario: A dispatch that names its model

- **WHEN** an agent dispatches a subagent and names its model
- **THEN** no warning is shown

### Requirement: A subagent prompt holding diff text warns

The guard hooks SHALL warn, without blocking, when a subagent's prompt holds pasted diff text, a line starting `diff --git `, rather than the path of a diff file.

#### Scenario: Diff text pasted into a prompt

- **WHEN** an agent dispatches a subagent whose prompt holds a pasted diff
- **THEN** the subagent starts, and the agent is told to pass a diff file's path instead

#### Scenario: A prompt that names a diff file

- **WHEN** the prompt names the absolute path of a diff file and mentions the diff header only in a sentence
- **THEN** no warning is shown

### Requirement: A review brief that says no area is protected warns

The guard hooks SHALL warn, without blocking, when a subagent's prompt fills its protected-areas slot with `(none recorded)`.

#### Scenario: The protected-areas slot left as none recorded

- **WHEN** an agent dispatches a review whose brief reads "touches a protected area ((none recorded))"
- **THEN** the review starts, and the agent is told to fill the slot with the protected areas or the default-list line

#### Scenario: Another slot left as none recorded

- **WHEN** a brief fills its protected-areas slot and says `(none recorded)` only for a formula set
- **THEN** no warning is shown

### Requirement: A doc sweep reply without its footer warns

The guard hooks SHALL warn, without blocking, when a documentation sweeper's completed reply holds no line starting `Scanned:`, and SHALL NOT judge whether the footer's counts are true.

#### Scenario: A sweep reply with no footer

- **WHEN** a documentation sweeper returns "No stale references found." with no `Scanned:` line
- **THEN** the agent sees the reply with a warning that the sweep cannot be told apart from one that searched nothing

#### Scenario: A sweep still running in the background

- **WHEN** the sweeper was launched in the background and has not replied yet
- **THEN** no warning is shown

### Requirement: A fix reply without its fact-corrections field warns

The guard hooks SHALL warn, without blocking, when a subagent whose brief names `Fact corrections:` replies without that field, and SHALL NOT judge whether the field's content is true.

#### Scenario: The field is missing

- **WHEN** a brief asks for `Fact corrections:` and the reply ends without it
- **THEN** the agent sees the reply with a warning that a missing field is not `(none)`

#### Scenario: The field is present

- **WHEN** the reply holds `Fact corrections: (none)`
- **THEN** no warning is shown
