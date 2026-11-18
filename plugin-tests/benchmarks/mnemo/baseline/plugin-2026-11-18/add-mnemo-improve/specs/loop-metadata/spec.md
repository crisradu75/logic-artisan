# Spec Delta

## Purpose

**Serves:** the owner's existing notes, which must keep passing the checks as the loop gains the fields it owns. It adds the loop's metadata without rewriting any note.

## ADDED Requirements

### Requirement: Loop metadata is add-only
The base schema SHALL gain `questions` and `links` as optional fields and a `mnemo_schema_version` key, and no existing note SHALL need any change to keep passing the checks.

#### Scenario: Old note still passes
- **WHEN** the schema check runs on a note with the five required fields and neither `questions` nor `links`
- **THEN** it exits 0

#### Scenario: Version key present
- **WHEN** the base schema is read
- **THEN** it holds `mnemo_schema_version: 1`, lists `questions` and `links` as optional, and the base-schema add-only test passes

### Requirement: The test set names each question's answering note
The test set in `_meta/tests/questions.yml` SHALL list each test question with its text and the path of the note that answers it, in the schema files' YAML subset, and a run SHALL report an entry whose answering note does not exist and show its figures as missing.

#### Scenario: Valid test set
- **WHEN** the test set holds two entries whose notes exist
- **THEN** the run reads both questions with their answering notes

#### Scenario: Answering note gone
- **WHEN** an entry names a note that does not exist on a side
- **THEN** the run names the entry, and its figures on that side read missing

#### Scenario: No test set
- **WHEN** the domain has no test set file
- **THEN** a content scorecard holds the triggering question and its paraphrases only, and a `[meta]` scorecard says there is no test set
