## MODIFIED Requirements

### Requirement: Direct pushes to main are refused

The plugin SHALL ship a git `pre-push` hook that, once copied into a clone's `.git/hooks/`, refuses any push that updates or deletes `main` or `master` on the remote, from any tool, unless `ALLOW_PUSH_TO_MAIN=1` is set; a deletion git does not report to the hook, as in a mirror push, is outside what it can refuse.

#### Scenario: Pushing to main

- **WHEN** a push from a clone with the hook installed would update the remote's `main`
- **THEN** git refuses the push and suggests a branch and a pull request

#### Scenario: An emergency override

- **WHEN** the push is run with `ALLOW_PUSH_TO_MAIN=1`
- **THEN** the push goes through

### Requirement: A push to the remote's own default branch is refused

The `pre-push` hook SHALL also refuse a push that updates or deletes the branch the remote names as its default, whatever its name, unless `ALLOW_PUSH_TO_MAIN=1` is set; a deletion git does not report to the hook, as in a mirror push, is outside what it can refuse.

#### Scenario: A default branch that is not main

- **WHEN** the remote's default branch is `develop` and a push would update it
- **THEN** git refuses the push

#### Scenario: A remote with no recorded default

- **WHEN** the remote has no recorded default branch and a push would update `develop`
- **THEN** the push goes through, while a push to `main` is still refused

### Requirement: A push that deletes or moves a tag on the remote is refused

The `pre-push` hook SHALL refuse a push that deletes a tag on the remote or points a tag the remote already has at a different object, naming the `ALLOW_TAG_REWRITE=1` override in its message, SHALL let a push that creates a new tag through, and setting `ALLOW_TAG_REWRITE=1` SHALL lift only this refusal; a deletion git does not report to the hook, as in a mirror push, is outside what it can refuse.

#### Scenario: Deleting a tag

- **WHEN** a push from a clone with the hook installed would delete a tag on the remote
- **THEN** git refuses the push and the message names `ALLOW_TAG_REWRITE=1`

#### Scenario: Moving a tag

- **WHEN** a forced push would point a tag the remote already has at another commit or tag object
- **THEN** git refuses the push and the remote tag stays where it was

#### Scenario: A new tag

- **WHEN** a push creates a tag the remote does not have
- **THEN** the push goes through
