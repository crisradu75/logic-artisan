# Spec Delta

## Purpose

**Serves:** the owner as maintainer of `mnemo`, and the privacy of each domain. It carries an approved proposal from a domain session to `mnemo` as an issue, with nothing from the domain's notes in it.

## ADDED Requirements

### Requirement: The issue target comes from the stamp
The loop SHALL file on the repository named by the `repository` key of the domain's stamp file, and SHALL stop and ask the owner when that key is missing or empty.

#### Scenario: Key present
- **WHEN** the stamp's `repository` is `owner/mnemo`
- **THEN** the issue is filed on `owner/mnemo`

#### Scenario: Key missing
- **WHEN** the stamp has no `repository` key
- **THEN** the loop files nothing and asks the owner which repository to use

### Requirement: Nothing is filed without approval
The loop SHALL show the owner the exact issue title and text in the session and file or comment only after the owner approves that text.

#### Scenario: Owner declines
- **WHEN** the owner declines the shown issue text
- **THEN** nothing is filed or commented

### Requirement: Open issues are not duplicated
Before filing, the loop SHALL search the target's open issues and comment on a matching one, else create a new one, using GitHub's REST interface through `gh api`.

#### Scenario: Matching open issue
- **WHEN** an open issue on the target already proposes the same change
- **THEN** the loop adds a comment to it and creates no new issue

#### Scenario: No match
- **WHEN** no open issue matches
- **THEN** the loop creates one issue

### Requirement: Only counts leave a domain
An issue or comment SHALL carry only counts, cause categories and proposed rule text, never question text, note content, note paths or anything the secrets check flags.

#### Scenario: Draft quotes a question
- **WHEN** a drafted issue contains the text of a logged question
- **THEN** the loop removes it before showing the draft to the owner

#### Scenario: Draft holds a secret pattern
- **WHEN** a drafted issue matches a secret pattern
- **THEN** the loop does not file it and tells the owner which line matched

### Requirement: Only Mnemo is added, only to file
A domain session SHALL add no repository other than `mnemo`, and SHALL use `mnemo` only to search, comment on or create an approved loop issue, never to read or change its files.

#### Scenario: Another repository
- **WHEN** a run would need a repository other than `mnemo`
- **THEN** the loop does not add it

#### Scenario: Write to Mnemo
- **WHEN** a proposed change targets a file in `mnemo`
- **THEN** the loop files it as an issue and makes no commit or branch on `mnemo`
