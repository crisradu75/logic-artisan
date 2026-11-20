## ADDED Requirements

### Requirement: One full gate on every run, naming its commit

When the repo's facts file has the line `Full gate: final-commit-only`, every `/cla:spec-to-pr` run SHALL run the full test gate once after archiving, whichever skill or prompt invoked it, and its report SHALL name the commit that run passed or failed on.

#### Scenario: Invoked by a chain

- **WHEN** `/cla:multi-pr` runs `/cla:spec-to-pr` on a change in a repo with that line
- **THEN** the full gate still runs after archiving, and the report names the commit it ran on and whether it passed

#### Scenario: A red full gate

- **WHEN** that run fails
- **THEN** the report names the commit, the failing check and the first error, and says the pull request carries a red full gate

#### Scenario: The line is absent

- **WHEN** the facts file has no `Full gate: final-commit-only` line
- **THEN** no extra full gate runs after archiving

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
- **THEN** the report names the failing test as a warning, and review still runs on the merged code

### Requirement: The drift merge keeps history and stays on the run's own branch

The base-drift step SHALL only ever merge, never rebase, force-push or rewrite a commit; SHALL write to no branch but the run's own feature branch; and on a conflict SHALL follow the plugin's conflict procedure, naming each side before resolving, with the report naming each conflicted file.

#### Scenario: A conflicting base change

- **WHEN** merging the base into the feature branch conflicts in one file
- **THEN** each side is named before the file is resolved, the resolution is committed as a merge, and the report names the file as a resolved conflict

#### Scenario: Another branch is left alone

- **WHEN** the drift step finishes, with or without a merge
- **THEN** the base branch and every other branch hold exactly the commits they held before, and the feature branch's earlier commits are unchanged

### Requirement: A base that could not be read is never reported as unchanged

When the base-drift step cannot fetch or compare the base, `/cla:spec-to-pr` SHALL say in its report that base drift was not checked and continue, and SHALL never report the base as unchanged or merge anything on that run.

#### Scenario: The remote does not answer

- **WHEN** the fetch of the base fails
- **THEN** no merge is made, the run goes on to review, and the report says base drift was not checked and why

### Requirement: Merged-in base commits are not counted as review rounds

When `/cla:spec-to-pr` resumes a change, its count of applied review rounds SHALL include only the feature branch's own review-fix commits, never commits a base-drift merge brought in, even when the local copy of the base branch is out of date.

#### Scenario: A base commit with a review-round subject

- **WHEN** a drift merge brought in a base commit whose subject is `fix: review round 1`, the local base branch predates it, and the feature branch has no review-fix commit of its own
- **THEN** the resumed run counts no review round applied and runs the first review round

### Requirement: A large change is implemented one task group at a time

When a change's tasks list has more than 40 subtasks, `/cla:spec-to-pr` SHALL implement it with one delegate per task group, one after another, each told what the earlier groups built, and SHALL settle each group's unfinished work before the next group starts.

#### Scenario: A 60-subtask change in five groups

- **WHEN** a change has 60 subtasks under five numbered groups
- **THEN** five delegates run in group order, and each brief summarises what the groups before it built

#### Scenario: A group comes back unfinished

- **WHEN** a group's delegate returns with some of its tasks unticked
- **THEN** that group's remaining work is finished or recorded as a report issue before the next group's delegate starts

#### Scenario: Resumed partway through

- **WHEN** a run stopped after two groups and is resumed
- **THEN** implementation restarts at the first group with an unticked task, and its brief summarises the earlier groups from the ticked tasks and the code on the branch

### Requirement: A correction continues the same agent

When `/cla:spec-to-pr` re-dispatches an agent to correct its own reply (a reviewer that returned nothing, an uncited enumeration, or an implementer with unfinished work), it SHALL continue that same agent with the gap named when the host can message it, and otherwise SHALL dispatch a fresh agent with the full brief, making at most the one correction attempt each case allows today.

#### Scenario: A reviewer returned nothing

- **WHEN** a first-round reviewer returns no reply and the host can message it
- **THEN** that reviewer is asked again, and a second empty reply is recorded as a missing reviewer, with no third attempt

#### Scenario: The host cannot message the agent

- **WHEN** a correction is needed and the host offers no way to message a finished agent
- **THEN** a fresh agent is dispatched with the full brief, and the run continues
