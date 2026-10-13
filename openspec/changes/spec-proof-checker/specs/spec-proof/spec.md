# Spec Delta

## Purpose

Defines the shipped checker that ties each changed requirement to its proof, and how a repo chooses whether proof is per requirement or per scenario.

## ADDED Requirements

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

- **WHEN** the facts file says `scenario` and a changed scenario has no `scenario: <spec> / <heading>` marker
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
