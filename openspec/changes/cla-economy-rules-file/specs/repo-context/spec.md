## REMOVED Requirements

### Requirement: Setting up a repo's cla.io tree

**Migration**: Replaced by "Setting up a repo's cla.io tree and economy rules file", which adds the rules file and keeps all three scenarios' intent.

## ADDED Requirements

### Requirement: Setting up a repo's cla.io tree and economy rules file

`/cla:cla-setup` SHALL create whatever is missing of a repo's `cla.io/` tree and the `.gitignore` line that keeps chain run notes untracked, SHALL write `.claude/rules/cla-economy.md` whole on every run and report `created`, `replaced` (existing content differed) or `unchanged`, SHALL create no overlay, and SHALL change no other existing file except to append that line when no `.gitignore` in the repo ignores the notes.

#### Scenario: A fresh repo

- **WHEN** `/cla:cla-setup` runs in a repo with no `cla.io/` directory, no `.gitignore` and no `.claude/rules/cla-economy.md`
- **THEN** it creates the directories, the empty ledger, the seeded files, the rules file and a `.gitignore` holding the run-notes line, and no overlay

#### Scenario: A repo already set up with a rules file that differs

- **WHEN** `/cla:cla-setup` runs where some of the tree exists, `.gitignore` already holds the run-notes line, and the rules file differs from the fresh text
- **THEN** it replaces the rules file and reports `replaced`, and every other existing file is left as it was

#### Scenario: Only this clone or machine ignores the notes

- **WHEN** the user's global git excludes or the clone's own exclude file ignores the run notes but no `.gitignore` in the repo does
- **THEN** `/cla:cla-setup` appends the line to `.gitignore` and leaves every other line as it was
