## REMOVED Requirements

### Requirement: Disclosing the Copilot CLI install is untested

Every document offering the Copilot CLI install, except the manifest shipped inside a release tag,
SHALL say, beside the install command, that it covers Copilot CLI only and is untested in a live
Copilot CLI. The manifest shipped inside a release tag SHALL NOT say the install is untested.

#### Scenario: A reader looks for the Copilot install

- **WHEN** a reader opens the install instructions
- **THEN** they say the Copilot install is Copilot CLI only and untested

#### Scenario: The disclosure sits in another section

- **WHEN** a document gives the install command and says it is untested only in a different section
- **THEN** the test suite fails

#### Scenario: The shipped manifest is read

- **WHEN** the description in the plugin's Copilot manifest is read
- **THEN** it does not say the install is untested

## ADDED Requirements

### Requirement: Documenting Copilot CLI support status

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
