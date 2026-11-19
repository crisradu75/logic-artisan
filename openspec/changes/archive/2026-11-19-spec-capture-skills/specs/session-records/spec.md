## ADDED Requirements

### Requirement: A checkpoint is a resumable briefing

`/cla:checkpoint` SHALL write one dated briefing in the repo's checkpoints folder holding where things stand, what landed, each open thread with its exact next action, what was decided and why, open questions and traps, omitting an empty section and pointing at commits and pull requests instead of copying them.

#### Scenario: A session with an open branch

- **WHEN** the user runs `/cla:checkpoint` with a branch and pull request still open
- **THEN** the briefing names that branch and pull request with the exact next action, and the report prints the file's path

### Requirement: A checkpoint never holds a secret

`/cla:checkpoint` SHALL name a file that holds a secret and SHALL NOT copy a token, key, connection string or env-file content into the briefing.

#### Scenario: A thread that involved an env file

- **WHEN** a session's trouble was a wrong value in an env file
- **THEN** the briefing names the file and not the value

### Requirement: A checkpoint is checked against the tree before it is followed

When a session resumes from a checkpoint, `/cla:checkpoint` SHALL have it compared with the current git status and open pull requests first, and SHALL treat the tree as true and the checkpoint as stale where they disagree, saying so.

#### Scenario: A pull request merged since

- **WHEN** a checkpoint lists a pull request as open and it has since merged
- **THEN** the session reports the checkpoint as stale on that point and follows the tree

### Requirement: Feedback notes are taken one at a time and read-only grounded

`/cla:feedback` SHALL take one note per turn, ask a question only when a note's target or expectation cannot be told, attach the file or component and a probable cause labelled as unverified from a read-only look at the repo, and change no source file.

#### Scenario: A clear note

- **WHEN** the user gives a note that names its screen and behaviour
- **THEN** no question is asked, and the note is stored with its file context and a severity tag

### Requirement: Feedback writes a new file and never overwrites

`/cla:feedback` SHALL create its dated triage file before the first note and add a numeric suffix rather than overwrite an earlier file of the same name, SHALL read the scratch inbox only on the user's yes and SHALL NOT modify it.

#### Scenario: A second run on the same day

- **WHEN** a triage file with the same slug and date already exists
- **THEN** the new run writes to a suffixed name and leaves the earlier file as it was

### Requirement: Near-duplicate notes merge only on confirmation

`/cla:feedback` SHALL show the notes it would fuse and the combined entry and SHALL merge them only after the user confirms each merge.

#### Scenario: The same crash reported twice

- **WHEN** two notes describe one crash
- **THEN** the skill proposes the merge and keeps both notes until the user agrees

### Requirement: A decision is shaped one question at a time until every axis is settled

`/cla:shape-decision` SHALL read the repo's rules first, list the axes the decision turns on including reversibility, downstream consumers and release, and ask one question at a time, each with options, pros, cons and one recommended pick, until every axis is settled by a quoted answer or a stated reason it needs no question.

#### Scenario: A hard-to-reverse topic

- **WHEN** the user shapes a decision that ships to other repos
- **THEN** the three standing axes are listed first and questions stop only when each has evidence

### Requirement: A decision is saved only on an explicit yes

`/cla:shape-decision` SHALL write its decision record only after the user's explicit yes, to a new dated file in the repo's decisions folder, and SHALL add a numeric suffix rather than overwrite an existing one.

#### Scenario: The user declines

- **WHEN** the user answers no to saving the summary
- **THEN** no file is written

#### Scenario: A record with that name exists

- **WHEN** the user says yes and a record with the same name exists
- **THEN** the new record gets a numeric suffix and the old one is unchanged
