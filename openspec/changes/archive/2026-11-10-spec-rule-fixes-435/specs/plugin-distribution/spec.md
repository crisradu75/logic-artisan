## MODIFIED Requirements

### Requirement: Listing for GitHub Copilot CLI

The plugin SHALL be listed for GitHub Copilot CLI with `copilot plugin marketplace add crisradu75/logic-artisan` followed by `copilot plugin install cla@cris-logic-artisan`, pinned to the same exact release tag as the Claude Code install.

#### Scenario: Both installs pin one release

- **WHEN** a release is published
- **THEN** the Copilot catalog and the Claude catalog name the same release tag

#### Scenario: A released plugin does not claim its own install is untested

- **WHEN** a reader checks what a release says about its own Copilot CLI install
- **THEN** it makes no claim that the install is untested, and the documentation carries the validation status
