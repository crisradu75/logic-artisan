## REMOVED Requirements

### Requirement: A resumed small-change chain merges only commits it checked

**Reason**: Its exemption for the run's own notes commits existed only because the notes rode the pull request; they now stay local. Rewritten as "A resumed small-change chain merges only the head it checked".
**Migration**: None.

## ADDED Requirements

### Requirement: A resumed small-change chain merges only the head it checked

When `/cla:multi-lite` resumes an interrupted run, it SHALL merge a pull request only when its head is the commit its local run notes recorded as covered by its review and full test suite, and SHALL leave every other open pull request, including one found without those notes, open with its reason for the user.

#### Scenario: Commits pushed while the run was stopped

- **WHEN** a run resumes and a candidate's pull request head differs from the head the run recorded
- **THEN** the pull request is left open as moved since review and is not merged

#### Scenario: No local run notes

- **WHEN** a run resumes without its notes file and finds a candidate's open pull request on GitHub
- **THEN** the pull request is left open as unverifiable and is not merged
