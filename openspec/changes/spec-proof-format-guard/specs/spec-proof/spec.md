## ADDED Requirements

### Requirement: A checker reports specs over the repo's format limits

`check_spec_proof.py` SHALL report a requirement statement longer than, a requirement with more scenarios than, and a spec with more requirements than, the limits written in the repo's `openspec/config.yaml` spec rules, reading those numbers from that file, and SHALL say which limit it could not find and so did not enforce.

#### Scenario: A requirement with too many scenarios

- **WHEN** a live spec holds a requirement with more scenarios than the config allows
- **THEN** the checker names the spec and requirement and exits non-zero

#### Scenario: A repo with different limits

- **WHEN** the config allows 5 scenarios and a requirement has 4
- **THEN** the checker reports nothing for it

#### Scenario: A limit the config does not state

- **WHEN** the config states no requirement-count limit
- **THEN** the checker enforces the other limits and says it did not enforce that one
