# Spec Delta

## Purpose

**Serves:** the owner deciding whether to merge a loop PR. It shows how answers to the questions a change affects compare between the current `main` and the PR's branch.

## ADDED Requirements

### Requirement: Targeted scorecard by default
A content PR's scorecard SHALL cover the question that triggered the change, two paraphrases of it, and every test-set question whose answering note the change edits, answering each three times on `main` and three times on the branch.

#### Scenario: Change to one note
- **WHEN** a PR edits a note that answers two test-set questions
- **THEN** the scorecard covers the triggering question, its two paraphrases and those two questions, each answered three times per side

#### Scenario: No test set yet
- **WHEN** the domain has no test-set questions
- **THEN** the scorecard covers the triggering question and its two paraphrases only

### Requirement: Full set for meta PRs
A `[meta]` PR's scorecard SHALL cover every question in the test set on `main` and every question in the test set on the branch, scoring both sides on that same combined list.

#### Scenario: Test question removed
- **WHEN** a `[meta]` PR removes a question from the test set
- **THEN** that question is still scored on both sides and shown

### Requirement: Scorecard figures
For each question and side the scorecard SHALL show how many of the runs gave a correct answer (one that cites the question's answering note), the run count, and the spread across runs, and SHALL mark each question where the branch scores below `main`; it sets no pass mark.

#### Scenario: Branch is worse on one question
- **WHEN** a question is answered correctly 3 of 3 times on `main` and 1 of 3 on the branch
- **THEN** the scorecard shows both figures with run count 3 and marks that question

### Requirement: The baseline is the current main
Scoring SHALL compare the branch against `main` as it stands on the remote when scoring starts.

#### Scenario: Remote main moved
- **WHEN** another location pushed to `main` after the session last pulled
- **THEN** the `main` side is scored on the pushed state

### Requirement: Scoring leaves no trace
Scoring SHALL run in the owner's session, never on GitHub, and SHALL NOT append to the query log, commit, or change any note.

#### Scenario: After scoring
- **WHEN** a scorecard of 15 answers has been produced
- **THEN** the query log has no new lines and no new commit exists
