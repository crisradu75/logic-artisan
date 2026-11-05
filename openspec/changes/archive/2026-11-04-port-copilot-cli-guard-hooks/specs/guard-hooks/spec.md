# Spec Delta

## ADDED Requirements

### Requirement: Copilot CLI enforces session guards

Copilot CLI sessions with CLA installed SHALL run applicable CLA guard checks around matching tool calls and apply their block, confirmation, and warning outcomes through Copilot's hook interface.

#### Scenario: An unsafe tool call is blocked

- **WHEN** a tool call matches a CLA blocking guard
- **THEN** Copilot denies the call before it runs and gives the agent the guard's reason

#### Scenario: A destructive action requires confirmation

- **WHEN** a tool call matches a CLA confirmation guard in an interactive session
- **THEN** Copilot requests user confirmation before the call runs

#### Scenario: A guarded action produces a warning

- **WHEN** a tool call matches a CLA warning guard
- **THEN** the action proceeds and the warning is made available to the agent

### Requirement: Copilot hook failures have an explicit policy

Copilot CLI guard hooks SHALL deny a matched tool call when a guard fails to run, and documentation SHALL disclose that Copilot CLI hook timeouts fail open.

#### Scenario: A guard hook exits with an error

- **WHEN** a required guard cannot load or crashes while checking a tool call
- **THEN** Copilot denies the call rather than treating the check as approval

#### Scenario: A guard hook times out

- **WHEN** Copilot CLI times out a pre-tool guard hook
- **THEN** it continues with its normal permission flow and the documented limitation makes clear that the guard did not enforce the call
