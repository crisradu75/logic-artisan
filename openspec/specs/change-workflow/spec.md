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

### Requirement: One full gate on every run, naming its commit

When the repo's facts file has the line `Full gate: final-commit-only` and the run changes a file the tests build from, every `/cla:spec-to-pr` run SHALL run the full test gate once after archiving, whichever skill or prompt invoked it, and its report SHALL name the commit that run passed or failed on, or say that the gate did not run and why.

#### Scenario: Invoked by a chain

- **WHEN** `/cla:multi-pr` runs `/cla:spec-to-pr` on a change in a repo with that line
- **THEN** the full gate still runs after archiving, and the report names the commit it ran on and whether it passed, and for a failure the failing check and the first error

#### Scenario: Resumed after archiving

- **WHEN** a run that stopped after archiving, before or during its full gate, is resumed
- **THEN** the full gate runs before the report is written, or the report says the full gate did not run and why

#### Scenario: Nothing for the gate to test

- **WHEN** the run changes no file the tests build from, or the facts file names no test commands
- **THEN** no full gate runs after archiving, and the report says it was skipped and why, as a warning when source files changed

### Requirement: Base changes that overlap the pull request are merged in before review

After opening its pull request and before the first review round, when the pull request targets the repo's default branch, `/cla:spec-to-pr` SHALL fetch that branch and, only when a file changed there since the branch point is also changed by the pull request, SHALL merge that branch into the feature branch, run the tests for the touched area, and push, so the first review round reads the merged code.

#### Scenario: The base changed a file the pull request also changes

- **WHEN** a commit merged to the base after branching edits a file the pull request also edits
- **THEN** the base is merged into the feature branch, the touched area's tests run, and the first review round's diff is taken from the merged branch

#### Scenario: No overlap

- **WHEN** the base gained commits since branching but none touches a file the pull request changes
- **THEN** no merge is made, no commit is added, and the report says no overlapping base change was found

#### Scenario: Tests red after the merge

- **WHEN** the touched area's tests fail on the merged branch
- **THEN** the report names the failing test as a warning, no fix loop runs, and review still runs on the merged code

### Requirement: No base-drift merge lands without review

`/cla:spec-to-pr` SHALL check for and merge base changes only on a run whose first review round will run, and SHALL say in its report when the check was skipped because review was skipped.

#### Scenario: Review rounds set to zero

- **WHEN** the run is invoked with `--pr-rounds 0`
- **THEN** the base is neither fetched nor merged, and the report says base drift was not checked because review was skipped

#### Scenario: Review skipped by request

- **WHEN** the run is told to skip review
- **THEN** the base is neither fetched nor merged, and the report says base drift was not checked because review was skipped

#### Scenario: A stacked child

- **WHEN** the pull request targets a parent branch, not the default branch
- **THEN** nothing is fetched or merged, and the report says base drift was not checked: stacked child

### Requirement: The drift merge keeps history and stays on the run's own branch

The base-drift step SHALL only ever merge, never rebase, force-push or rewrite a commit; SHALL change no local or remote branch but the run's own feature branch; and on a conflict SHALL follow the plugin's conflict procedure, naming each side before resolving, with the report naming each conflicted file.

#### Scenario: A conflicting base change

- **WHEN** merging the base into the feature branch conflicts in one file
- **THEN** each side is named before the file is resolved, the resolution is committed as a merge, and the report names the file as a resolved conflict

#### Scenario: Another branch is left alone

- **WHEN** the drift step finishes, with or without a merge
- **THEN** every other local branch and every branch on the remote hold exactly the commits they held before, the feature branch's earlier commits are unchanged, and only the local copy of the remote base has moved, by the fetch

### Requirement: A base that could not be checked or merged is never reported as clean

When the base-drift step cannot fetch or compare the base, or its merge refuses to start or is aborted, `/cla:spec-to-pr` SHALL say in its report that base drift was not checked or not merged, and why, and continue to review, and SHALL never report the base as unchanged or merged on that run.

#### Scenario: The remote does not answer

- **WHEN** the fetch of the base fails
- **THEN** no merge is made, the run goes on to review, and the report says base drift was not checked and why

#### Scenario: The merge is made but not pushed

- **WHEN** the merge is made but the push fails or cannot be verified
- **THEN** the report says the base was merged locally, not pushed, and never that it was merged

#### Scenario: The merge cannot complete

- **WHEN** an overlap is found but the merge refuses to start, because an untracked file would be overwritten, or a hook rejects the merge commit
- **THEN** any half-made merge is undone, the feature branch keeps its earlier head, review runs on it, and the report says the overlapping base change was found but not merged, and why

### Requirement: Merged-in base commits are not counted as review rounds

When `/cla:spec-to-pr` resumes a change whose pull request targets the repo's default branch, its count of applied review rounds SHALL include only the feature branch's own review-fix commits, never commits a base-drift merge brought in, even when the local copy of the base branch is out of date.

#### Scenario: A base commit with a review-round subject

- **WHEN** a drift merge brought in a base commit whose subject is `fix: review round 1`, the local base branch predates it, and the feature branch has no review-fix commit of its own
- **THEN** the resumed run counts no review round applied and runs the first review round

#### Scenario: The branch's own round still counts

- **WHEN** the feature branch carries its own `fix: review round 1` commit and the local base branch is out of date
- **THEN** the resumed run counts one review round applied

### Requirement: A large change's build is never left half-done by one helper running out of context

When a change's tasks list has more than 40 subtasks, `/cla:spec-to-pr` SHALL end its build with every task done, or with a report naming each task still undone, and SHALL never leave the build half-finished because one helper ran out of context.

#### Scenario: A 60-subtask change in five groups

- **WHEN** a change has 60 subtasks under five numbered groups
- **THEN** the build is done in parts no single helper must hold at once, and the run ends with every task ticked or its report naming each unticked task

#### Scenario: Resumed partway through

- **WHEN** a run stopped partway through the build and is resumed
- **THEN** the build continues from the first unticked task, and no ticked task is redone

#### Scenario: A flat tasks list

- **WHEN** a change has 50 subtasks and its tasks list has no numbered groups
- **THEN** it is built as one part, and the run still ends with every task ticked or its report naming each unticked task

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
