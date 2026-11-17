# plugin-release

## Purpose

**Serves:** the owner, who releases the plugin, and the sessions that install it. It keeps what ships small and self-contained, and tied to the release tag it was cut from.

## ADDED Requirements

### Requirement: Release pointer names a tag
The marketplace SHALL install the plugin from a named release tag, and the plugin version recorded at that tag SHALL equal the version in the tag's name.

#### Scenario: Pointer matches its tag
- **GIVEN** the marketplace pointer names tag `mnemo--v0.1.1`, and the plugin manifest at that tag says `0.1.1`
- **WHEN** the plugin's tests run
- **THEN** the release-pointer test passes

#### Scenario: Version at the tag disagrees
- **GIVEN** the pointer names a tag whose plugin manifest records a different version
- **WHEN** the plugin's tests run
- **THEN** the release-pointer test fails and names both versions

#### Scenario: No tag to check
- **GIVEN** the pointer has no tag, or names a tag missing from the local clone
- **WHEN** the plugin's tests run
- **THEN** the release-pointer test fails, saying what is missing, rather than skipping

### Requirement: Pointer never ahead of the code
The plugin version on the branch SHALL never be lower than the version the release pointer names.

#### Scenario: Branch behind the pointer
- **GIVEN** a pointer naming a version higher than the branch's plugin manifest
- **WHEN** the plugin's tests run
- **THEN** the release-pointer test fails

### Requirement: Packaged paths exist
Every plugin-root path that a skill file or hook file in the plugin names SHALL exist in the packaged plugin folder.

#### Scenario: Missing referenced file
- **GIVEN** a skill or hook file that names a plugin-root path that is not in the packaged plugin
- **WHEN** the plugin's tests run
- **THEN** the packaged-path test fails and names the file and the path

#### Scenario: Scanner finds references
- **GIVEN** a test copy of the plugin with one skill file naming an existing plugin-root path
- **WHEN** the packaged-path test scans it
- **THEN** it finds that reference, so a scan that finds nothing cannot pass by accident

### Requirement: Tests stay out of the plugin
Nothing from the repo's tests or evals SHALL sit inside the packaged plugin folder.

#### Scenario: Test file inside the plugin
- **GIVEN** a test module or test fixture placed inside the packaged plugin folder
- **WHEN** the plugin's tests run
- **THEN** the packaging test fails and names the file

### Requirement: Standard library only
The plugin's scripts SHALL run on a plain Python 3 install, importing only the Python standard library.

#### Scenario: Third-party import
- **GIVEN** a plugin script that imports a module outside the standard library
- **WHEN** the plugin's tests run
- **THEN** the import test fails and names the script and the module

### Requirement: Nothing runs on GitHub
The repo SHALL hold no GitHub workflow, so no check or other job runs on GitHub's machines.

#### Scenario: Workflow added
- **GIVEN** a workflow file added under the repo's GitHub workflows folder
- **WHEN** the plugin's tests run
- **THEN** the no-workflow test fails and names the file

### Requirement: Shared files exist once
The base schema and the check command SHALL each exist exactly once in the packaged plugin, and the check command SHALL be the only file in the plugin's scripts folder.

#### Scenario: Second copy of the base schema
- **GIVEN** a second copy of the base schema placed elsewhere in the plugin
- **WHEN** the plugin's tests run
- **THEN** the shared-file test fails and names both paths

#### Scenario: Second script beside the check command
- **GIVEN** another file added to the plugin's scripts folder
- **WHEN** the plugin's tests run
- **THEN** the shared-file test fails and names the file
