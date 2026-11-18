# change-chains Specification

## Purpose

**Serves:** maintainers who run a batch of changes from one decisions doc.

What the plugin promises when a batch of changes from one decisions doc is proposed, run and merged without a person in the loop.

## Requirements

### Requirement: Proposing a batch of changes

`/cla:multi-spec [decisions-file]` SHALL turn a decisions file, by default the newest under `cla.io/decisions/`, into a batch of OpenSpec change proposals, one for each change that touches a protected area or behaviour shipped to other repos, committed one change at a time, reviewed together and opened as one pull request, without implementing them. When no change touches a protected area or shipped behaviour, no pull request opens.

#### Scenario: A decisions file with three decisions

- **WHEN** a user runs `/cla:multi-spec` on a decisions file describing three changes that each touch a protected area or behaviour shipped to other repos
- **THEN** one pull request opens holding three reviewed change proposals and no implementation

#### Scenario: A change that touches no protected area

- **WHEN** a user runs `/cla:multi-spec` on a decisions file where a change touches no protected area and no behaviour shipped to other repos
- **THEN** no proposal is written for it, and the report lists it as a `lite-pr` item with its scope, its decision ids and a one-line reason, and no pull request opens when every change is such a one

### Requirement: Running a batch of OpenSpec changes in dependency order

`/cla:multi-pr [change ...]` SHALL run each named change, or every open change when none is named, through `/cla:spec-to-pr` in dependency order, fixing every blocking finding (`_shared/references/blocking-findings.md`) before a change counts as done and recording unfixed Suggestions and non-blocking findings in `TODO.md` unless the user chose to fix them too.

#### Scenario: A change with only Suggestions left

- **WHEN** a change's review leaves only Suggestions and the user did not choose to fix them
- **THEN** the change counts as done and its Suggestions are recorded in `TODO.md`

#### Scenario: A change that depends on another

- **WHEN** one change in the batch depends on another
- **THEN** the change it depends on runs first

#### Scenario: Resuming before a change's findings were fixed

- **WHEN** a resumed chain cannot show that a change's blocking findings were fixed, and a later change needs it merged
- **THEN** it is not merged and no later change starts

### Requirement: A failed OpenSpec change stops the chain

`/cla:multi-pr` SHALL stop before any later change when a change fails to open or archive its pull request or leaves the live specs failing validation, and SHALL report each change in the batch as shipped, halted with its reason, or never attempted.

#### Scenario: A pull request that never opens

- **WHEN** a change in a `/cla:multi-pr` chain fails to open its pull request
- **THEN** no later change starts
- **AND** the report names each change in the batch as shipped, halted with its reason, or never attempted

### Requirement: Shared environment state merges first

A change that migrates a shared environment, seeds shared data or provisions shared infrastructure SHALL be merged before the next change in its chain starts, even when nothing depends on its code, and when it cannot be merged every later change SHALL be skipped.

#### Scenario: A migration with no code dependents

- **WHEN** a chain holds a change that applies a database migration and nothing depends on its code
- **THEN** it is merged before the next change starts

### Requirement: A later change is held to what an earlier one owes it

When an earlier change in a `/cla:multi-pr` chain adds a field or behaviour for a later change, the later change's review SHALL report each such obligation the later change ignores, the later change SHALL not count as ready while one is ignored, and a resumed chain that cannot read those obligations SHALL stop before starting the later change.

#### Scenario: A field the later change ignores

- **WHEN** a later change's artifacts never mention a field an earlier change added for it
- **THEN** its review reports the ignored obligation and the change is not ready

#### Scenario: Resuming without the run notes

- **WHEN** a chain is resumed where its run notes are missing and a change still to run comes after another change in the chain
- **THEN** the chain stops before that change and says how to go on

### Requirement: A later change's code references are rechecked after earlier merges

Before a later change in a `/cla:multi-pr` chain runs, the chain SHALL recheck each file-and-line reference in its tasks and design against the tree the earlier merges produced, SHALL correct each reference whose lines only moved, and SHALL hand each reference whose lines are gone or now ambiguous to that change's review to answer.

#### Scenario: Cited lines that moved

- **WHEN** an earlier merge moved the lines a later change cites
- **THEN** the later change's references point at the new lines before its review starts

#### Scenario: Cited lines that were removed

