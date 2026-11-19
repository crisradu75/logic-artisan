# project-review Specification

## Purpose

**Serves:** maintainers who want a whole-repo assessment before a demo or a release.

How the project-review skill checks, reviews and grades a repo without changing it.

## Requirements

### Requirement: Baseline checks run before any reviewer

`/cla:project-review` SHALL run the repo's build, lint and test commands from its facts before dispatching any reviewer, record a suite the repo leaves out of its aggregate as skipped, and give every reviewer the results as pre-verified facts.

#### Scenario: A failing build

- **WHEN** the build fails
- **THEN** the failure is printed at once and every reviewer receives it in the baseline table

### Requirement: Five dimension reviews run at once

`/cla:project-review` SHALL dispatch five reviewers concurrently in one message, one each for vision, structure, requirements and specs, architecture and validation, with the vision and architecture reviewers on the strongest model and the other three a tier below.

#### Scenario: A full review

- **WHEN** the baseline checks are done
- **THEN** all five reviewers start together, not one after another

### Requirement: The verdict follows the grades

`/cla:project-review` SHALL leave not-applicable dimensions out and give NEEDS WORK for two or more D grades or more than half C or D, EXEMPLARY for all A or B, STRONG for no D and at most one C, and SOLID otherwise, taking the first row that matches.

#### Scenario: One D among five

- **WHEN** the grades are A, A, B, B, D
- **THEN** the verdict is SOLID

### Requirement: A project review changes nothing

`/cla:project-review` SHALL read the repo and run its checks and SHALL NOT edit a tracked file or keep state between runs, printing its report as the whole output.

#### Scenario: A finished review

- **WHEN** a review ends
- **THEN** the repo's tracked files are as they were and no ledger or report file is written
