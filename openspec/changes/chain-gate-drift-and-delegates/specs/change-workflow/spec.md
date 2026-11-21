## ADDED Requirements

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

After opening its pull request and before the first review round, `/cla:spec-to-pr` SHALL fetch the branch the pull request targets and, only when a file changed there since the branch point is also changed by the pull request, SHALL merge that branch into the feature branch, run the tests for the touched area, and push, so the first review round reads the merged code.

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
