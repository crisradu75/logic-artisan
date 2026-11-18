# Spec Delta

## ADDED Requirements

### Requirement: A commit message carrying Measured-by none is refused

The guard hooks SHALL refuse a `git commit` whose message holds a `Measured-by: none` trailer, and SHALL stay silent for a line that only mentions it.

#### Scenario: A none trailer

- **WHEN** an agent commits with a `Measured-by: none` trailer
- **THEN** the commit is refused

#### Scenario: A line that mentions the trailer

- **WHEN** a message says "never Measured-by: none" mid-line
- **THEN** no prompt is shown

### Requirement: An empty review-round commit is refused

The guard hooks SHALL refuse `git commit --allow-empty` with a review-round subject, and SHALL only warn on any other `--allow-empty`.

#### Scenario: An empty review-round commit

- **WHEN** an agent runs `git commit --allow-empty -m "fix: review round 2"`
- **THEN** the commit is refused

#### Scenario: Another empty commit

- **WHEN** an agent runs `git commit --allow-empty -m "chore: init"`
- **THEN** a warning is shown and the commit runs

### Requirement: A commit that would add a debug tag asks first

The guard hooks SHALL ask before a `git commit` that would add a line holding a `/cla:diagnose` debug tag, and SHALL stay silent when no such line is added or the check cannot run.

#### Scenario: A staged debug tag

- **WHEN** an agent commits a staged diff that adds a line with a debug tag
- **THEN** the user is asked before it runs

#### Scenario: No tag added

- **WHEN** the staged diff adds no debug tag
- **THEN** no prompt is shown
