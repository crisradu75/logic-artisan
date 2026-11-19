# failure-diagnosis Specification

## Purpose

**Serves:** users and change runs that need a failure's real cause found and fixed, not guessed at.

How the diagnose skill reproduces a failure, tests its causes and lands the fix.

## Requirements

### Requirement: A reproduce loop comes before any fix

`/cla:diagnose` SHALL build one command that fails on the reported failure and passes against a known-good state, and confirm its failure matches the reported symptom in specifics, before it ranks a cause or edits anything, and when no such command can be built SHALL stop and report what it tried instead of guessing.

#### Scenario: No loop can be built

- **WHEN** no command reproduces the failure
- **THEN** the skill stops, reports what it tried, and edits nothing

#### Scenario: A loop that fails on something else

- **WHEN** the loop fails with an error other than the reported one
- **THEN** the skill does not treat it as the reproduction and keeps looking

### Requirement: Causes are ranked and written down before any edit

`/cla:diagnose` SHALL write three to five candidate causes, each with what would prove it wrong, ranked before any edit, SHALL let the user prune the list when the user is present to answer, and when no one is, or the caller declared an unattended run, SHALL proceed on the top cause without asking and put the full list in its report.

#### Scenario: Run by a user

- **WHEN** a user starts the skill and answers its questions
- **THEN** the ranked causes are shown for the user to prune before the first test of one

#### Scenario: Run inside an unattended change run

- **WHEN** a calling skill declares the run unattended
- **THEN** the skill tests the top cause without asking and its report lists every ranked cause

### Requirement: The regression test fails before the fix

`/cla:diagnose` SHALL change one variable at a time while testing a cause, and once a cause is confirmed SHALL write a test that fails for that cause and see it fail before fixing it, and when no test can reach the cause without contorting the code SHALL record a dated finding in the repo's feedback folder that points to shaping a decision instead of forcing or skipping the test.

#### Scenario: A confirmed cause with a reachable seam

- **WHEN** the confirmed cause can be reached by a test
- **THEN** the test is seen failing before the fix and passing after it

#### Scenario: No correct seam

- **WHEN** the cause lives where no test can reach it without contorting the code
- **THEN** a dated finding naming the cause and the structural change is written to the feedback folder

### Requirement: Clean up and name the cause

`/cla:diagnose` SHALL remove every debug tag it added, proving it with a search that finds none, and SHALL write a commit message that states the confirmed cause rather than the symptom or the edit.

#### Scenario: A leftover debug tag

- **WHEN** the search still finds a debug tag the run added
- **THEN** the run halts before committing until the tag is removed
