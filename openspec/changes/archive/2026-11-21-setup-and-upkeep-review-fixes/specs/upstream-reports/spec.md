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
- **THEN** it is a duplicate only if it shares such a concrete detail and the user confirms it

### Requirement: A report opens an issue and changes nothing else

`/cla:report-upstream` SHALL open one issue from a body file giving the path, version, platform, what happens, why it belongs in core and a suggested fix, SHALL end its output with the issue's URL, and SHALL change no tracked file here or upstream.

#### Scenario: A confirmed core defect

- **WHEN** the checks pass, no duplicate exists and the user approves the draft
- **THEN** one issue is opened with those parts and its URL is the last line of output
