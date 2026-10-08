## REMOVED Requirements

### Requirement: Chain run notes ride the last open pull request

**Reason**: The owner decided on 2026-10-08 that chain run notes are local working state; committing them on a pull request kept growing machinery and still trusted anyone with push access.
**Migration**: None. Notes files a repo already tracks stay tracked; new ones are ignored.

## ADDED Requirements

### Requirement: Chain run notes stay local

`/cla:multi-lite` and `/cla:multi-pr` SHALL keep their run notes as local working state that no step adds, commits or pushes, and a resume that cannot find them SHALL fall back to the state of the pull requests on GitHub.

#### Scenario: A chain ends with a pull request open

- **WHEN** a chain finishes with some of its pull requests still open
- **THEN** its run notes stay uncommitted on the machine that ran it and no branch gets a notes commit

#### Scenario: Resuming where the notes are missing

- **WHEN** a chain is re-run on another machine, or after its notes file was deleted
- **THEN** it reads each change's state from GitHub instead
