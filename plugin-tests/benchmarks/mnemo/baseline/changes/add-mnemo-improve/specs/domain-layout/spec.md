# domain-layout

## MODIFIED Requirements

### Requirement: No deferred metadata
The setup skill SHALL create no `mnemo_schema_version` key, no `index.md`, no `log.md` and no `.github/workflows/` folder.

#### Scenario: Fresh repo holds none of them
- **GIVEN** a domain repo the setup skill just created
- **WHEN** the owner lists its files
- **THEN** none of those paths or keys exists

### Requirement: Note folders
The setup skill SHALL create the `inbox`, `sources`, `attachments`, `hubs` and `archive` folders, the `_meta/query-log` and `_meta/tests` folders and one folder per declared type, each kept in git even while it holds no note.

#### Scenario: Folders survive a fresh clone
- **GIVEN** a domain repo the setup skill created and pushed
- **WHEN** the owner clones it into a new folder
- **THEN** every one of those folders exists in the clone

## ADDED Requirements

### Requirement: Empty test set
The setup skill SHALL write the test-set file with a comment line and no questions, and a top-up SHALL add it only when it is missing, leaving an existing test set as it was.

#### Scenario: Fresh repo
- **GIVEN** a domain repo the setup skill just created
- **WHEN** the owner opens the test-set file
- **THEN** it holds the comment line and no question

#### Scenario: Top-up keeps the owner's questions
- **GIVEN** a domain repo whose test set holds invented questions, and whose `hubs` folder is missing
- **WHEN** the setup skill tops it up
- **THEN** the `hubs` folder is added and the test set is byte for byte as it was
