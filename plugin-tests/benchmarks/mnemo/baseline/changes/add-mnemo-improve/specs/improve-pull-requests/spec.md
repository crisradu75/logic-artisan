# improve-pull-requests

## Purpose

**Serves:** the owner, who reviews and merges every change the loop makes to a domain. It sets which pull requests a run opens, what each one holds, and what must pass before one is pushed.

## ADDED Requirements

### Requirement: One domain pull request for content changes
A run SHALL put all its proposed changes to notes and to the domain's conventions file, other than rules that steer the loop, in one pull request on the domain repo, on a branch of its own.

#### Scenario: Several content changes
- **GIVEN** a run that proposes an alias, a new summary and a conventions rule for recall
- **WHEN** the owner approves opening the pull requests
- **THEN** one pull request on the domain repo holds all three

### Requirement: Meta changes in a separate pull request
A run SHALL put every change to the test set, and every conventions rule that steers the loop or its scorecard, in a second pull request whose title starts with `[meta]`, never in the domain pull request, and SHALL add no label to either.

#### Scenario: Run with both kinds
- **GIVEN** a run that proposes an alias and a new test question
- **WHEN** the owner approves opening the pull requests
- **THEN** the domain pull request holds the alias only, a pull request titled with the `[meta]` prefix holds the test question only, and neither carries a label

#### Scenario: Content changes only
- **GIVEN** a run whose only proposals are content changes, and an owner who declines adding test questions
- **WHEN** the pull requests are opened
- **THEN** no `[meta]` pull request is opened

### Requirement: Test questions proposed for each fix
For each change in the domain pull request, the run SHALL propose adding its triggering question, with the notes expected to answer it, to the test set in the `[meta]` pull request.

#### Scenario: Alias fix adds a test question
- **GIVEN** a domain pull request that adds an alias for one `not-found` question
- **WHEN** the `[meta]` pull request is built
- **THEN** it adds that question to the test set, with the aliased note as its expected note and the log line it came from

### Requirement: Pull request body
Each pull request body SHALL show, for every change, what it changes, the log lines behind it and its scorecard result, then the pull request's overall pass or fail, the gaps and items left for the owner, and the count of unreadable log lines.

#### Scenario: Body read by the owner
- **WHEN** the owner opens a pull request from a scratch run
- **THEN** its body holds each change with its log lines and result, the overall pass or fail, the owner's items and the unreadable-line count

### Requirement: Merge order named
A `[meta]` pull request scored on top of the same run's domain pull request SHALL say so in its body and name that domain pull request as the one to merge first.

#### Scenario: Both pull requests opened
- **GIVEN** a run that opens a domain pull request and a `[meta]` pull request
- **WHEN** the owner reads the `[meta]` pull request body
- **THEN** it names the domain pull request and says to merge it first

### Requirement: Checks pass before a push
Before it asks to push a branch, the run SHALL run the link, schema, deletion and secret checks on the branch's commits through the plugin's check command, and when any check reports a problem or cannot run SHALL report it and push nothing.

#### Scenario: Proposed link to a missing note
- **GIVEN** a branch where a proposed `links` entry names a note that does not exist
- **WHEN** the run checks the branch
- **THEN** it reports the problem, does not ask to push, and nothing reaches the remote

### Requirement: Never on the main branch
The improve skill SHALL never commit to or push the domain's main branch, so each of its changes reaches main only through a pull request the owner merges.

#### Scenario: Remote after a run
- **GIVEN** a run that opened a domain pull request
- **WHEN** the owner lists the remote's main branch history
- **THEN** it holds no commit from the run until the owner merges
