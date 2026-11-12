# Spec Delta

## ADDED Requirements

### Requirement: Copilot helper-agent profiles inherit the session model

Generated Copilot helper-agent profiles SHALL omit account-specific model identifiers so they inherit the active Copilot CLI session model.

#### Scenario: A Copilot helper agent uses the active session model

- **WHEN** a helper agent is invoked in Copilot CLI
- **THEN** its generated profile has no account-specific model identifier and uses the active session model

### Requirement: Copilot helper-agent profiles are validated locally

The local release check SHALL reject unmapped source aliases, stale generated profiles, or explicit Copilot model pins.

#### Scenario: The local release check finds a profile mismatch

- **WHEN** a source alias is unmapped, a generated profile is stale, or a Copilot model pin is present
- **THEN** the release check fails with a diagnostic

## MODIFIED Requirements

### Requirement: Documenting Copilot CLI validation status

Documentation for Copilot CLI SHALL identify the supported surface, the validated plugin capabilities, and behavior that remains unsupported or unverified, and SHALL provide installation, update, troubleshooting, and repository-instruction setup guidance.

#### Scenario: A reader checks the Copilot CLI installation

- **WHEN** a reader follows the Copilot CLI install guidance
- **THEN** it states the marketplace registration, browsing, installation, update, and troubleshooting steps, and explains how to copy the response style to `.github/copilot-instructions.md` and refresh it after plugin updates

#### Scenario: A reader checks Copilot support boundaries

- **WHEN** a reader checks which Copilot surfaces and plugin features are supported
- **THEN** the guidance says the scope is Copilot CLI only, describes source-tree `PreToolUse`/`PostToolUse` guard support and its fail-open timeout and autopilot-confirmation limitations, distinguishes source-tree validation from tagged-release validation, warns against unresolved `${CLAUDE_PLUGIN_ROOT}` references, and marks workflows requiring Claude-only delegation, chaining, model routing, or permission settings unsupported

#### Scenario: A reader checks the helper-agent model behavior

- **WHEN** a reader checks the current Copilot helper-agent profiles
- **THEN** the guidance says they inherit the active session model because profiles omit account-specific model identifiers
