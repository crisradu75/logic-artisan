## MODIFIED Requirements

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
