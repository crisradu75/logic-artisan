## ADDED Requirements

### Requirement: Running a batch of small changes

`/cla:multi-lite [doc]` SHALL take every small change a decisions or feedback doc describes, by default the newest under `cla.io/decisions/`, confirm the order and the merge policy once at the start, and run `/cla:lite-pr` on each in dependency order.

#### Scenario: A feedback doc with several small fixes

- **WHEN** a user runs `/cla:multi-lite` on a doc listing several small fixes and confirms the plan
- **THEN** each fix gets its own pull request, in dependency order, with no further question

### Requirement: What a small-change chain merges

`/cla:multi-lite` SHALL merge a pull request only under the merge policy confirmed for that run, which is `merge-dependencies-only` when the invocation pre-confirms the plan without naming one, and only when its review left no Critical or Important finding open, counting any finding it cannot recount as open, its full test suite passed on the exact commit being merged with no uncommitted changes, and the host reports it merged rather than queued.

#### Scenario: A fix committed after the tests ran

- **WHEN** a review fix was committed after a candidate's test run
- **THEN** the full suite runs again on that commit before any merge, and a failure leaves the pull request open with its reason

#### Scenario: A queued merge

- **WHEN** the host accepts the merge command but reports the pull request still open or queued
- **THEN** the candidate is not counted as merged and the changes that depend on it are skipped

#### Scenario: A pre-confirmed run that names no policy

- **WHEN** the invocation pre-confirms the plan and names no merge policy
- **THEN** only the changes a later change needs merged are merged
- **AND** the report says which policy applied and why

### Requirement: A resumed small-change chain never merges unchecked commits

When `/cla:multi-lite` resumes an interrupted run, it SHALL never merge a pull request whose head is not the exact commit its review and full test suite both covered, and SHALL leave such a pull request open with its reason for the user.

#### Scenario: Commits pushed while the run was stopped

- **WHEN** a run resumes and a candidate's pull request head differs from the head the run recorded
- **THEN** the pull request is left open with a reason and is not merged

#### Scenario: No recorded head

- **WHEN** a run resumes without the head it recorded for a candidate's pull request
- **THEN** the pull request is left open with a reason and is not merged

### Requirement: A failed small change skips its dependents

`/cla:multi-lite` SHALL skip a failed change and every change that depends on it, continue with the changes that do not, and report each skipped change with its reason.

#### Scenario: A failed small change

- **WHEN** one change in a `/cla:multi-lite` chain fails its tests
- **THEN** it and its dependents are skipped with a reason and the independent changes still run
