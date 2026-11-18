# Spec Delta

## Purpose

**Serves:** the owner, whose approved proposals for Mnemo itself reach `mnemo` as issues. It files them from a domain session without carrying the domain's notes or questions out of it.

## ADDED Requirements

### Requirement: Issues go only to the stamped target
Issues SHALL go only to the repository named by the `repository` key of the domain's `.claude/mnemo/stamp.json`, and when the file or key is missing or empty the run SHALL file nothing, say which is missing and ask the owner, never taking a target from anywhere else.

#### Scenario: Target set
- **WHEN** the stamp's `repository` is `owner-x/mnemo` and the owner approves an issue
- **THEN** the issue is filed on `owner-x/mnemo` and nowhere else

#### Scenario: Key missing
- **WHEN** the stamp file has no `repository` key
- **THEN** the run files nothing, says the key is missing and asks the owner, and contacts no repository from the domain's remotes or settings

### Requirement: Nothing is filed without approval
An issue or comment SHALL be filed only after the owner approves its exact text in the session, and any change to the text SHALL need a new approval.

#### Scenario: Owner declines
- **WHEN** the owner does not approve a drafted issue
- **THEN** nothing is filed and no request reaches the target

#### Scenario: Owner edits the text
- **WHEN** the owner asks for a change to an approved draft
- **THEN** the run shows the new text and files it only after a new approval

### Requirement: No duplicate issues
Before filing, the run SHALL search the target's open issues and comment on a matching one instead of opening a new one, through GitHub's REST API only, and a retry after an interrupted or failed filing SHALL open no second issue.

#### Scenario: Open match
- **WHEN** an open issue on the target has the drafted title
- **THEN** the run adds a comment to it and opens no issue

#### Scenario: No match
- **WHEN** no open issue matches
- **THEN** exactly one new issue is opened

#### Scenario: Retry after a lost reply
- **WHEN** a filing created the issue but the run stopped before seeing the reply, and the owner retries
- **THEN** the retry finds that issue and opens no second one

### Requirement: Only counts leave the domain
An issue or comment SHALL carry only counts, cause categories and proposed rule text, never a logged question, note text or a path of a file in the domain, and the run SHALL refuse to file, even when approved, text holding a logged question, a domain file's path or a passage copied from a note, within the bounds `design.md` sets for each.

#### Scenario: Logged question in the draft
- **WHEN** an approved draft quotes a question from the query log
- **THEN** nothing is filed and the run names the quoted question as the reason

#### Scenario: Note path in the draft
- **WHEN** an approved draft names a note's path
- **THEN** nothing is filed and the run names the path

#### Scenario: Counts only
- **WHEN** an approved draft holds counts, a cause category and rule text
- **THEN** it is filed

### Requirement: The target is touched only through issues
On the issue target the run SHALL only list, comment on and create issues, never clone, branch, commit, push or open a PR, and it SHALL reach no repository other than the domain and that target.

#### Scenario: After filing
- **WHEN** a run files an issue
- **THEN** the target's branches and commits are unchanged

#### Scenario: Other repository asked for
- **WHEN** the run's filing step is given a repository other than the stamped target
- **THEN** it refuses, names the stamped target, and sends no request to the other repository

### Requirement: A failed filing is reported, not rerouted
When a REST call fails or does not answer within its time limit, the run SHALL say the issue was not filed, show the approved text, and file it nowhere else and by no other command.

#### Scenario: Network failure
- **WHEN** the REST call to create the issue fails
- **THEN** the run says it was not filed and shows the text, and no other command or repository is tried

#### Scenario: No answer
- **WHEN** the target accepts the connection but never answers
- **THEN** the call ends within 30 seconds and the run says the issue was not filed
