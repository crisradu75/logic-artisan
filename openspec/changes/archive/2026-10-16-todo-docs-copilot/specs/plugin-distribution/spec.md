## ADDED Requirements

### Requirement: Listing for GitHub Copilot CLI

The plugin SHALL be listed for GitHub Copilot CLI with `copilot plugin marketplace add crisradu75/logic-artisan` followed by `copilot plugin install cla@cris-logic-artisan`, pinned to the same exact release tag as the Claude Code install.

#### Scenario: Both installs pin one release

- **WHEN** a release is published
- **THEN** the Copilot catalog and the Claude catalog name the same release tag

### Requirement: Disclosing the Copilot CLI install is untested

Every document offering the Copilot CLI install, except the manifest shipped inside a release tag, SHALL say, beside the install command, that it covers Copilot CLI only and is untested in a live Copilot CLI.

#### Scenario: A reader looks for the Copilot install

- **WHEN** a reader opens the install instructions
- **THEN** they say the Copilot install is Copilot CLI only and untested

#### Scenario: The disclosure sits in another section

- **WHEN** a document gives the install command and says it is untested only in a different section
- **THEN** the test suite fails

#### Scenario: The shipped manifest is read

- **WHEN** the description in the plugin's Copilot manifest is read
- **THEN** it does not say the install is untested

## REMOVED Requirements

### Requirement: Installing from GitHub Copilot CLI

**Reason**: It joined two outcomes, the install line and the disclosure duty.

**Migration**: "Listing for GitHub Copilot CLI" holds the install line and "Disclosing the Copilot CLI install is untested" holds the duty.
