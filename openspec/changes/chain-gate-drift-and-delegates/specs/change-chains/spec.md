## ADDED Requirements

### Requirement: A chain merge reuses the change's own full gate only on the head it ran on

Before merging a change, `/cla:multi-pr` SHALL count the full gate `/cla:spec-to-pr` ran only when that run, in the same session, ran on exactly the recorded head; otherwise it SHALL run the full gate itself, so no change merges without a full gate on the commit it merges and none runs it twice on one commit.

#### Scenario: The head is the commit the change's run gated

- **WHEN** the change's report names a green full gate on a commit equal to the recorded head
- **THEN** the merge goes ahead without a second full gate run

#### Scenario: The head moved after the run

- **WHEN** the recorded head differs from the commit the change's run gated, after a fix the chain committed or a resolved conflict
- **THEN** the chain runs the full gate on the recorded head before merging

#### Scenario: The change's run was red on the head

- **WHEN** the change's report names a failing full gate on a commit equal to the recorded head
- **THEN** the change is not merged, its reason is `full gate red: <failing check>`, and the gate is not run again
