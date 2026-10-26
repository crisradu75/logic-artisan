# Spec Delta

## ADDED Requirements

### Requirement: A reviewer is dispatched with a diff file, a ban on state changes and a named model

A skill that dispatches a pull-request reviewer SHALL save the change to a diff file outside the working tree, name that file in the reviewer's brief, tell the reviewer in that brief to run no git command and edit no file, and pass the reviewer's model on that dispatch.

#### Scenario: A review round starts

- **WHEN** a skill dispatches reviewers for a pull request
- **THEN** each brief names a diff file, forbids git checkout, switch, stash, reset, clean, commit and branch and any file edit, and the dispatch names a model

#### Scenario: A high-risk change

- **WHEN** a pull request is judged high risk
- **THEN** the code reviewer and the silent-failure hunter both run on the stronger model the review-sizing guidance gives for high risk

#### Scenario: The working tree after a review round

- **WHEN** a review round ends
- **THEN** no diff file is left in the working tree and none is committed

## REMOVED Requirements

### Requirement: The plugin ships its own read-only reviewers

**Reason**: The plugin no longer ships reviewers; it dispatches the `pr-review-toolkit` ones, which it already requires, and states the dispatch rule in the added requirement.
**Migration**: Reviewers come from `pr-review-toolkit`. Their tool list is not read-only, so the added requirement is the only safeguard against a state-changing command.

### Requirement: A reviewer reads the change from a diff file

**Reason**: Replaced by the added requirement, which keeps the diff file and adds the ban on git commands and file edits that a reviewer with a shell needs.
**Migration**: None; the diff-file step is unchanged.

### Requirement: Review sizing names each reviewer it uses

**Reason**: It tied the sizing table to agent files the plugin no longer has. The risk tiers and their models stay in the sizing guidance, and the added requirement says the model is passed on every dispatch.
**Migration**: None; the sizing table and its rows are unchanged.
