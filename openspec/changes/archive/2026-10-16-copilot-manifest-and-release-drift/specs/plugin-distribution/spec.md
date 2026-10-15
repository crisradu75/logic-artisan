## ADDED Requirements

### Requirement: Installing from GitHub Copilot CLI

The plugin SHALL be listed for GitHub Copilot CLI with `copilot plugin marketplace add crisradu75/logic-artisan` followed by `copilot plugin install cla@cris-logic-artisan`, pinned to the same exact release tag as the Claude Code install, and every document offering it SHALL say it covers Copilot CLI only and is untested in a live Copilot CLI.

#### Scenario: Both installs pin one release

- **WHEN** a release is published
- **THEN** the Copilot catalog and the Claude catalog name the same release tag

#### Scenario: A reader looks for the Copilot install

- **WHEN** a reader opens the install instructions
- **THEN** they say the Copilot install is Copilot CLI only and untested

## MODIFIED Requirements

### Requirement: What a release contains

A published release SHALL contain only what a consuming repo uses: the skills, agents, guard hooks, output styles, the scripts they run, and the plugin's manifests and README, with no tests.

#### Scenario: Listing an installed release

- **WHEN** the files of an installed release are listed
- **THEN** none of them is a test, a test configuration or a test fixture

### Requirement: Publishing a release

In the source repo, `/release` SHALL bump the version in the Claude plugin manifest, the Copilot plugin manifest, both marketplace catalogs and the release note in one commit and cut the matching `cla--v<version>` tag, only from a clean, up-to-date default branch with passing tests, refusing and naming every file when the plugin directory holds a file a consuming repo cannot use.

#### Scenario: A development file inside the plugin blocks the release

- **WHEN** a test file is tracked inside the plugin directory
- **THEN** `/release` stops, names every such file, and cuts no tag

#### Scenario: A published tag is never moved

- **WHEN** a published release needs a correction
- **THEN** the correction ships as a new version and the published tag stays where it is

#### Scenario: A manifest names a different version

- **WHEN** either manifest, either catalog or the release note names a version the others do not
- **THEN** the test suite fails
