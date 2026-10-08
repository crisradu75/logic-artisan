# plugin-distribution Specification

## Purpose

How a repo installs the `cla` plugin, what a release contains, and how releases are published.

## Requirements

### Requirement: Installing a pinned release

The plugin SHALL install into a repo with `claude plugin marketplace add crisradu75/logic-artisan` followed by `claude plugin install cla@cris-logic-artisan`, giving the release the marketplace pins to an exact `cla--v<version>` tag, and a newer release on `/plugin marketplace update`.

#### Scenario: A fresh install

- **WHEN** a repo runs the two install commands
- **THEN** the plugin's skills, agents and guard hooks are available in that repo's sessions
- **AND** the installed version is the one the pinned tag names

### Requirement: Skills are invoked under the cla namespace

Every skill the plugin ships SHALL be invocable as `/cla:<skill>`, and the skills that open or merge pull requests unattended, or that are meant to be run deliberately, SHALL start only when invoked by name.

#### Scenario: Invoking a skill by name

- **WHEN** a user types `/cla:spec-to-pr` in a repo with the plugin installed
- **THEN** the spec-to-pr skill runs

#### Scenario: An unattended chain is not started from plain words

- **WHEN** a user asks in plain words to run every open change
- **THEN** `/cla:multi-pr` does not start until the user invokes it by name

### Requirement: Repo data stays in the repo

The plugin SHALL keep every repo-specific fact, setting and run record in the consuming repo's `cla.io/` directory and never write to its own installed files, and installing or updating the plugin SHALL leave `cla.io/` untouched.

#### Scenario: Updating the plugin

- **WHEN** a repo with a populated `cla.io/` updates the plugin to a newer release
- **THEN** every file under `cla.io/` is unchanged

### Requirement: What a release contains

A published release SHALL contain only what a consuming repo uses: the skills, agents, guard hooks, output styles, the scripts they run, and the plugin's manifest and README, with no tests.

#### Scenario: Listing an installed release

- **WHEN** the files of an installed release are listed
- **THEN** none of them is a test, a test configuration or a test fixture

### Requirement: Publishing a release

In the source repo, `/release` SHALL bump the version in the plugin manifest, the marketplace entry and the release note in one commit and cut the matching `cla--v<version>` tag, only from a clean, up-to-date default branch with passing tests, refusing and naming every file when the plugin directory holds a file a consuming repo cannot use.

#### Scenario: A development file inside the plugin blocks the release

- **WHEN** a test file is tracked inside the plugin directory
- **THEN** `/release` stops, names every such file, and cuts no tag

#### Scenario: A published tag is never moved

- **WHEN** a published release needs a correction
- **THEN** the correction ships as a new version and the published tag stays where it is