- **WHEN** an earlier merge removed the lines a later change cites
- **THEN** the later change's review must answer for that reference and does not count it as fixed while it still points at nothing

### Requirement: An unattended chain keeps running

A chain confirmed at its start SHALL keep running without the user until every change is done, skipped or stopped with a reported reason, asking the user only about a blocker it cannot resolve itself.

#### Scenario: Between two changes

- **WHEN** one change finishes and another is still to run
- **THEN** the chain starts the next change without waiting for the user

### Requirement: An OpenSpec change chain merges only a later change's prerequisite, on the head it checked

`/cla:multi-pr` SHALL merge a pull request only when the merges were confirmed at the start of the run and a later change needs it merged, and only when its head is the commit its review and full test suite covered and the host reports it merged rather than queued, leaving every other pull request open for the user and stopping the chain when a needed merge cannot happen.

#### Scenario: A change later in the order

- **WHEN** one change depends on another in the batch
- **THEN** the dependency is merged before the dependent starts

#### Scenario: An independent change

- **WHEN** a change that nothing later depends on, and that moves no shared environment state, is done
- **THEN** its pull request is left open for the user to merge

#### Scenario: Commits pushed after review

- **WHEN** a change a later change needs merged has a pull request head other than the one its review and full test suite covered
- **THEN** it is not merged and no later change starts

### Requirement: A chain checks a pull request's head before it merges it

Before a chain merges a pull request, the chain check's `before-merge` SHALL exit 1 with the reason the chain records when the run notes hold no head for it, it is not on the branch the run recorded or comes from a fork, it targets another base, it is not open, its head or the remote branch differs from the recorded head, or the checkout is on another commit or has uncommitted changes, and SHALL exit 2, never 0, when it cannot ask the host or the remote.

#### Scenario: Commits pushed after the head was recorded

- **WHEN** the remote branch holds a commit the run notes did not record as the head
- **THEN** `before-merge` exits 1 with `head moved` and the pull request is not merged

#### Scenario: A pull request the chain did not open

- **WHEN** the run notes name a pull request whose branch is not the one the run recorded
- **THEN** `before-merge` exits 1 with `not opened by this chain`

#### Scenario: The host cannot be asked

- **WHEN** `gh` is missing or fails
- **THEN** `before-merge` exits 2 and the pull request is not merged

### Requirement: A chain counts a merge only when the host reports it merged

After a chain's merge command, the chain check's `after-merge` SHALL exit 0, naming the merge commit, only when the host reports the pull request merged, and SHALL exit 1 with `queued: merges later outside this run` when an automatic merge is pending, or with `merge not confirmed` otherwise.

#### Scenario: Auto-merge turned on instead of a merge

- **WHEN** the merge command exits 0 but the pull request is still open with auto-merge pending
- **THEN** `after-merge` exits 1 with `queued: merges later outside this run` and the item does not count as merged

### Requirement: A chain's own fix becomes the recorded head only once it is committed and pushed

After a chain commits and pushes its own fix, the chain check's `fix-pushed` SHALL exit 0, naming the commit to record as the new head, only when a commit was made past the recorded head, nothing outside the run notes is uncommitted and the remote branch holds that commit, and SHALL exit 1 with `fix not committed` or `push not verified` otherwise.

#### Scenario: A hook rejected the commit

- **WHEN** the fix's commit was refused, so the checkout is still on the recorded head
- **THEN** `fix-pushed` exits 1 with `fix not committed` and the recorded head is unchanged

#### Scenario: The push did not land

- **WHEN** the fix was committed but the remote branch does not hold it
- **THEN** `fix-pushed` exits 1 with `push not verified`

### Requirement: A resumed chain acts only on its own pull request at the recorded head

When a chain resumes an item whose pull request it recorded, the chain check's `resume` SHALL exit 0 only when that pull request is open on the recorded head or already merged, and SHALL exit 1 with `head moved since review`, `head unverifiable (ledger lost)`, `PR closed without merging`, `recorded PR not found` or `not opened by this chain` otherwise.

#### Scenario: Commits pushed while the run was stopped

- **WHEN** a resumed item's pull request head differs from the head the run notes recorded
- **THEN** `resume` exits 1 with `head moved since review` and the item is neither handed back nor merged

#### Scenario: Merged while the run was stopped

- **WHEN** a resumed item's pull request was merged in the meantime
- **THEN** `resume` exits 0 and names the merge commit for the run notes
