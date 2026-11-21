# change-workflow Specification

## Purpose

**Serves:** maintainers who take one change from a description to an opened pull request.

What the plugin promises when one change goes from a description to a reviewed, tested, opened pull request, and the authoring rules its specs follow.

## Requirements

### Requirement: Options for one change's run

`/cla:spec-to-pr` SHALL accept `--review-rounds N`, `--test-rounds N` and `--pr-rounds N` to cap the review before implementation, the test-fix rounds and the pull request review rounds, `--skip-review` to skip the pull request review, `--gate-on-push` or `--interactive` to pause before pushing, `--pr-base <branch>` to build on and open against another branch, `--narrow` for narrower permission rules, and `--dry-run` to run every check while writing nothing.

#### Scenario: Skipping the pull request review

- **WHEN** a user runs `/cla:spec-to-pr` with `--pr-rounds 0`
- **THEN** no review round runs on the opened pull request

#### Scenario: A dry run

- **WHEN** a user runs `/cla:spec-to-pr` with `--dry-run`
- **THEN** every check runs and no commit, push, pull request or file edit is made

### Requirement: Resuming a partly done change

Running `/cla:spec-to-pr` again on a change it has partly done SHALL resume at the first phase not yet done, including for a change with no design.md.

#### Scenario: A change with no design.md

- **WHEN** a change's proposal, specs and tasks are written, it has no design.md, and nothing is implemented yet
- **THEN** the run resumes at implementation

#### Scenario: Tasks not written yet

- **WHEN** a change's tasks are not written
- **THEN** implementation does not start

### Requirement: The run's report

A `/cla:spec-to-pr` run SHALL end with a report of each phase's outcome and every open issue, naming the merge command only when every phase passed and no review finding is left open, and SHALL add the review Suggestions it did not fix to the repo-root `TODO.md`.

#### Scenario: A finding left open

- **WHEN** a run ends with a Critical review finding still open
- **THEN** the report says the pull request is not ready to merge and names no merge command

### Requirement: A small change without OpenSpec

`/cla:lite-pr` SHALL take a change that touches no protected area or shipped behaviour from a description to an opened pull request with its docs and tests, one test pass and one review round with a single fix round (two for a fix touching a protected area), writing no OpenSpec change and editing a live spec only when an outcome or interface changes.

#### Scenario: A small fix

- **WHEN** a user runs `/cla:lite-pr` with a one-line description of a small fix
- **THEN** a reviewed pull request with the fix and its test is opened, with no OpenSpec change directory

### Requirement: Reviewing a change before implementation

`/cla:review-change <change>` SHALL check an OpenSpec change's claims and its file and symbol references against the repo, grade each finding Critical, Important or Suggestion, and end with a READY, FIX FIRST or RETHINK verdict.

#### Scenario: A claim the code contradicts

- **WHEN** a change says it mirrors an existing function and the function does something else
- **THEN** the review reports where the claim is wrong and does not return READY while that finding is Critical or Important

### Requirement: Specs follow the repo's authoring rules

Skills that write or review an OpenSpec change SHALL apply the `rules:` block in the repo's `openspec/config.yaml`, which the plugin seeds from its shipped `rules:` block to keep specs to outcomes and interfaces in short requirements.

#### Scenario: A requirement describing internal steps

- **WHEN** a change adds a requirement that describes how a skill sequences its own steps
- **THEN** `/cla:review-change` reports it as a finding

#### Scenario: A repo edits its rules

- **WHEN** a repo changes a rule in its `openspec/config.yaml`
- **THEN** the next change authored by the plugin follows the changed rule

### Requirement: Each requirement names its proof

Each requirement a change adds or modifies SHALL be proven by a test carrying a `requirement: <spec> / <heading>` comment line, or by a tasks.md line `manual: <spec> / <heading>: <reason>`, and `/cla:review-change` SHALL report a requirement with neither as an Important finding.

#### Scenario: A requirement with no proof

- **WHEN** a change adds a requirement and its tasks name neither a test with the marker nor a `manual:` line
- **THEN** the review reports an Important finding naming the requirement

#### Scenario: A test task that names no marker

- **WHEN** a test task proves a requirement but does not name the marker its test will carry
- **THEN** the review reports a Suggestion, which does not block the verdict

### Requirement: A change becomes a risk-reviewed pull request

`/cla:spec-to-pr` SHALL take a description, an existing change name, or nothing (using the conversation so far) and carry the change through its OpenSpec proposal, a review before implementation, implementation, tests, an opened pull request whose body states its risk, reason and reviewers, review fixes sized to that risk, a second review only after a fix that touches a protected area unless `--pr-rounds` is 1, and archiving its specs on the same pull request, without merging or deploying.

#### Scenario: From a description

