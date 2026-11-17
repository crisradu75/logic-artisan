# Spec Delta

## Purpose

**Serves:** the owner, who wants each domain's notes and rules to get better from the questions actually asked. It turns the query log into changes the owner reviews and merges, and never touches what a note says.

## ADDED Requirements

### Requirement: A run starts only on request
The improve skill SHALL start a run only when the owner asks for it in a session on a domain repo, for example "run Mnemo maintenance", and never on a schedule or from another skill.

#### Scenario: Owner asks
- **WHEN** the owner says "run Mnemo maintenance" in a domain session
- **THEN** the run starts

#### Scenario: Not a Mnemo repo
- **WHEN** the owner asks for maintenance in a repo with no `mnemo.schema.yml`
- **THEN** the skill says this is not a Mnemo repo and stops

### Requirement: A run stops early when it has nothing to do
A run SHALL end without opening anything, and say why, when the query log is empty or a loop PR is already open in that domain.

#### Scenario: Empty query log
- **WHEN** the domain's query log has no lines
- **THEN** the run ends with "no signals" and opens no PR or issue

#### Scenario: Loop PR already open
- **WHEN** a PR the loop opened earlier is still open in that domain
- **THEN** the run stops and names that PR

### Requirement: A run never disturbs unsaved work
A run SHALL stop before doing anything else when the domain has uncommitted or unpushed changes, and SHALL leave the session on the branch it started on with every file as it found it.

#### Scenario: Uncommitted note at the start
- **WHEN** a run starts while a note has uncommitted edits
- **THEN** the run stops, asks the owner to save first, and the note is unchanged

#### Scenario: Run finishes
- **WHEN** a run that opened a PR ends
- **THEN** the session is on the branch it started on and the working tree is clean

### Requirement: Domain changes reach the owner as PRs
The loop SHALL propose domain-specific rules as edits to the domain's `_meta/conventions.md`, and note-metadata changes as frontmatter edits, each through a PR in the domain repo that the owner merges; it never merges and never commits to `main`.

#### Scenario: Domain rule
- **WHEN** the loop learns a rule that applies only to this domain
- **THEN** it opens a PR that edits `_meta/conventions.md` and leaves the PR for the owner

#### Scenario: Owner's merge is the only gate
- **WHEN** a loop PR is open
- **THEN** `main` is unchanged until the owner merges it

### Requirement: Changes to Mnemo itself become issues
Any change the loop proposes to itself, its scorer, or the Mnemo copy inside a domain repo (its skills, its scripts and conventions, its hook entries) SHALL go to `mnemo` as an issue, never into a PR or a commit.

#### Scenario: Change to the loop's own skill
- **WHEN** the loop proposes rewording its own skill
- **THEN** it prepares an issue on `mnemo` and opens no PR

#### Scenario: Change to the copied check script
- **WHEN** a proposed edit would change a file in the domain's Mnemo copy
- **THEN** no PR contains that edit and it is prepared as an issue instead

### Requirement: Note bodies are never edited
No loop PR SHALL change a note's body (everything below its frontmatter) or any file under `sources/` or `attachments/`; in frontmatter it may change only `aliases`, `summary`, `questions` and `links`.

#### Scenario: Proposal touches a body
- **WHEN** a candidate change would edit text below a note's frontmatter
- **THEN** the change is dropped, the owner is told why, and no PR contains it

#### Scenario: Attachment
- **WHEN** a candidate change would modify, move or delete a file under `attachments/`
- **THEN** no PR contains it

#### Scenario: Allowed field
- **WHEN** a candidate change adds an alias to a note's frontmatter
- **THEN** the PR may contain it, with the body byte-identical

### Requirement: Owner-only rules stay
No loop PR or issue SHALL propose removing or weakening the rule that note bodies are never edited or the rule that only counts leave a domain.

#### Scenario: Proposal weakens a kept rule
- **WHEN** a candidate change would let the loop edit note bodies
- **THEN** it is dropped and the owner is told it is owner-only

### Requirement: Every change cites its signals
Each change the loop proposes SHALL cite the query-log lines behind it (date, result, opened and cited paths), and a change with no cited lines SHALL NOT be proposed.

#### Scenario: Provenance shown
- **WHEN** a loop PR proposes an alias for a note
- **THEN** the PR lists the log lines that led to it

#### Scenario: No signal behind a change
- **WHEN** a candidate change cites no query-log line
- **THEN** it is not proposed

### Requirement: Each PR shows what the owner needs to decide
Every loop PR SHALL show its diff, its scorecard and, for each change, its provenance.

#### Scenario: PR body
- **WHEN** the loop opens a PR
- **THEN** its description holds the scorecard and the provenance of every change, and the diff is the PR's own

### Requirement: Meta changes travel alone
A change to the domain's test set SHALL go in its own PR whose title starts with `[meta]`, never together with a content change, and that PR always carries the full-set scorecard.

#### Scenario: Run with both kinds
- **WHEN** a run proposes a test-set change and a frontmatter change
- **THEN** it opens two PRs, one titled `[meta] ...` holding only the test-set change

### Requirement: Loop commits pass every check
Every commit the loop makes SHALL pass the links, schema, deletions and secrets checks, and a commit that fails one is not made.

#### Scenario: Proposed summary holds a secret
- **WHEN** a proposed `summary` edit contains an IBAN
- **THEN** the commit is not made and no PR carries it
