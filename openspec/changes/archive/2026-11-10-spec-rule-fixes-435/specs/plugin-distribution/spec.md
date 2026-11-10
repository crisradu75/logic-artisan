## MODIFIED Requirements

### Requirement: Listing for GitHub Copilot CLI

The plugin SHALL be listed for GitHub Copilot CLI with `copilot plugin marketplace add crisradu75/logic-artisan` followed by `copilot plugin install cla@cris-logic-artisan`, pinned to the same exact release tag as the Claude Code install. A released plugin SHALL NOT claim that its own install is untested, because a release is never moved and the claim would outlive a change in support status.

#### Scenario: Both installs pin one release

- **WHEN** a release is published
- **THEN** the Copilot catalog and the Claude catalog name the same release tag

#### Scenario: A reader checks what a release says about itself

- **WHEN** a reader checks the description a release ships for Copilot CLI
- **THEN** it makes no claim that the install is untested, and the validation status is carried by the documentation instead
