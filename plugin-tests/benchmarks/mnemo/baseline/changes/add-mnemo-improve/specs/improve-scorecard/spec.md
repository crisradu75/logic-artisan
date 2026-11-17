# improve-scorecard

## Purpose

**Serves:** the owner deciding whether to merge a loop pull request. It sets which questions each pull request is scored on, how often each is answered, and when a change or a pull request passes.

## ADDED Requirements

### Requirement: Targeted set for a domain pull request
A domain pull request's scorecard SHALL cover, for each change, its triggering questions, 2 paraphrases of each triggering question, and every test-set question whose expected notes include a note the change edits.

#### Scenario: Alias for one question
- **GIVEN** a change that adds an alias to one note for one `not-found` question, and a test set with one question expecting that note
- **WHEN** the scorecard is built
- **THEN** it covers 4 questions: the triggering question, 2 paraphrases and that test question

### Requirement: Full set for a meta pull request
A `[meta]` pull request's scorecard SHALL cover every question in the test set, plus each of its changes' triggering questions and 2 paraphrases of each.

#### Scenario: Test set of ten questions
- **GIVEN** a test set of 10 questions and a `[meta]` pull request that adds 1 test question
- **WHEN** the scorecard is built
- **THEN** it covers the 10 questions, the added question and its 2 paraphrases

### Requirement: Three blind answers per side
Each scorecard question SHALL be answered 3 times on the base side, which is main, or main with the run's domain changes for a `[meta]` pull request, and 3 times on the pull request's side, each by a fresh answerer that follows the recall answer rules and is told neither the side nor the change.

#### Scenario: Answer count
- **GIVEN** a scorecard of 4 questions
- **WHEN** it runs
- **THEN** 24 answers are made, 12 on each side, each from a new answerer

#### Scenario: Meta base side
- **GIVEN** a run with a domain pull request and a `[meta]` pull request
- **WHEN** the `[meta]` scorecard runs
- **THEN** its base side holds the domain pull request's changes, and its other side holds those plus the `[meta]` changes

### Requirement: Figures with run count and spread
An answer SHALL count as correct when it cites at least one expected note of its question, and each figure SHALL show the correct answers out of 3 per question and side, and each side's total with its lowest and highest per-run totals.

#### Scenario: Figure as shown
- **GIVEN** a question answered correctly in 2 of 3 answers on the pull request's side
- **WHEN** the scorecard is written
- **THEN** that figure reads "2/3", and the side's total shows its lowest and highest per-run totals

### Requirement: Pass for a change
A change SHALL pass when, on the pull request's side, each of its triggering questions and each paraphrase is answered correctly at least 2 times out of 3, and SHALL fail otherwise.

#### Scenario: One paraphrase missed
- **GIVEN** a change whose triggering question scores 3/3 and whose paraphrases score 2/3 and 1/3 on the pull request's side
- **WHEN** the scorecard is judged
- **THEN** the change fails

### Requirement: Pass for a pull request
A pull request SHALL pass when every change in it passes and its side's total of correct answers on test-set questions is no lower than the base side's total, and SHALL fail otherwise.

#### Scenario: Regression on a test question
- **GIVEN** a pull request whose changes all pass, with test-set totals of 9 correct on the base side and 8 on its own side
- **WHEN** the scorecard is judged
- **THEN** the pull request fails

#### Scenario: No test-set questions
- **GIVEN** a domain pull request whose changes all pass and touch no note any test question expects
- **WHEN** the scorecard is judged
- **THEN** the pull request passes, and its body says no test question was affected

### Requirement: Scoring leaves the query log alone
Scorecard answers SHALL append nothing to the session's query log and SHALL change no file in the session's working tree.

#### Scenario: Log after scoring
- **GIVEN** a query log of an invented number of lines before a run
- **WHEN** a scorecard of 4 questions runs
- **THEN** the log holds the same lines, byte for byte

### Requirement: Full-set cost asked first
Before a full-set scorecard runs, the improve skill SHALL state how many answers it will make and wait for the owner's yes, and on a no SHALL open no `[meta]` pull request and list its proposals for the owner instead.

#### Scenario: Owner declines the full set
- **GIVEN** a run that proposes one test question, and a test set of 40 questions
- **WHEN** the skill says the full set needs 258 answers, 43 questions on two sides 3 times, and the owner says no
- **THEN** no full-set answer is made, no `[meta]` pull request is opened, and the proposed test question is listed for the owner
