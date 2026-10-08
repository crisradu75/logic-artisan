# change-workflow Specification

## Purpose

What the plugin promises when one change goes from a description to a reviewed, tested, opened pull request, and the authoring rules its specs follow.

## Requirements

### Requirement: A change becomes an opened pull request

`/cla:spec-to-pr` SHALL take a description, an existing change name, or nothing (using the conversation so far) and carry the change through its OpenSpec proposal, a review before implementation, implementation, tests, an opened pull request, review fixes on that pull request followed by a second review of those fixes unless `--pr-rounds` allows only one round, and archiving its specs into the live specs on the same pull request, without merging or deploying.

#### Scenario: From a description

- **WHEN** a user runs `/cla:spec-to-pr` with a description of a change
- **THEN** a pull request is opened holding the change's code, tests and updated live specs
- **AND** it is left open for the user to merge

#### Scenario: The first pull request review commits fixes

- **WHEN** the first review round on the pull request commits fixes and `--pr-rounds` allows a second round
- **THEN** a second round reviews those fixes before the run ends

### Requirement: Options for one change's run

`/cla:spec-to-pr` SHALL accept `--review-rounds N`, `--test-rounds N` and `--pr-rounds N` to cap the review before implementation, the test-fix rounds and the pull request review rounds, `--skip-review` to skip the pull request review, `--gate-on-push` or `--interactive` to pause before pushing, `--pr-base <branch>` to build on and open against another branch, `--narrow` for narrower permission rules, and `--dry-run` to run every check while writing nothing.

#### Scenario: Skipping the pull request review

- **WHEN** a user runs `/cla:spec-to-pr` with `--pr-rounds 0`
- **THEN** no review round runs on the opened pull request

#### Scenario: A dry run

- **WHEN** a user runs `/cla:spec-to-pr` with `--dry-run`
- **THEN** every check runs and no commit, push, pull request or file edit is made

### Requirement: Resuming a partly done change

Running `/cla:spec-to-pr` again on a change it has partly done SHALL resume at the first phase not yet done, including for a change with no design.md.

#### Scenario: A change with no design.md

- **WHEN** a change's proposal, specs and tasks are written, it has no design.md, and nothing is implemented yet
- **THEN** the run resumes at implementation

#### Scenario: Tasks not written yet

- **WHEN** a change's tasks are not written
- **THEN** implementation does not start

### Requirement: The run's report

A `/cla:spec-to-pr` run SHALL end with a report of each phase's outcome and every open issue, naming the merge command only when every phase passed and no review finding is left open, and SHALL add the review Suggestions it did not fix to the repo-root `TODO.md`.

#### Scenario: A finding left open

- **WHEN** a run ends with a Critical review finding still open
- **THEN** the report says the pull request is not ready to merge and names no merge command

### Requirement: A small change without OpenSpec

`/cla:lite-pr` SHALL take a small change from a description to an opened pull request with its docs and tests, one test pass and one review round with a single fix round, writing no OpenSpec change and editing a live spec only when an outcome or interface changes.

#### Scenario: A small fix

- **WHEN** a user runs `/cla:lite-pr` with a one-line description of a small fix
- **THEN** a reviewed pull request with the fix and its test is opened, with no OpenSpec change directory

### Requirement: Reviewing a change before implementation

`/cla:review-change <change>` SHALL check an OpenSpec change's claims and its file and symbol references against the repo, grade each finding Critical, Important or Suggestion, and end with a READY, FIX FIRST or RETHINK verdict.

#### Scenario: A claim the code contradicts

- **WHEN** a change says it mirrors an existing function and the function does something else
- **THEN** the review reports where the claim is wrong and does not return READY while that finding is Critical or Important

### Requirement: Specs follow the repo's authoring rules

Skills that write or review an OpenSpec change SHALL apply the `rules:` block in the repo's `openspec/config.yaml`, which the plugin seeds from its shipped `rules:` block to keep specs to outcomes and interfaces in short requirements.

#### Scenario: A requirement describing internal steps

- **WHEN** a change adds a requirement that describes how a skill sequences its own steps
- **THEN** `/cla:review-change` reports it as a finding

#### Scenario: A repo edits its rules

- **WHEN** a repo changes a rule in its `openspec/config.yaml`
- **THEN** the next change authored by the plugin follows the changed rule

### Requirement: Each requirement names its proof

Each requirement a change adds or modifies SHALL be proven by a test carrying a `requirement: <spec> / <heading>` comment line, or by a tasks.md line `manual: <heading>: <reason>`, and `/cla:review-change` SHALL report a requirement with neither as an Important finding.

#### Scenario: A requirement with no proof

- **WHEN** a change adds a requirement and its tasks name neither a test with the marker nor a `manual:` line
- **THEN** the review reports an Important finding naming the requirement

#### Scenario: A test task that names no marker

- **WHEN** a test task proves a requirement but does not name the marker its test will carry
- **THEN** the review reports a Suggestion, which does not block the verdict
