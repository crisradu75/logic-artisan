## ADDED Requirements

### Requirement: A change keeps the repo's docs current

`/cla:spec-to-pr` and `/cla:lite-pr` SHALL report a repo document that still describes what a change altered as an Important finding, comparing the documents on the repo's doc list when it has one, and otherwise the documents a reader of the repo would open for that change.

#### Scenario: A listed doc the change leaves stale

- **WHEN** `/cla:spec-to-pr` opens a pull request that renames a flag a listed document still describes under its old name
- **THEN** the review of the pull request reports that document as an Important finding

#### Scenario: A small change

- **WHEN** `/cla:lite-pr` ships a change and a listed document still describes the old behaviour
- **THEN** its review reports that document as an Important finding

#### Scenario: A repo with no doc list

- **WHEN** a repo has no doc list and a change alters behaviour its README describes
- **THEN** the review judges the README one of the documents to compare
