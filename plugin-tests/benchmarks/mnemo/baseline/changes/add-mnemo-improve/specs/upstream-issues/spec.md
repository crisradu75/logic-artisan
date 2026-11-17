# upstream-issues

## Purpose

**Serves:** the plugin's maintainer and every domain, which share learned rules without sharing notes. It sets how an approved cross-domain rule reaches the plugin's repository as an issue, and what such an issue may carry.

## ADDED Requirements

### Requirement: Target read from the plugin manifest
The improve skill SHALL file to the repository named by the `repository` field of the installed plugin's manifest, and when that field is missing or empty SHALL stop and ask the owner for the target, filing nothing.

#### Scenario: Manifest names the target
- **GIVEN** a test copy of the plugin whose manifest's `repository` names a scratch repository
- **WHEN** an approved issue is filed
- **THEN** it is filed on that scratch repository

#### Scenario: Field missing
- **GIVEN** a test copy of the plugin whose manifest has no `repository` field
- **WHEN** a run reaches the issue step
- **THEN** it asks the owner for the target and files nothing

### Requirement: Owner approves the exact text
The improve skill SHALL show the owner the exact issue title and body, or comment, it will send, and SHALL send nothing until the owner approves that text in the session, showing the text again after any change.

#### Scenario: Owner edits the rule text
- **GIVEN** a proposed issue shown to the owner
- **WHEN** the owner asks for a change to the rule text
- **THEN** the skill shows the changed text and sends nothing until the owner approves it

### Requirement: Counts and rule text only
An issue or comment the improve skill sends SHALL carry only the plugin version, the cause category, counts of log lines by result and month, and the proposed rule text, and never a question, the owner's words, a note path or title, or any note content.

#### Scenario: Body checked against the domain
- **GIVEN** a scratch domain whose log holds invented questions and corrections
- **WHEN** an issue from it is filed
- **THEN** the filed body contains no `q` or `user` value from the log, and no note path, title or text from the domain

### Requirement: Search before filing
Before filing, the improve skill SHALL search the target's open issues for one with the same title, comment on that issue when one is found, and create a new issue only when none is found.

#### Scenario: Open issue with the same title
- **GIVEN** an open issue on the scratch target with the title the run would use
- **WHEN** the approved text is sent
- **THEN** it is added as a comment on that issue, and no new issue is created

#### Scenario: No match
- **GIVEN** a scratch target with no open issue of that title
- **WHEN** the approved text is sent
- **THEN** one new issue with that title is created

### Requirement: REST interface only
The improve skill SHALL search, comment on and create issues only through GitHub's REST interface, never through a command that needs GitHub's GraphQL interface, which cloud sessions block.

#### Scenario: Transcript of a filing
- **WHEN** a scratch run files an issue
- **THEN** the transcript holds REST calls for the search and the filing, and no `gh issue` command

### Requirement: The plugin's repository is never changed
The improve skill SHALL never clone, commit to, push to or open a pull request on the plugin's repository, and SHALL add that repository to a cloud session only to send an approved issue or comment.

#### Scenario: Rule fix belongs in the shared skill
- **GIVEN** an approved rule that would change the shared recall skill's text
- **WHEN** the run sends it
- **THEN** the plugin's repository gains one issue or comment and no branch, commit or pull request

### Requirement: Filing failure reports and stops
When the target cannot be reached or refuses a request, the improve skill SHALL show the approved text and the error, and stop without retrying or trying another way to send it.

#### Scenario: Target refuses the request
- **GIVEN** a scratch target that answers the create request with an error
- **WHEN** the run sends the approved issue
- **THEN** it shows the error and the approved text, sends nothing more, and the target holds no new issue or comment
