# upstream-reports Specification

## Purpose

**Serves:** maintainers who find a defect in the plugin's shared core.

When and how the report-upstream skill sends one back to the plugin's source.

## Requirements

### Requirement: Only a defect every repo shares is reported

`/cla:report-upstream` SHALL report a problem only when adopting the fix would improve every repo running the plugin, and for a local preference SHALL report nothing, change nothing and point to the repo's own facts or overlay.

#### Scenario: A local preference

- **WHEN** the user wants a rule that only their repo needs
- **THEN** no issue is opened and the skill points to the repo's facts or overlay

#### Scenario: An unclear case

- **WHEN** it is unclear whether every repo would benefit
- **THEN** the skill asks the user instead of guessing

### Requirement: A report rests on facts read this run

`/cla:report-upstream` SHALL quote the faulty core file as read in this run, name its exact path inside the plugin and the installed plugin version, and say whether the repo has edited that file, and SHALL make no claim about the current core that it did not verify in this run.

#### Scenario: A defect remembered but not read

- **WHEN** the skill has not read the file it would blame
- **THEN** it reads the file before writing any claim about it

### Requirement: The report goes where the plugin's manifest says

`/cla:report-upstream` SHALL take its target repository from the plugin's own manifest, SHALL ask the user when the manifest names none, and SHALL NOT guess one.

#### Scenario: A manifest with no repository

- **WHEN** the plugin's manifest has no repository field
- **THEN** the skill stops and asks the user for the target

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

### Requirement: Nothing is posted before the user approves the text

Before commenting on or opening an issue in the target repository, `/cla:report-upstream` SHALL show the user the exact title and body or comment text and SHALL post only on an explicit yes, a question separate from confirming a duplicate.

#### Scenario: A confirmed core defect

- **WHEN** the checks pass and a draft issue is ready
- **THEN** the draft is shown and nothing is posted until the user says yes

#### Scenario: A confirmed duplicate

- **WHEN** the user confirms an open issue is the same defect
- **THEN** the comment text is shown and posted only after a further yes
