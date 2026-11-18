# Spec Delta

## ADDED Requirements

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
