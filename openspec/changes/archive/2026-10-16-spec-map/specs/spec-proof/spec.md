## ADDED Requirements

### Requirement: A checker reports specs a declared map leaves out and links that point nowhere

Once a repo declares a spec map, `check_spec_proof.py` SHALL report as problems, exiting non-zero, each spec, live or added by a change in progress, that no map file links, each map link that points at a spec that does not exist, and each declared path that matches no file.

#### Scenario: A spec no map links

- **WHEN** a map is declared and a spec is linked from none of its files
- **THEN** the checker names that spec and exits non-zero

#### Scenario: A link to a missing spec

- **WHEN** a map file links a spec that no live spec matches
- **THEN** the checker names the map file and the link and exits non-zero

#### Scenario: A declared path that matches nothing

- **WHEN** a declared path matches no file in the repo
- **THEN** the checker names that path and exits non-zero
