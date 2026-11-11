# copilot-cli Specification

## Purpose

**Serves:** repos whose agents run in GitHub Copilot CLI.

How the plugin is offered, guarded and documented for GitHub Copilot CLI.

## Requirements

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

### Requirement: Listing for GitHub Copilot CLI

The plugin SHALL be listed for GitHub Copilot CLI with `copilot plugin marketplace add crisradu75/logic-artisan` followed by `copilot plugin install cla@cris-logic-artisan`, pinned to the same exact release tag as the Claude Code install.

#### Scenario: Both installs pin one release

- **WHEN** a release is published
- **THEN** the Copilot catalog and the Claude catalog name the same release tag

#### Scenario: A released plugin does not claim its own install is untested

- **WHEN** a reader checks what a release says about its own Copilot CLI install
- **THEN** it makes no claim that the install is untested, and the documentation carries the validation status

### Requirement: Documenting Copilot CLI validation status

Documentation for Copilot CLI SHALL identify the supported surface, the validated plugin
capabilities, and the behavior that remains unsupported or unverified.

#### Scenario: A reader checks the Copilot CLI installation

- **WHEN** a reader follows the Copilot CLI install guidance
- **THEN** it states that marketplace registration and browsing, installation, a skill invocation,
  and both helper-agent invocations were validated with Copilot CLI 1.0.105 and release
  `cla--v2.2.3`

#### Scenario: A reader checks Copilot support boundaries

- **WHEN** a reader checks which Copilot surfaces and plugin features are supported
- **THEN** the guidance says the scope is Copilot CLI only, describes the current source-tree
  `PreToolUse`/`PostToolUse` guard support and its fail-open timeout and autopilot-confirmation
  limitations, distinguishes those source changes from the tagged `cla--v2.2.3` release, and says
  Claude-specific skill tool instructions are not ported

#### Scenario: A reader checks the helper-agent model behavior

- **WHEN** a reader checks the current Copilot helper-agent profiles
- **THEN** the guidance discloses that Copilot CLI does not honor their declared model and falls
  back to `auto`

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
