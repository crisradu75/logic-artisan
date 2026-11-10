# review-agents Specification

## Purpose

**Serves:** maintainers whose pull requests are reviewed by agents that can edit their working tree.

Defines how the plugin dispatches pull-request reviewers: the diff file they read, what their brief forbids, and the model each dispatch names.

## Requirements

### Requirement: A reviewer gets a diff file named in its brief

A skill that dispatches a pull-request reviewer SHALL save the change to a diff file outside the working tree and name that file in the reviewer's brief.

#### Scenario: A review round starts

- **WHEN** a skill dispatches reviewers for a pull request
- **THEN** each brief names a diff file

#### Scenario: The working tree after a review round

- **WHEN** a review round ends
- **THEN** no diff file is left in the working tree and none is committed

### Requirement: A reviewer makes no git or file changes

A skill that dispatches a pull-request reviewer SHALL tell the reviewer in its brief to run no git command and edit no file.

#### Scenario: A review round starts

- **WHEN** a skill dispatches reviewers for a pull request
- **THEN** each brief forbids git checkout, switch, stash, reset, clean, commit and branch and any file edit

### Requirement: A reviewer runs on a named model

A skill that dispatches a pull-request reviewer SHALL pass the reviewer's model on that dispatch.

#### Scenario: A review round starts

- **WHEN** a skill dispatches reviewers for a pull request
- **THEN** the dispatch names a model

#### Scenario: A high-risk change

- **WHEN** a pull request is judged high risk
- **THEN** the code reviewer and the silent-failure hunter both run on the stronger model the review-sizing guidance gives for high risk
