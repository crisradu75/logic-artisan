## ADDED Requirements

### Requirement: A test already failing on the base is labelled, not fixed

Before spending its one fix, `/cla:lite-pr` SHALL label a failing test `probably already failing on the base branch: <test>` when neither the test nor the code it exercises shares a file with the change, judging by reading alone with no extra test run, no stash and no second worktree, and SHALL make no edit to fix a labelled test.

#### Scenario: A failing test unrelated to the change

- **WHEN** the gate fails on a test that, together with the code it exercises, shares no file with the change
- **THEN** the test is labelled as probably already failing on the base branch, and the one fix is not spent on it
- **AND** the uncommitted changes in the working tree are left exactly as they were

#### Scenario: A failing test the change touched

- **WHEN** the failing test, or the code it exercises, is in a file the change added or edited
- **THEN** the test is not labelled, and the usual one fix applies to it

### Requirement: A labelled failure ships only by a person's choice

When a failure carries that label, `/cla:lite-pr` SHALL ask a present user whether to open the pull request with `Known failing before this change: <test>, not fixed here` in its body, and when run by `/cla:multi-lite` SHALL halt with the label as its reason, so a red gate never ships unattended.

#### Scenario: The user chooses to ship

- **WHEN** the user agrees to ship with a labelled failure
- **THEN** the pull request is opened, and its body says `Known failing before this change: <test>, not fixed here`

#### Scenario: The user declines

- **WHEN** the user declines to ship with a labelled failure
- **THEN** the test is handled as an unlabelled failure, and no pull request is opened while it is still red

#### Scenario: An unattended run

- **WHEN** a run started by `/cla:multi-lite` has a labelled failure
- **THEN** the run halts without opening a pull request, and its reason names the labelled test

### Requirement: One reported rerun for a failure with no code error

When a failure's log shows no failed assertion, compiler error or test error and names an unreachable network or service, `/cla:lite-pr` SHALL rerun the failing check once with no edit, at most once per run and without using its one fix, and SHALL report the failure as a suspected flake.

#### Scenario: An unreachable service, then a green rerun

- **WHEN** the only error in the log is a refused connection to a service, and the rerun passes
- **THEN** the run goes on to open the pull request, and the pull request reports the suspected flake

#### Scenario: A real failure or a bare timeout

- **WHEN** the log shows a failed assertion, or shows only a timeout
- **THEN** no rerun happens, and the usual one fix applies

#### Scenario: The rerun is still red

- **WHEN** the rerun fails again
- **THEN** the one fix is still available, and no second rerun happens

### Requirement: A search for duplicate work before building

While planning, `/cla:lite-pr` SHALL search the repo's pull requests in every state and the base branch's recent commits for work matching the change, and on a likely match SHALL show it and wait for a present user's reply, or, when run by `/cla:multi-lite`, continue and name the match in the pull request body.

#### Scenario: A likely match with the user present

- **WHEN** the search finds a merged pull request that made the same change
- **THEN** the match is shown, and implementation waits for the user's reply

#### Scenario: A likely match in an unattended run

- **WHEN** a run started by `/cla:multi-lite` finds a likely match
- **THEN** the run continues, and the pull request body names the match

#### Scenario: No GitHub remote, or a failed search

- **WHEN** the repo has no GitHub remote, or the search cannot run
- **THEN** the run continues without halting, and the pull request body says the search was skipped and why

### Requirement: Matched work is left untouched

`/cla:lite-pr` SHALL only read what its duplicate-work search finds, and SHALL never comment on, edit, label, close, merge, check out or push to a matched pull request or its branch.

#### Scenario: Another session's open pull request matches

- **WHEN** the search matches an open pull request this run did not open
- **THEN** that pull request and its branch are left exactly as they were, and the match is only shown or named

### Requirement: The pull request says what was checked

`/cla:lite-pr` SHALL put one `Checks:` line next to the `Risk:` line in the pull request body, naming the checks that ran, each check skipped with its reason, and any known-failing, suspected-flake or likely-duplicate note.

#### Scenario: A docs-only change

- **WHEN** a change touches no source-affecting file, so the test gate is skipped
- **THEN** the `Checks:` line says the test gate was skipped because the change is docs-only

#### Scenario: A run with notes

- **WHEN** a run reran a suspected flake and found a likely duplicate
- **THEN** the `Checks:` line names both notes, and the `Risk:` line still appears next to it, unchanged
