# note-checks

## Purpose

**Serves:** the owner, whose notes stay linked, kept and free of secrets. It defines what the `links`, `deletions` and `secrets` checks report.

## ADDED Requirements

### Requirement: Links resolve
The `links` check SHALL report every relative link or image in a covered Markdown file whose target, without its `#` part, is not a file in the version being checked, comparing names with exact letter case, and SHALL ignore web and mail links.

#### Scenario: Link to a missing note
- **GIVEN** a changed note that links to a note path that does not exist
- **WHEN** the `links` check runs
- **THEN** it reports the note, the line and the missing target

#### Scenario: Wrong letter case
- **GIVEN** a changed note that links to an existing note but with one folder name in different letter case
- **WHEN** the `links` check runs, on any operating system
- **THEN** it reports the link

#### Scenario: Web links and anchors
- **GIVEN** a changed note with a web link and a link to an existing note followed by a `#` heading part
- **WHEN** the `links` check runs
- **THEN** it reports neither link

### Requirement: Links into deleted paths
When the covered change deletes or moves a file, the `links` check SHALL also report every Markdown file anywhere in the repo that still links to the old path, even if that file did not change.

#### Scenario: Unchanged note links to a deleted note
- **GIVEN** a change that deletes note A, while an unchanged note B links to A
- **WHEN** the `links` check runs on the change
- **THEN** it reports note B and the link to A

#### Scenario: Move with updated links
- **GIVEN** a change that moves note A and updates every link to it
- **WHEN** the `links` check runs on the change
- **THEN** it reports nothing about A

### Requirement: Deletions only in the inbox
The `deletions` check SHALL report every file the covered change removes outside the top-level `inbox` folder, and SHALL accept a removal inside `inbox` and a move that git detects as a rename.

#### Scenario: Note deleted outside the inbox
- **GIVEN** a change that deletes a note in a type folder
- **WHEN** the `deletions` check runs
- **THEN** it reports the path and says notes are archived by status, not deleted

#### Scenario: Note deleted in the inbox
- **GIVEN** a change that deletes a note in `inbox`
- **WHEN** the `deletions` check runs
- **THEN** it does not report it

#### Scenario: Note moved out of the inbox
- **GIVEN** a change that moves a note from `inbox` into a type folder
- **WHEN** the `deletions` check runs
- **THEN** it does not report it

### Requirement: Secrets found
The `secrets` check SHALL report every API key, private key block, payment card number and IBAN it finds anywhere in a covered text file, whatever the file's folder or type.

#### Scenario: Card number
- **GIVEN** a changed note holding a 16-digit number that passes the card checksum
- **WHEN** the `secrets` check runs
- **THEN** it reports the note, the line and the kind `card number`

#### Scenario: Private key
- **GIVEN** a changed file holding a line that opens a private key block
- **WHEN** the `secrets` check runs
- **THEN** it reports the file, the line and the kind `private key`

#### Scenario: Number that fails the checksum
- **GIVEN** a changed note holding a 16-digit number that fails the card checksum and has no masked characters
- **WHEN** the `secrets` check runs
- **THEN** it does not report that number

### Requirement: Masked secrets still count
A secret SHALL be reported whether or not part of it is masked, so a card number, IBAN or API key with some characters replaced by `*`, `•` or `x` is still a problem, while the placeholder `<redacted>` is not.

#### Scenario: Masked card number
- **GIVEN** a changed note holding a card number written with its middle digits replaced by `*`
- **WHEN** the `secrets` check runs
- **THEN** it reports the note

#### Scenario: Redacted placeholder
- **GIVEN** a changed note where the secret has been replaced by `<redacted>`
- **WHEN** the `secrets` check runs
- **THEN** it does not report the note

### Requirement: Secret values never printed
A `secrets` report SHALL name the file, the line and the kind of secret and ask the owner to remove the value or replace it with `<redacted>`, and SHALL never print the matched value or any part of it.

#### Scenario: Report hides the value
- **GIVEN** a changed note holding an invented API key
- **WHEN** the `secrets` check reports it
- **THEN** neither standard error nor standard output contains any run of eight or more characters from the key

### Requirement: Every commit in a range is scanned
When a check covers a range of commits, the `secrets` check SHALL scan every file version that each commit in the range introduced, so a secret added and then removed inside the range is still reported.

#### Scenario: Secret added then removed
- **GIVEN** a range of two commits, where the first adds a card number to a note and the second removes it
- **WHEN** the `secrets` check runs on the range
- **THEN** it reports the note and names the first commit
