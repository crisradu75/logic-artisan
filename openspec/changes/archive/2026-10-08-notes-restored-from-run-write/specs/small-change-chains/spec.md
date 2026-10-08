## REMOVED Requirements

### Requirement: A resumed small-change chain merges only checked commits

**Reason**: It excepted "the run's own notes commits", which a re-run cannot authenticate, and said nothing about notes edited on the pull request.
**Migration**: Replaced by "A resumed small-change chain merges only commits it checked".

## ADDED Requirements

### Requirement: A resumed small-change chain merges only commits it checked

When `/cla:multi-lite` resumes an interrupted run, it SHALL never merge a pull request holding a commit its review and full test suite did not cover, except commits that change nothing but the run's notes file, a renamed file counting under both its names, SHALL take no recorded head from notes edited on a pull request after the run committed them, and SHALL leave any such pull request open with its reason for the user.

#### Scenario: Commits pushed while the run was stopped

- **WHEN** a run resumes and a candidate's pull request head differs from the head the run recorded
- **THEN** the pull request is left open with a reason and is not merged

#### Scenario: No recorded head it can trust

- **WHEN** a run resumes without the head it recorded for a candidate's pull request, or its notes were edited on a pull request after the run committed them
- **THEN** the pull request is left open with a reason and is not merged

#### Scenario: Only notes commits

- **WHEN** the only commits since the recorded head change nothing but the run's notes file
- **THEN** the run treats the head as unmoved and carries on with that candidate
