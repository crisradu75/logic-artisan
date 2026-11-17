# Spec Delta

## Purpose

**Serves:** the owner, whose notes must stay valid, linked and free of secrets. It checks the notes a change touches before they are committed, through one command that hooks, skills and tests all call.

## ADDED Requirements

### Requirement: One check command
The check script SHALL take one subcommand, `links`, `schema`, `deletions`, `secrets` or `save`, exit 0 only when that subcommand passes, and otherwise exit non-zero and print each problem as `<path>:<line>: <reason>`.

#### Scenario: Passing check
- **WHEN** `mnemo_check.py links` runs on a change whose links all resolve
- **THEN** it exits 0

#### Scenario: Failing check names the place
- **WHEN** `mnemo_check.py schema` finds a note missing `summary`
- **THEN** it exits non-zero and prints that note's path, the line and the missing field

#### Scenario: Unknown subcommand
- **WHEN** the script is run with a subcommand it does not know
- **THEN** it exits non-zero and lists the five subcommands

### Requirement: Checks cover changed files only
The `links`, `schema`, `deletions` and `secrets` subcommands SHALL examine only the files that differ from the last commit, staged or not, including new untracked files that are not ignored, plus any note that links to a path deleted in the change.

#### Scenario: Unchanged note is not examined
- **WHEN** an unchanged note has a broken link and another note is edited
- **THEN** `links` checks only the edited note

#### Scenario: New untracked note is examined
- **WHEN** a new note has not yet been staged
- **THEN** every check examines it

### Requirement: A check that cannot run fails
A subcommand SHALL fail, naming the cause, when the working folder is not inside a git repo, the repo's top level has no `mnemo.schema.yml`, or a changed text file cannot be read or parsed; it never passes by skipping.

#### Scenario: Outside a git repo
- **WHEN** any subcommand runs in a folder that is not inside a git repo
- **THEN** it exits non-zero and says no repo was found

#### Scenario: Unreadable file
- **WHEN** a changed note is not valid UTF-8 text
- **THEN** the subcommand exits non-zero and names the file

### Requirement: Checks never change files
The `links`, `schema`, `deletions` and `secrets` subcommands SHALL leave every file, the staging area and the git history exactly as they found them, whether they pass or fail.

#### Scenario: Failing run leaves the repo as it was
- **WHEN** `secrets` fails on a changed note
- **THEN** the note's bytes, the staging area and the last commit are identical to before the run

### Requirement: Links resolve
The `links` subcommand SHALL fail when a link in a changed file points to a repo path that does not exist; links to web addresses are not checked.

#### Scenario: Broken relative link
- **WHEN** a changed note links to a note path that does not exist
- **THEN** `links` fails and names the note, the line and the missing target

#### Scenario: Web link
- **WHEN** a changed note links to an `https://` address
- **THEN** `links` does not check that link

### Requirement: No note links to a deleted path
The `deletions` subcommand SHALL fail when the change deletes or renames away a file that any remaining note in the repo still links to.

#### Scenario: Deleted note still linked
- **WHEN** a change deletes a note that an unchanged note links to
- **THEN** `deletions` fails and names the linking note and the deleted path

#### Scenario: Deleted note no longer linked
- **WHEN** a change deletes a note that no remaining note links to
- **THEN** `deletions` passes

### Requirement: Notes match the schema
The `schema` subcommand SHALL fail when a changed note lacks a field the base schema or its type's schema requires; a per-type field the domain schema does not mark required is optional, and notes in `inbox/` are checked against the base fields only.

#### Scenario: Missing required field
- **WHEN** a changed note has no `status` field
- **THEN** `schema` fails and names the note and the field

#### Scenario: Inbox note skips type rules
- **WHEN** a note in `inbox/` has `status: inbox` and only base fields
- **THEN** `schema` passes it without applying any type's rules

#### Scenario: Unmarked type field is optional
- **WHEN** a domain schema lists a per-type field without marking it required, and a note of that type omits it
- **THEN** `schema` passes the note

### Requirement: Base note fields are fixed and add-only
The base schema SHALL require `type`, `title`, `created`, `summary` and `status`, and allow `updated`, `tags`, `aliases` and `source` as optional; a later change may add optional fields only, so existing notes never need rewriting.

#### Scenario: Required set is pinned
- **WHEN** a change adds a required base field or removes any base field
- **THEN** the test suite fails

### Requirement: Schema-file values
The schema reader SHALL read a value after the first `: ` on a line as one of: a plain scalar (the rest of the line, trimmed, which may contain `:`), a single- or double-quoted string with the quotes removed, an inline list `[a, "b, c"]`, or empty.

#### Scenario: Value containing a colon
- **WHEN** a frontmatter line reads `source: https://example.org/a:b`
- **THEN** the value is `https://example.org/a:b`

#### Scenario: Quoted value
- **WHEN** a line reads `title: "Rates: a note"`
- **THEN** the value is `Rates: a note` without the quotes

#### Scenario: Inline list with a quoted comma
- **WHEN** a line reads `tags: [rates, "a, b"]`
- **THEN** the value is the list `rates`, `a, b`

### Requirement: Schema-file structure
The schema reader SHALL accept blank lines, `#` comment lines, `key: value` lines at the left edge, and, under a `key:` line with no value, `key: value` lines indented by exactly two spaces; any other line, such as a tab indent, a `- item` list, a `|` or `>` block, a `{}` map or deeper nesting, SHALL fail naming the file and line.

#### Scenario: Two-level block
- **WHEN** a schema has `fields:` followed by `  summary: required`
- **THEN** the reader returns `fields` holding `summary` set to `required`

#### Scenario: Unsupported construct
- **WHEN** a schema line is `tags: {a: 1}`
- **THEN** the reader fails and names the file and line

### Requirement: Secrets block
The `secrets` subcommand SHALL fail on any API key, private key, card number or IBAN in any changed text file, notes in `inbox/` included, whether masked or not, and print each hit's path, line number and line.

#### Scenario: IBAN in an inbox note
- **WHEN** a changed note in `inbox/` contains an IBAN
- **THEN** `secrets` fails and prints that note's path, line number and line

#### Scenario: Partly masked card number
- **WHEN** a changed note contains a card number with some digits masked
- **THEN** `secrets` still fails

#### Scenario: Clean change
- **WHEN** no changed file contains any secret pattern
- **THEN** `secrets` passes

### Requirement: Standard library only
The check script SHALL run on Mac, Windows and Linux with nothing installed beyond Python 3 and its standard library.

#### Scenario: Third-party import
- **WHEN** a shipped script imports a module outside the Python standard library
- **THEN** the test suite fails and names the script and the module
