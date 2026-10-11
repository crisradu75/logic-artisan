## REMOVED Requirements

### Requirement: A change becomes an opened pull request

**Migration**: Replaced by "A change becomes a risk-reviewed pull request". The second review round now depends on a fixed Critical finding, and the pull request body carries a risk line.

## ADDED Requirements

### Requirement: A change becomes a risk-reviewed pull request

`/cla:spec-to-pr` SHALL take a description, an existing change name, or nothing (using the conversation so far) and carry the change through its OpenSpec proposal, a review before implementation, implementation, tests, an opened pull request whose body states its risk, reason and reviewers, review fixes sized to that risk, a second review only after a fixed Critical finding unless `--pr-rounds` allows only one round, and archiving its specs on the same pull request, without merging or deploying.

#### Scenario: From a description

- **WHEN** a user runs `/cla:spec-to-pr` with a description of a change
- **THEN** a pull request is opened holding the change's code, tests and updated live specs
- **AND** its body states the risk level, the reason and the reviewers chosen
- **AND** it is left open for the user to merge

#### Scenario: The first review fixed only lesser findings

- **WHEN** the first review round on the pull request fixes Important or lesser findings and no Critical one
- **THEN** no second round runs and the run ends

#### Scenario: The first review fixed a Critical finding

- **WHEN** the first review round fixes a Critical finding and `--pr-rounds` allows a second round
- **THEN** a second round reviews those fixes before the run ends
