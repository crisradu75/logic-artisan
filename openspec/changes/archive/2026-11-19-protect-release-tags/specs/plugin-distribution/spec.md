## ADDED Requirements

### Requirement: A release is tagged before its catalogs name it

`/release` SHALL push the new tag on the release pull request's head commit and confirm the remote has it before merging that pull request with a merge commit, so the tagged commit is on the default branch, and SHALL restart as the next version, leaving the tag where it is, when the pull request needs another commit after the tag is pushed.

#### Scenario: The tag push fails

- **WHEN** the tag push to the remote is refused
- **THEN** the release pull request is not merged and the default branch's catalogs still name the previous tag

#### Scenario: The release merges

- **WHEN** the tag is on the remote and the release pull request is merged
- **THEN** the tagged commit is on the default branch

#### Scenario: The release pull request needs another commit

- **WHEN** the release pull request needs another commit after the tag was pushed
- **THEN** the tag stays where it is and the release starts again as the next version
