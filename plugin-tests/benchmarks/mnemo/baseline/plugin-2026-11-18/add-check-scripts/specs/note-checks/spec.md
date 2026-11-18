# Spec Delta

## Purpose

**Serves:** the owner, whose notes must reach `main` valid and free of secrets. It checks the notes a change touches for broken links, missing fields and secrets before they are committed.

## ADDED Requirements

### Requirement: Checks cover changed files only
Each of the `links`, `schema` and `secrets` subcommands SHALL check only the paths named on its command line or, when none are named, every file that differs from the last commit (staged, unstaged or new and not ignored) and still exists, never the whole repo; `deletions` SHALL take the deleted or moved paths the same way.

#### Scenario: Unchanged note is not checked
- **WHEN** a committed note has a broken link and a different note is edited
- **THEN** `links` with no paths reports nothing about the committed note

#### Scenario: Named path is checked
- **WHEN** `schema` is given one note's path
- **THEN** it checks that note and no other

#### Scenario: Deleted note not read
- **WHEN** the change deletes a note that nothing links to
- **THEN** `links`, `schema`, `secrets` and `deletions` exit 0 and name no unreadable file

### Requirement: Which files are notes
A note SHALL be every `.md` file outside `.claude/`, `_meta/`, `sources/` and `attachments/`, except the top-level `CLAUDE.md`, `AGENTS.md` and `README.md`; `links`, `schema` and `deletions` SHALL check notes only, and `secrets` SHALL check every checked file.

#### Scenario: Raw source not a note
- **WHEN** a changed `.md` file in `sources/` has no frontmatter and holds an IBAN
- **THEN** `schema` exits 0 and `secrets` exits 3

#### Scenario: Conventions file not a note
- **WHEN** `_meta/conventions.md` changes and has no frontmatter
- **THEN** `schema` exits 0

### Requirement: Exit status tells the caller what to do
Every subcommand SHALL exit 0 when all checks pass, 1 when a note has a problem, 2 when it cannot run and 3 when a secret is found, and `save` also 4 when it committed but did not push; on a non-zero exit it SHALL print each problem with its file, line and reason, saying for 2 and 3 that `inbox/` must not be used.

#### Scenario: Note problem
- **WHEN** a changed note lacks a required field
- **THEN** `schema` exits 1 and prints the file, the line and the missing field

#### Scenario: Secret found
- **WHEN** a changed file holds a private key
- **THEN** `secrets` exits 3 and prints the file and line and says not to use `inbox/`

### Requirement: A check that cannot run fails
A subcommand SHALL exit 2, never 0, when it cannot finish: the folder is not inside a git repo, the repo has no `mnemo.schema.yml` at its top level, a schema cannot be read, or a file it should check exists but cannot be read.

#### Scenario: Not a Mnemo repo
- **WHEN** any check runs in a git repo without `mnemo.schema.yml` at its top level
- **THEN** it exits 2 and names the missing file

#### Scenario: Unreadable file
- **WHEN** a changed file cannot be read
- **THEN** the check exits 2 and names the file, rather than passing it

### Requirement: The repo is the one the caller is in
The script SHALL check the git repo that contains the current folder, found from that folder, never the repo or folder the script file sits in.

#### Scenario: Run from a subfolder
- **WHEN** a domain's copy of the script runs from a subfolder of that domain repo
- **THEN** it checks that domain repo

#### Scenario: Script lives elsewhere
- **WHEN** the script is run by path from another repo while the current folder is a scratch domain repo
- **THEN** it checks the scratch domain repo

### Requirement: Checks change nothing
The `links`, `schema`, `deletions` and `secrets` subcommands SHALL leave every file, the index and the history of the repo exactly as they found them, and SHALL create no file in the repo, a bytecode cache included.

#### Scenario: Repo unchanged after checks
- **WHEN** all four checks run on a scratch repo with changed and broken notes
- **THEN** the working tree, the index and the commits are byte-identical to before, and no new file exists

### Requirement: Broken links are reported
The `links` check SHALL report each Markdown link in a checked note whose target is a relative path that does not exist in the working tree, and SHALL ignore links with a URL scheme and links that are only an anchor.

