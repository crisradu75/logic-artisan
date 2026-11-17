# improve-triggering

## Purpose

**Serves:** the owner asking for maintenance of a domain in plain words. It sets when Claude Code picks the improve skill over the review, recall and capture skills, and how that choice is measured before a release.

## ADDED Requirements

### Requirement: Description within the limit
The improve skill's description SHALL have 200 characters or fewer, and SHALL name the words that ask for it, that it reads the query log, and that it proposes pull requests and issues.

#### Scenario: Description length
- **WHEN** the plugin's tests read the improve skill's description
- **THEN** it has 200 characters or fewer, holds "Mnemo maintenance", and the skill's name is `mnemo-improve`

### Requirement: Trigger evals
The improve skill SHALL have 20 trigger prompts of its own, half of them near-misses it must not trigger on, and SHALL be chosen correctly on at least 18 of the 20 before its pull request merges.

#### Scenario: Maintenance request
- **WHEN** the owner asks to run Mnemo maintenance, to improve recall from the query log, or to turn this domain's misses into fixes, in a Mnemo domain session
- **THEN** Claude Code picks the improve skill

#### Scenario: Near-miss request
- **WHEN** the owner asks to check the notes for broken links, to recall or save a note, to set up a domain, or to open a pull request or issue unrelated to Mnemo
- **THEN** Claude Code does not pick the improve skill

#### Scenario: Pass mark
- **WHEN** the trigger evals run on improve's 20 prompts
- **THEN** at least 18 are chosen correctly
