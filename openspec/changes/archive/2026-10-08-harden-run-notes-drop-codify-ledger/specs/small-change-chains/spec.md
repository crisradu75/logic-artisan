## REMOVED Requirements

### Requirement: A resumed small-change chain never merges unchecked commits

**Reason**: The chain's own run-notes commit moves the head it recorded, so "the exact commit" stopped being true. Rewritten as "A resumed small-change chain merges only checked commits", which allows exactly that commit and nothing else.
**Migration**: None.

## ADDED Requirements

### Requirement: A resumed small-change chain merges only checked commits

When `/cla:multi-lite` resumes an interrupted run, it SHALL never merge a pull request holding a commit its review and full test suite did not cover, except the run's own notes commits that change nothing but its notes file, a renamed file counting under both its names, and SHALL leave any such pull request open with its reason for the user.

#### Scenario: Commits pushed while the run was stopped

- **WHEN** a run resumes and a candidate's pull request head differs from the head the run recorded
- **THEN** the pull request is left open with a reason and is not merged

#### Scenario: No recorded head

- **WHEN** a run resumes without the head it recorded for a candidate's pull request
- **THEN** the pull request is left open with a reason and is not merged

#### Scenario: Only the run's own notes commits

- **WHEN** the only commits since the recorded head are the run's own notes commits
- **THEN** the run treats the head as unmoved and carries on with that candidate
