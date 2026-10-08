## MODIFIED Requirements

### Requirement: A change becomes an opened pull request

`/cla:spec-to-pr` SHALL take a description, an existing change name, or nothing (using the conversation so far) and carry the change through its OpenSpec proposal, a review before implementation, implementation, tests, an opened pull request, review fixes on that pull request followed by a second review of those fixes unless `--pr-rounds` allows only one round, and archiving its specs into the live specs on the same pull request, without merging or deploying.

#### Scenario: From a description

- **WHEN** a user runs `/cla:spec-to-pr` with a description of a change
- **THEN** a pull request is opened holding the change's code, tests and updated live specs
- **AND** it is left open for the user to merge

#### Scenario: The first pull request review commits fixes

- **WHEN** the first review round on the pull request commits fixes and `--pr-rounds` allows a second round
- **THEN** a second round reviews those fixes before the run ends
