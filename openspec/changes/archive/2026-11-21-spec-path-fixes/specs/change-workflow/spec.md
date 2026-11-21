## ADDED Requirements

### Requirement: A protected change records its rejected alternatives

`/cla:spec-to-pr` SHALL ask that a change touching a protected area list its rejected alternatives in its design document, one line each, where `none considered` is a valid entry.

#### Scenario: A change touching a protected area

- **WHEN** the change touches a protected area
- **THEN** its design lists the rejected alternatives, one line each, or says `none considered`

### Requirement: A build that departs from the spec updates the spec

When the build departs from a requirement on purpose, `/cla:spec-to-pr` SHALL edit the change's delta spec in the same commit and re-run strict validation of the change.

#### Scenario: The build changes course

- **WHEN** the implementation departs from a requirement on purpose
- **THEN** the delta spec is edited in the same commit and the change is validated again

### Requirement: The pull request body is current after the review rounds

After the review fix rounds, `/cla:spec-to-pr` SHALL check that the pull request body still describes the branch and that its `Risk:` and `Checks:` clauses are current, updating only those clauses of the one-liner and keeping the rest of it, including any stacked-on and closing parts, as written, with no log of the review.

#### Scenario: A fix round changed the risk level

- **WHEN** a review fix round changed the risk level or the checks that ran
- **THEN** the `Risk:` and `Checks:` clauses say so and the rest of the body is unchanged
