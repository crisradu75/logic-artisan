# Spec Delta

## ADDED Requirements

### Requirement: A catalog never names a missing tag

`/release` SHALL refuse to start while either marketplace catalog names a release tag the remote does not have, and SHALL NOT report a release as done until every catalog's tag is on the remote; a remote that cannot be asked SHALL count as a failure, never a pass.

#### Scenario: An earlier release was merged but never tagged

- **WHEN** `/release` starts and a catalog names a tag the remote does not have
- **THEN** it stops, names the catalog and the tag, and edits nothing

#### Scenario: The tag push did not reach the remote

- **WHEN** the release commit is merged and the new tag exists only in the local clone
- **THEN** `/release` reports the release as not done and names the missing tag

#### Scenario: The remote does not answer

- **WHEN** the remote cannot be reached while the tags are checked
- **THEN** the check fails as not checked, and the release is not reported done
