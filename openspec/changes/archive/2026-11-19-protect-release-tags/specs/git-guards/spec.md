## ADDED Requirements

### Requirement: A push that deletes or moves a tag on the remote is refused

The `pre-push` hook SHALL refuse a push that deletes any tag on the remote or points a tag the remote already has at a different object, naming the `ALLOW_TAG_REWRITE=1` override in its message, SHALL let a push that creates a new tag through, and setting `ALLOW_TAG_REWRITE=1` SHALL lift only this refusal.

#### Scenario: Deleting a tag

- **WHEN** a push from a clone with the hook installed would delete a tag on the remote
- **THEN** git refuses the push and the message names `ALLOW_TAG_REWRITE=1`

#### Scenario: Moving a tag

- **WHEN** a forced push would point a tag the remote already has at another commit or tag object
- **THEN** git refuses the push and the remote tag stays where it was

#### Scenario: A new tag

- **WHEN** a push creates a tag the remote does not have
- **THEN** the push goes through
