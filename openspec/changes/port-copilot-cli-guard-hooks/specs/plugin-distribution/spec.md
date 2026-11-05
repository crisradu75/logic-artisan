# Spec Delta

## MODIFIED Requirements

### Requirement: Helper agents in GitHub Copilot CLI

The plugin SHALL offer each helper agent to GitHub Copilot CLI with the same instructions,
description, and read-only tools as its Claude Code agent. Generated Copilot profiles SHALL omit
account-specific model IDs so they inherit the session model, and the local release check SHALL
reject unmapped source aliases, stale copies, or explicit Copilot model pins.

#### Scenario: A source agent changes without a matching Copilot copy

- **WHEN** a helper agent is added or changed without a matching generated Copilot profile
- **THEN** the test suite fails

#### Scenario: A Copilot agent is read-only

- **WHEN** a Copilot agent's definition is read
- **THEN** it grants only the tools for reading and searching files

#### Scenario: A Copilot profile does not inherit the session model

- **WHEN** the local release check finds an unmapped source alias, stale generated copy, or explicit
  Copilot model ID
- **THEN** the release check fails with a diagnostic

### Requirement: Documenting Copilot CLI validation status

Copilot CLI documentation SHALL identify its supported surface, validated capabilities,
unsupported behavior, and troubleshooting steps. It SHALL document marketplace registration,
installation, update, and instruction discovery, and explain how to copy the response style to
`.github/copilot-instructions.md`.

#### Scenario: A reader installs or updates the Copilot CLI plugin

- **WHEN** a reader follows the Copilot CLI guidance
- **THEN** it gives marketplace registration, install, update, and troubleshooting commands, and
  says the source-style file must be copied to `.github/copilot-instructions.md`

#### Scenario: A reader checks Copilot support boundaries

- **WHEN** a reader checks which Copilot surfaces and plugin features are supported
- **THEN** the guidance says the scope is Copilot CLI only, describes the source-tree
  `PreToolUse`/`PostToolUse` guard support and its fail-open timeout and autopilot-confirmation
  limitations, distinguishes those source changes from release `cla--v2.2.3`, and marks workflows
  requiring Claude-only delegation, chaining, model routing, or permission settings unsupported

#### Scenario: A reader checks the helper-agent model behavior

- **WHEN** a reader checks the current Copilot helper-agent profiles
- **THEN** the guidance says they inherit the session model because profiles omit account-specific
  model IDs