- **WHEN** a user runs `/cla:spec-to-pr` with a description of a change
- **THEN** a pull request is opened holding the change's code, tests and updated live specs
- **AND** its body states the risk level, the reason and the reviewers chosen
- **AND** it is left open for the user to merge

#### Scenario: The first review applied no fix touching a protected area

- **WHEN** the first review round applies fixes and none of them touches a protected area
- **THEN** no second round runs and the run ends

#### Scenario: The first review applied a fix touching a protected area

- **WHEN** the first review round applies a fix that touches a protected area, and `--pr-rounds` allows a second round
- **THEN** a second round reviews those fixes before the run ends

### Requirement: A new branch is checked for collisions before it is made

Before a change's branch is made, the ship check's `preflight` SHALL exit 1 when a branch of that name exists locally, as a remote-tracking ref or on the remote, when a branch to be renamed is the default branch or the stacked parent or holds commits the branch it is cut from does not, or when a stacked parent has no upstream on the remote, and SHALL exit 2, never 0, when it cannot ask the remote.

#### Scenario: The branch is already on the remote

- **WHEN** `preflight` runs for `feature/x` and the remote already has a `feature/x` branch
- **THEN** it exits 1 and names the remote branch, and no branch is created

#### Scenario: The remote does not answer

- **WHEN** `preflight` runs and the remote cannot be reached
- **THEN** it exits 2, and the branch is not created on an unanswered question

#### Scenario: A stacked parent that was never pushed

- **WHEN** `preflight` runs with `--pr-base feature/parent` and that branch has no upstream
- **THEN** it exits 1 and names the missing upstream

### Requirement: A push is verified against the remote

After a push, the ship check's `pushed` SHALL exit 0 only when the checked-out branch is the one named, its head equals that branch's head on the remote, and its configured upstream is that branch on the remote, and SHALL print `push not verified` on its first line otherwise.

#### Scenario: The commit did not reach the remote

- **WHEN** `pushed` runs after a push that left the remote branch behind the local head
- **THEN** it exits 1 and its first line says `push not verified`

#### Scenario: The remote does not answer

- **WHEN** `pushed` runs and the remote cannot be reached
- **THEN** it exits 2 and its first line says `push not verified`

### Requirement: Measurement trailers are checked before a push

Before a push, the ship check's `trailers` SHALL exit 1 when the number of `Measured-by:` lines in the commit message differs from the number of `Measured-by` trailers git parses from it, and SHALL exit 0 when the two agree, including when both are zero.

#### Scenario: A blank line splits the trailer block

- **WHEN** a commit's two `Measured-by:` lines are separated from its attribution lines by a blank line
- **THEN** `trailers` exits 1

#### Scenario: A change with no measurement

- **WHEN** a commit message has no `Measured-by:` line
- **THEN** `trailers` exits 0

### Requirement: A test already failing on the base is labelled, not fixed

Before spending its one fix, `/cla:lite-pr` SHALL label a failing test `probably already failing on the base branch: <test>` when neither the test nor any code it reaches, directly or through other modules, shares a file with the change, and SHALL make no edit to fix a labelled test.

#### Scenario: A failing test unrelated to the change

- **WHEN** the gate fails on a test that, with all the code it reaches, shares no file with the change
- **THEN** the test is labelled as probably already failing on the base branch, and the one fix is not spent on it
- **AND** the uncommitted changes and every other branch are left exactly as they were, and no extra test run is made to establish the label

#### Scenario: A failing test the change touched

- **WHEN** the failing test, or code it reaches, is in a file the change added or edited
- **THEN** the test is not labelled, and the usual one fix applies to it

#### Scenario: A failure reached only indirectly, or not a test failure

- **WHEN** a test fails because it reaches changed code only through an untouched module, or the failure is a build or typecheck error
- **THEN** it is not labelled, and the usual one fix applies to it

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
- **THEN** the run continues without halting, and its report says the search was skipped and why
- **AND** when a pull request is opened, its body says so too

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

### Requirement: Task count alone does not buy the full review

`/cla:review-change` SHALL NOT give a change its multi-agent review for its number of tasks alone, unless the value of the proposal's `Budget:` line is exactly `protected`, whatever else the budget checker prints about that line, and its report SHALL say whether that line was read.

#### Scenario: Many tasks, no marker

- **WHEN** a change lists four files, touches one capability, makes few claims about existing code and has 30 tasks spread across the four files, and its proposal has no `Budget: protected` line
- **THEN** the review runs without dispatching reviewer agents, and its report says no marker was read

#### Scenario: The same change, marked protected

- **WHEN** the same change's proposal carries the line `Budget: protected`, in a repo whose config states a protected budget sentence or in one whose config states none
- **THEN** the review dispatches its three reviewers, and its report says the marker was read

#### Scenario: A Budget line the review cannot honour

- **WHEN** the proposal carries a `Budget:` line with any value other than `protected`
- **THEN** the review grades the change as unmarked and reports that line as an Important finding
