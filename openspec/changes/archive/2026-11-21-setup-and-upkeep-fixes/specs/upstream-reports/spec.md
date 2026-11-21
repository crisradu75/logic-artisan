## ADDED Requirements

### Requirement: Nothing is posted before the user approves the text

Before commenting on or opening an issue in the target repository, `/cla:report-upstream` SHALL show the user the exact title and body or comment text and SHALL post only on an explicit yes, a question separate from confirming a duplicate.

#### Scenario: A confirmed core defect

- **WHEN** the checks pass and a draft issue is ready
- **THEN** the draft is shown and nothing is posted until the user says yes

#### Scenario: A confirmed duplicate

- **WHEN** the user confirms an open issue is the same defect
- **THEN** the comment text is shown and posted only after a further yes

## MODIFIED Requirements

### Requirement: A known defect gets a comment, not a second issue

Before opening an issue, `/cla:report-upstream` SHALL search the target's issues, SHALL treat an issue as a duplicate only when it shares a concrete detail with the defect and the user confirms it, SHALL comment on a matching open issue with this repo's platform, version and new detail, and SHALL ask the user before opening anything when only a closed issue matches.

#### Scenario: A matching open issue

- **WHEN** an open issue already describes the defect
- **THEN** the skill comments on it and opens no new issue

#### Scenario: A matching closed issue

- **WHEN** only a closed issue matches
- **THEN** the skill asks whether this is a regression before opening anything

#### Scenario: A match on a keyword only

- **WHEN** an issue shares a keyword with the defect but no symbol, error text or file path
- **THEN** the skill does not treat it as a duplicate without the user's confirmation
