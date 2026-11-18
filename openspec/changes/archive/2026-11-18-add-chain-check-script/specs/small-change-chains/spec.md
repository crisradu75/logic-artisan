# Spec Delta

## ADDED Requirements

### Requirement: A small change runs only after the changes it depends on merged

Before a `/cla:multi-lite` candidate with dependencies runs, the chain check's `deps` SHALL exit 0 only when the run notes record every dependency as merged with a merge commit the base holds, and SHALL exit 1 naming each dependency that is not, so the candidate is skipped.

#### Scenario: A dependency left open

- **WHEN** a candidate depends on one whose pull request the run left open
- **THEN** `deps` exits 1 naming that dependency and the candidate does not run

#### Scenario: A merge commit the base does not hold

- **WHEN** a dependency is recorded as merged but its merge commit is not in the base
- **THEN** `deps` exits 1 naming that dependency
