# review-agents Specification

## Purpose

**Serves:** maintainers who want pull-request reviews from the plugin's own reviewers.

Defines the pull-request reviewers the plugin ships itself: what they may do, how they receive the change they review, and how review sizing names them.

## Requirements

### Requirement: The plugin ships its own read-only reviewers

The plugin SHALL ship a code reviewer, a silent-failure hunter and a comment reviewer. Each names its default model in its own definition, and none of them can edit a file or run a command.

#### Scenario: A reviewer tries to change the tree

- **WHEN** a shipped reviewer is dispatched to review a pull request
- **THEN** it can read and search files but has no tool that edits a file or runs a command

#### Scenario: A reviewer is dispatched with no model named

- **WHEN** a skill dispatches a shipped reviewer without naming a model
- **THEN** the reviewer runs on the model its definition names

### Requirement: A reviewer reads the change from a diff file

A skill that dispatches a shipped reviewer SHALL first write the change under review to a diff file outside the working tree and name that file in the reviewer's brief. The reviewer SHALL read the change from that file and not run any command.

#### Scenario: Reviewing a pull request

- **WHEN** a pull request's review round starts
- **THEN** each shipped reviewer's brief names a diff file holding the change, and the reviewer's findings cite lines from it

#### Scenario: The working tree after a review round

- **WHEN** a review round ends
- **THEN** no diff file is left in the working tree and none is committed

### Requirement: Review sizing names each reviewer it uses

The review-sizing guidance SHALL name each shipped reviewer it assigns by its agent definition. Each risk tier SHALL run its reviewers on the model the guidance gives for that tier.

#### Scenario: A low-risk code change

- **WHEN** a pull request is judged low risk and changes code
- **THEN** the shipped code reviewer runs on the model its definition names

#### Scenario: A high-risk change

- **WHEN** a pull request is judged high risk
- **THEN** the shipped code reviewer and silent-failure hunter both run on the stronger model the guidance gives for high risk
