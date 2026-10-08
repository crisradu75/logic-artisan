## MODIFIED Requirements

### Requirement: A later change is held to what an earlier one owes it

When an earlier change in a `/cla:multi-pr` chain adds a field or behaviour for a later change, the later change's review SHALL report each such obligation the later change ignores, the later change SHALL not count as ready while one is ignored, and a resumed chain that cannot read those obligations SHALL stop before starting the later change.

#### Scenario: A field the later change ignores

- **WHEN** a later change's artifacts never mention a field an earlier change added for it
- **THEN** its review reports the ignored obligation and the change is not ready

#### Scenario: Resuming without the run notes

- **WHEN** a chain is resumed where its run notes are missing and a change still to run comes after another change in the chain
- **THEN** the chain stops before that change and says how to go on
