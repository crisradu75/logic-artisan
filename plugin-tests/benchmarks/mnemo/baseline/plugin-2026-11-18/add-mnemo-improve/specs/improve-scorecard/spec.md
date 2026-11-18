# Spec Delta

## Purpose

**Serves:** the owner deciding whether to merge a loop PR. It shows, honestly, how recall answers with and without the change.

## ADDED Requirements

### Requirement: The scorecard asks the right questions
A content PR's scorecard SHALL answer the triggering question, 2 paraphrases of it and every test question whose answering note the change edits, a `[meta]` PR's scorecard SHALL answer every test question, and each question SHALL be answered 3 times on each side.

#### Scenario: Targeted content PR
- **WHEN** a change adds an alias to a note that answers one test question
- **THEN** the scorecard answers 4 questions, each 3 times on main and 3 times on the branch

#### Scenario: Meta PR
- **WHEN** a `[meta]` PR is scored
- **THEN** the scorecard answers every test question 3 times per side

#### Scenario: Test set edited
- **WHEN** a `[meta]` PR adds and removes test questions
- **THEN** the scorecard answers every question from both sides' test sets on both sides, and lists the added and removed questions apart

### Requirement: Both sides start from the same commit
The scorecard SHALL compare the branch with main at the commit the branch starts from, name both commits, and answer each side only from that side's files.

#### Scenario: Main moves during the run
- **WHEN** a capture reaches main while scoring runs
- **THEN** the main side is still answered at the branch's starting commit, and the scorecard names both commits

#### Scenario: Note newer than the branch
- **WHEN** a note reaches main after the branch started
- **THEN** no answer on either side cites it

### Requirement: Figures say what they measured
Each scorecard figure SHALL count an answer as a pass only when it cites the question's expected note, or, for a change that edits no note, when it is not `not-found` and cites a note, state how many answers it counts and their spread, and show a figure it could not measure as missing, never as a score.

#### Scenario: Partial passes
- **WHEN** 2 of the 3 branch answers to a question cite its expected note
- **THEN** the figure reads 2 of 3 for that side

#### Scenario: Side not measured
- **WHEN** the answers on one side fail to run
- **THEN** that side's figures read missing, and no total or difference is shown for them

#### Scenario: Totals show spread
- **WHEN** a scorecard has several questions
- **THEN** each side's total shows the lowest and highest of its 3 runs

### Requirement: Scoring leaves no trace
Scoring SHALL add no line to the query log, change no file in the domain and make no commit.

#### Scenario: Log unchanged after scoring
- **WHEN** scoring answers 24 questions
- **THEN** every query-log file is byte-identical to before, and `git status` in the session shows the same entries

#### Scenario: Next run ignores paraphrases
- **WHEN** a run starts after a scored run
- **THEN** none of the earlier paraphrases appears among its signals
