## ADDED Requirements

### Requirement: A review round after a fix uses fresh reviewers

A skill that runs another pull-request review round after a fix SHALL dispatch new reviewers for it and SHALL never continue a reviewer from an earlier round; continuing an agent is only for correcting a reply within the same round.

#### Scenario: A second round after a protected-area fix

- **WHEN** the first round's fix touches a protected area and a second round runs
- **THEN** every reviewer in the second round is a new dispatch that has not seen the first round

#### Scenario: A correction inside the first round

- **WHEN** a first-round reviewer is asked again because it returned nothing
- **THEN** its reply counts toward the first round only, and the second round still dispatches new reviewers
