## REMOVED Requirements

### Requirement: What an OpenSpec change chain merges

**Reason**: It allowed a choice of merge policy, and `multi-pr` now has one, and it said nothing about which head may be merged.
**Migration**: Replaced by "An OpenSpec change chain merges only a later change's prerequisite, on the head it checked"; its two scenarios carry over.

## ADDED Requirements

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
