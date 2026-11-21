## ADDED Requirements

### Requirement: A bug fix starts with its regression test

For a bug fix, `/cla:lite-pr` SHALL write the regression test and see it fail before it changes the code, and when no correct place for a test exists SHALL record `no regression test: no correct seam for <cause>` on the pull request's `Checks:` line and write no feedback file.

#### Scenario: A bug with a testable cause

- **WHEN** the change fixes a bug whose cause a test can reach
- **THEN** the test is written and seen failing before the fix

#### Scenario: A bug with no correct test seam

- **WHEN** no correct place for a test exists
- **THEN** the `Checks:` line says there is no regression test and why, and no file is written under the feedback folder

### Requirement: The pull request description describes the branch as it is

After a review fix round, `/cla:lite-pr` SHALL rewrite the pull request description to describe the branch as it now stands, with no log of the review, keeping the `Risk:` and `Checks:` lines in their formats.

#### Scenario: A review round applied fixes

- **WHEN** the review fix round has been pushed
- **THEN** the description describes the branch as it is now and holds no account of the review
- **AND** the `Risk:` line is still one line in its original format

### Requirement: A duplicate match shares a concrete detail

`/cla:lite-pr` SHALL count a search hit as a likely duplicate only when it shares a concrete detail with the change (a function name, error text or file path) and not only key words, and SHALL show a match to a present user to confirm.

#### Scenario: A hit sharing only key words

- **WHEN** a pull request matches the key words but shares no function name, error text or file path
- **THEN** it is not treated as a likely duplicate
