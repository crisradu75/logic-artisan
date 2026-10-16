## ADDED Requirements

### Requirement: Helper agents in GitHub Copilot CLI

The plugin SHALL offer each of its helper agents to GitHub Copilot CLI with the same instructions, description and read-only tools as its Claude Code agent, and the test suite SHALL fail when a Copilot agent differs from its Claude Code agent in any of them.

#### Scenario: A Claude agent's instructions are edited alone

- **WHEN** a helper agent's instructions are changed and its Copilot copy is not
- **THEN** the test suite fails

#### Scenario: A helper agent has no Copilot copy

- **WHEN** a helper agent is added without a Copilot copy
- **THEN** the test suite fails

#### Scenario: A Copilot agent is read-only

- **WHEN** a Copilot agent's definition is read
- **THEN** it grants only the tools for reading and searching files
