## ADDED Requirements

### Requirement: A spec a change in progress removes is gone for the map rule

A spec whose every requirement a change in progress removes, with none added or modified, SHALL count as gone for the spec map rule: the change may drop its map link and pass, and a map link that stays is reported as a problem.

#### Scenario: The link goes with the spec

- **WHEN** a change removes every requirement of a spec and drops that spec's map link
- **THEN** the checker reports no unlinked spec for it

#### Scenario: The link stays

- **WHEN** a change removes every requirement of a spec and a map file still links it
- **THEN** the checker names the link and exits non-zero
