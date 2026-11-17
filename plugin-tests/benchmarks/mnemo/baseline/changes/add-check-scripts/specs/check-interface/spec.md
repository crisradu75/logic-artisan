# check-interface

## Purpose

**Serves:** the hooks and skills that check and save notes, and the owner reading their results. The check command is the one entry point every caller uses to check and save the notes of a domain repo.

## ADDED Requirements

### Requirement: Five subcommands
The check command SHALL offer exactly five subcommands, `links`, `schema`, `deletions`, `secrets` and `save`, and SHALL offer no `index` subcommand.

#### Scenario: Help lists the five subcommands
- **WHEN** the owner asks the check command for help
- **THEN** it lists `links`, `schema`, `deletions`, `secrets` and `save`, and no other subcommand

#### Scenario: No index subcommand
- **WHEN** a caller runs the check command with `index`
- **THEN** it exits 2 with a usage message and changes nothing

### Requirement: Exit status
Every subcommand SHALL exit 0 when it ran and found no problem, 1 when it ran and found at least one problem, and 2 when it could not run, and `save` SHALL also exit 3 when it committed but could not push.

#### Scenario: Clean files pass
- **GIVEN** a domain repo whose changed notes break no rule
- **WHEN** any check subcommand runs
- **THEN** it exits 0

#### Scenario: A problem fails
- **GIVEN** a changed note that leaves out a required field
- **WHEN** the `schema` subcommand runs
- **THEN** it exits 1

### Requirement: Problem messages
Each problem SHALL be reported on standard error as one line giving the file's path from the repo root, the line number when there is one, the rule that failed and what to do, while standard output SHALL carry only a one-line summary.

#### Scenario: A problem names file, line and rule
- **GIVEN** a changed note whose line 7 links to a file that does not exist
- **WHEN** the `links` subcommand runs
- **THEN** standard error holds one line starting with the note's path and line 7, naming the broken-link rule and the missing target
- **AND** standard output holds only the summary line

### Requirement: A check that cannot run fails
A subcommand that cannot run, or cannot read a file it was asked to check, SHALL exit 2 with a message saying what stopped it, and SHALL never report a pass.

#### Scenario: Not a Mnemo repo
- **GIVEN** a git repo with no `mnemo.schema.yml` at its top level
- **WHEN** any subcommand runs
- **THEN** it exits 2 and says the repo is not a Mnemo repo

#### Scenario: Git fails
- **GIVEN** git cannot list the changed files
- **WHEN** any check subcommand runs
- **THEN** it exits 2, shows git's error, and prints no pass summary

### Requirement: Repo found from the working directory
The check command SHALL find the domain repo from the directory it runs in, using git's top-level folder and never the place the command is installed, and SHALL exit 2 when run outside a git repo.

#### Scenario: Run from a subfolder
- **GIVEN** the working directory is a subfolder of a domain repo
- **WHEN** a check subcommand runs
- **THEN** it checks the whole repo's changed files and reports paths from the repo root

#### Scenario: Run outside a git repo
- **WHEN** a subcommand runs in a folder that is not inside a git repo
- **THEN** it exits 2 and says no git repo was found

### Requirement: Changed files by default
By default a check SHALL cover only the files changed in the working tree against the last commit, untracked files included, and SHALL offer options to cover instead the staged files, the files changed in a range of commits, or every file in the repo.

#### Scenario: An unchanged note is left alone
- **GIVEN** a committed note with a broken link and no change to it
- **WHEN** the `links` subcommand runs with no option
- **THEN** it does not report that note

#### Scenario: Whole-repo option
- **GIVEN** the same committed note with a broken link
- **WHEN** the `links` subcommand runs with the whole-repo option
- **THEN** it reports that note

#### Scenario: Staged option ignores unstaged edits
- **GIVEN** a staged note that passes and an unstaged edit to it that breaks a rule
- **WHEN** the `schema` subcommand runs with the staged option
- **THEN** it exits 0

### Requirement: Which files are notes
A note SHALL be any Markdown file inside a folder of the domain repo, except files under a top-level folder whose name starts with `_` or `.` and files under the top-level `sources` and `attachments` folders, so Markdown files at the repo's top level are not notes.

#### Scenario: A file in a type folder is a note
- **WHEN** the `schema` subcommand covers a changed Markdown file in a type folder
- **THEN** it applies the note rules to it

#### Scenario: Top-level and underscore files are not notes
- **WHEN** the `schema` subcommand covers a changed top-level `AGENTS.md` and a changed file under `_meta`
- **THEN** it applies no note rules to either
