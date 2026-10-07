## MODIFIED Requirements

### Requirement: The review report carries no parallelism plan and no claim quota

A change review report SHALL NOT include an implementation-parallelism section and SHALL NOT require a minimum number of verified claims.

#### Scenario: A small change is reviewed

- **WHEN** a review report is printed
- **THEN** it has no implementation-parallelism section
- **AND** it does not pad its verified claims to reach a count
