## ADDED Requirements

### Requirement: A checker notes a touched spec's Purpose without failing the run

`check_spec_proof.py` SHALL print an advisory `NOTE purpose:` line for each live spec whose Purpose is missing, TBD, or not a `**Serves:**` line followed by exactly one sentence, limited to the specs the branch touches (every live spec when there is no base commit to compare with), never changing its exit code, and SHALL print a `purpose notes:` line saying which it checked.

#### Scenario: A touched spec with a plain Purpose

- **WHEN** a branch edits a live spec whose Purpose has no `**Serves:**` line
- **THEN** the checker prints a `NOTE purpose:` line for it and its exit code is unchanged

#### Scenario: An untouched spec with a plain Purpose

- **WHEN** a live spec has a plain Purpose and the branch changes nothing under that spec
- **THEN** the checker prints no `NOTE purpose:` line for it

#### Scenario: No base commit to compare with

- **WHEN** the checker has no base commit, so it cannot tell which specs the branch touches
- **THEN** it notes every live spec and its `purpose notes:` line says so
