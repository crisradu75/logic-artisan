## ADDED Requirements

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
