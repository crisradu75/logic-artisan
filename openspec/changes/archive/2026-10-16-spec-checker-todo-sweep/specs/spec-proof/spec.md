## MODIFIED Requirements

### Requirement: A checker reports requirements with no proof

`check_spec_proof.py` SHALL, without editing anything, report each requirement a branch adds or changes that has neither a `requirement: <spec> / <heading>` test marker nor a `manual: <spec> / <heading>: <reason>` tasks.md line, and exit non-zero when it finds one.

#### Scenario: A new requirement with no proof

- **WHEN** a branch adds a requirement and no test or tasks line names it
- **THEN** the checker names the requirement and exits non-zero

#### Scenario: A heading rename

- **WHEN** a branch only renames a requirement's heading
- **THEN** the checker does not ask for new proof

#### Scenario: No default branch to compare with

- **WHEN** the default branch cannot be found
- **THEN** the checker says it skipped the changed-requirement rule and runs its other rules

### Requirement: A checker reports specs a declared map leaves out and links that point nowhere

Once a repo declares a spec map, `check_spec_proof.py` SHALL report as problems, exiting non-zero, each spec that is live or added by a change in progress, and that no change in progress removes, that no map file links, each map link that points at a spec that does not exist, and each declared path that matches no Markdown file.

#### Scenario: A spec no map links

- **WHEN** a map is declared and a spec is linked from none of its files
- **THEN** the checker names that spec and exits non-zero

#### Scenario: A link to a missing spec

- **WHEN** a map file links a spec that no live spec matches
- **THEN** the checker names the map file and the link and exits non-zero

#### Scenario: A declared path that matches nothing

- **WHEN** a declared path matches no Markdown file in the repo
- **THEN** the checker names that path and exits non-zero

## ADDED Requirements

### Requirement: A manual line names its spec, and the older form still counts

A `manual: <spec> / <heading>: <reason>` line in a change's tasks.md SHALL cover that heading in that spec only, and the older `manual: <heading>: <reason>` line SHALL keep covering the heading in every spec of its change, with a `NOTE` suggesting the new form that leaves the exit code unchanged.

#### Scenario: Two specs share a heading

- **WHEN** a change alters the same heading in two specs and one `manual:` line names only the first spec
- **THEN** the checker reports the second spec's requirement as having no proof

#### Scenario: An older line

- **WHEN** a change in progress carries `manual: <heading>: <reason>`
- **THEN** it covers the heading as before, and the checker prints a `NOTE` and keeps its exit code
