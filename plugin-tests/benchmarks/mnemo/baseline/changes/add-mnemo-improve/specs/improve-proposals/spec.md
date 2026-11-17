# improve-proposals

## Purpose

**Serves:** the owner, whose notes should answer next time the questions they failed on. It sets what change the improve skill may propose for each kind of signal in the query log.

## ADDED Requirements

### Requirement: Missing words added to the answering note
When a `not-found` or `corrected` line asks a question that an existing note answers in other words, the improve skill SHALL propose adding the question's words to that note's `aliases` or `questions` field.

#### Scenario: Note uses another name
- **GIVEN** a `not-found` line asking about an invented project by a nickname, and a note on that project that never uses the nickname
- **WHEN** a run proposes changes
- **THEN** it proposes adding the nickname to that note's `aliases`, and no other field of the note changes

### Requirement: Gaps listed, never filled
When no note answers a `not-found` question, the improve skill SHALL list the question as a gap for the owner and SHALL never create or propose a note that answers it.

#### Scenario: Topic never saved
- **GIVEN** a `not-found` line about an invented topic no note covers
- **WHEN** a run proposes changes
- **THEN** the question appears as a gap, and no branch adds a note about that topic

### Requirement: Summary for notes opened but not cited
When a note was opened but not cited in at least two covered lines, the improve skill SHALL propose a new `summary` for that note.

#### Scenario: Note opened twice, never cited
- **GIVEN** two covered lines that each list one invented note under `opened` but not under `cited`
- **WHEN** a run proposes changes
- **THEN** it proposes a new `summary` for that note

#### Scenario: Opened once
- **GIVEN** one covered line that lists a note under `opened` but not under `cited`
- **WHEN** a run proposes changes
- **THEN** it proposes no `summary` change for that note

### Requirement: Hub for a repeated topic
When at least three covered lines ask about one topic, the improve skill SHALL propose a new hub note that gathers that topic's notes, or, when a hub for the topic exists, new entries in that hub's `links` field.

#### Scenario: Topic asked three times
- **GIVEN** three covered lines about one invented topic, answered by notes in two type folders, and no hub for it
- **WHEN** a run proposes changes
- **THEN** it proposes one new hub note whose `links` name those notes

#### Scenario: Hub already exists
- **GIVEN** the same lines and an existing hub for the topic that lacks one of the notes
- **WHEN** a run proposes changes
- **THEN** it proposes adding that note to the hub's `links`, and the hub's body is unchanged

### Requirement: Links for notes opened together
When two notes are both opened in at least three covered lines, the improve skill SHALL propose adding each note to the other's `links` field.

#### Scenario: Pair opened together
- **GIVEN** three covered lines that each list the same two invented notes under `opened`
- **WHEN** a run proposes changes
- **THEN** it proposes a `links` entry in each note naming the other

### Requirement: Corrections and conflicts left to the owner
The improve skill SHALL list each covered `corrected` line with the owner's words, and each pair of notes cited for one answer that disagree, as items for the owner, and SHALL change neither note's body to resolve them.

#### Scenario: Owner corrected an answer
- **GIVEN** a covered `corrected` line whose `user` holds an invented fact
- **WHEN** a run proposes changes
- **THEN** the run lists the correction with those words for the owner, and no branch changes the body of the cited note

### Requirement: Domain rules go to the conventions file
When one cause lies behind at least three covered `not-found` or `corrected` lines and the cause is specific to this domain, the improve skill SHALL propose a numbered rule in the domain's conventions file.

#### Scenario: Repeated date misses
- **GIVEN** three covered `not-found` lines that each missed a note because the question gave a month name and the notes use numeric dates
- **WHEN** a run proposes changes
- **THEN** it proposes one numbered rule in the conventions file that cites all three lines

### Requirement: Shared rules become issues
When a cause behind covered `not-found` or `corrected` lines is not specific to this domain, the improve skill SHALL propose an issue on the plugin's repository instead of a change to any file.

#### Scenario: Cause in the shared recall skill
- **GIVEN** covered lines missed because of how the shared recall skill plans its searches, in a way no domain rule can fix
- **WHEN** a run proposes changes
- **THEN** it proposes an issue for the plugin's repository, and no branch holds a change for that cause
