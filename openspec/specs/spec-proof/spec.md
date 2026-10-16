# spec-proof Specification

## Purpose

**Serves:** maintainers who need each changed requirement tied to a test or a manual note.

Defines the shipped checker that ties each changed requirement to its proof, and how a repo chooses whether proof is per requirement or per scenario.

## Requirements

### Requirement: A checker reports requirements with no proof

`check_spec_proof.py` SHALL, without editing anything, report each requirement a branch adds or changes that has neither a `requirement: <spec> / <heading>` test marker nor a `manual: <heading>: <reason>` tasks.md line, and exit non-zero when it finds one.

#### Scenario: A new requirement with no proof

- **WHEN** a branch adds a requirement and no test or tasks line names it
- **THEN** the checker names the requirement and exits non-zero

#### Scenario: A heading rename

- **WHEN** a branch only renames a requirement's heading
- **THEN** the checker does not ask for new proof

#### Scenario: No default branch to compare with

- **WHEN** the default branch cannot be found
- **THEN** the checker says it skipped the changed-requirement rule and runs its other rules

### Requirement: A checker reports proof that points at nothing

`check_spec_proof.py` SHALL report a marker or `manual:` line naming a spec or heading that does not exist, a heading repeated within one spec, and a repo with no specs at all, so a misconfigured run never passes silently.

#### Scenario: A dangling marker

- **WHEN** a test carries a marker naming a requirement that no spec holds
- **THEN** the checker names the marker's file and exits non-zero

#### Scenario: An empty corpus

- **WHEN** the checker finds no spec files
- **THEN** it exits non-zero and says no specs were found

### Requirement: A repo chooses proof per requirement or per scenario

A repo SHALL choose its proof granularity with the line `- Test proof granularity: requirement` or `- Test proof granularity: scenario` in `cla.io/project-facts.md`; with no such line the checker uses requirement, and with a malformed or repeated line it exits non-zero naming the line.

#### Scenario: A repo opts in to scenarios

- **WHEN** the facts file says `scenario` and a changed scenario has no per-scenario marker
- **THEN** the checker reports that scenario

#### Scenario: A malformed value

- **WHEN** the facts file says `Test proof granularity: per-scenario`
- **THEN** the checker exits non-zero and names the line and the two accepted values

### Requirement: Half-proven and waiting requirements are counted apart

A requirement proven partly by a test and partly by a prompt SHALL carry a marker and a `manual:` line ending `(prompt half)`; one proven by a later change SHALL carry a `waiting: <heading>: <reason>` line, which the checker counts apart and reports once its change is archived.

#### Scenario: A prompt half without a test

- **WHEN** a requirement has a `(prompt half)` line and no marker
- **THEN** the checker reports it

#### Scenario: A waiting line in an archived change

- **WHEN** an archived change still holds a `waiting:` line
- **THEN** the checker reports it

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
