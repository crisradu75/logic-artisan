# note-recall

## MODIFIED Requirements

### Requirement: Read, follow links one level, search again
The recall skill SHALL read the top hits in full, follow the links in those notes, both links in the text and entries in the `links` field, one level and no deeper, and run a further search on any new name they reveal, within the limits the design sets.

#### Scenario: Answer sits in a linked note
- **GIVEN** an invented meeting note that names a person and links to that person's note, which holds the fact asked for
- **WHEN** the owner asks for that fact about the meeting
- **THEN** recall reads the linked note and cites it

#### Scenario: Links stop at one level
- **GIVEN** note A links to note B, and B links to note C
- **WHEN** a search hits only A
- **THEN** recall reads A and B and does not read C because of that chain

#### Scenario: Answer sits in a note named in the links field
- **GIVEN** an invented hub note whose `links` field names a note holding the fact asked for, and no text link to it
- **WHEN** a search hits only the hub and the owner's question asks for that fact
- **THEN** recall reads the named note and cites it