#### Scenario: Missing target
- **WHEN** a changed note links to a relative path that does not exist
- **THEN** `links` exits 1 and names the note, the line and the target

#### Scenario: Web link
- **WHEN** a changed note links to an `https:` address
- **THEN** `links` does not report it

### Requirement: Links to deleted paths are reported
The `deletions` check SHALL report every note in the repo, changed or not, that links to a path the change deletes or moves away.

#### Scenario: Unchanged note links to a deleted note
- **WHEN** a note is deleted and an unchanged note links to it
- **THEN** `deletions` exits 1 and names the unchanged note and its link

#### Scenario: Nothing deleted
- **WHEN** the change deletes no file
- **THEN** `deletions` exits 0

### Requirement: Notes carry the required base fields
The `schema` check SHALL report a checked note whose frontmatter lacks any of `type`, `title`, `created`, `summary` or `status`, and SHALL accept a note that lacks any of the optional base fields `updated`, `tags`, `aliases` or `source`.

#### Scenario: Missing summary
- **WHEN** a changed note has no `summary`
- **THEN** `schema` exits 1 and names the missing field

#### Scenario: Optional fields absent
- **WHEN** a changed note has the five required fields and no optional ones
- **THEN** `schema` exits 0

### Requirement: Type rules apply outside inbox
Outside `inbox/`, the `schema` check SHALL report a note whose `type` the domain's `mnemo.schema.yml` does not list or that lacks a field that type marks required, treating per-type fields as optional unless marked required; in `inbox/` it SHALL require only the base fields and `status: inbox`.

#### Scenario: Unknown type
- **WHEN** a changed note outside `inbox/` has a `type` the domain schema does not list
- **THEN** `schema` exits 1 and names the type

#### Scenario: Inbox note without a type rule
- **WHEN** a changed note in `inbox/` has the base fields and `status: inbox` but a type the domain schema does not list
- **THEN** `schema` exits 0

### Requirement: Schema files and frontmatter use one YAML subset
The script SHALL read schema files and note frontmatter as this subset: `key: value` lines whose value is a bare string, a quoted string or an inline list `[a, b]`; a key with no value opens indented `key: value` lines, two levels at most; blank and `#` lines are ignored; anything else is an error naming its line.

#### Scenario: Value holding a colon
- **WHEN** frontmatter holds `title: Plan: part 2`
- **THEN** the title is read as `Plan: part 2`

#### Scenario: Quoted list item holding a comma
- **WHEN** frontmatter holds `tags: ["a, b", c]`
- **THEN** the tags are read as `a, b` and `c`

#### Scenario: Outside the subset
- **WHEN** a note's frontmatter holds an inline map `{a: 1}` or a schema file does
- **THEN** the note gets exit 1 naming its line, and the schema file gets exit 2 naming its line

### Requirement: The base schema only grows
The base schema SHALL name its fields in two top-level inline lists, `required` holding exactly `type`, `title`, `created`, `summary` and `status`, and `optional` holding at least `updated`, `tags`, `aliases` and `source`; any other top-level key SHALL not be a field, and no change SHALL remove a base field or make a field required.

#### Scenario: Field removed
- **WHEN** a base field is deleted from the base schema
- **THEN** the tests fail and name the field

#### Scenario: Optional field added
- **WHEN** a new optional field is added to the base schema
- **THEN** the tests pass

#### Scenario: Extra top-level key
- **WHEN** the base schema gains a top-level key other than `required` and `optional`
- **THEN** the schema check reads it without error and no note is asked to carry it

### Requirement: Secrets block in every folder
The `secrets` check SHALL report every match in a checked file, in any folder `inbox/` included, of an API key, a private key, a card number or an IBAN as `design.md` defines them, whether or not part of it is masked.

#### Scenario: IBAN in an inbox note
- **WHEN** a changed note in `inbox/` holds an IBAN
- **THEN** `secrets` exits 3 and names the file and line

#### Scenario: Masked card number
- **WHEN** a changed note holds a card number with its middle digits replaced by `*`
- **THEN** `secrets` exits 3

#### Scenario: Clean note
- **WHEN** a changed note holds dates, prices and a phone number only
- **THEN** `secrets` exits 0
