## MODIFIED Requirements

### Requirement: Setting up a repo's cla.io directory

`/cla:cla-init` SHALL create whatever is missing of a repo's `cla.io/` tree (the `decisions/`, `feedback/`, `retro/` and `lessons-learned/` directories, empty run ledgers, the feedback notes and lessons files, and empty overlay stubs) and the `.gitignore` line that keeps chain run notes untracked, and SHALL never change a file that already exists except to append that line when it is missing.

#### Scenario: A fresh repo

- **WHEN** `/cla:cla-init` runs in a repo with no `cla.io/` directory and no `.gitignore`
- **THEN** it creates the directories, empty ledgers, seeded files and overlay stubs under the repo root, and a `.gitignore` holding the run-notes line

#### Scenario: A repo already set up

- **WHEN** `/cla:cla-init` runs where some of the tree exists and `.gitignore` already holds the run-notes line
- **THEN** every existing file is left as it was and only the missing pieces are created

#### Scenario: A .gitignore without the run-notes line

- **WHEN** `/cla:cla-init` runs where `.gitignore` exists without the run-notes line
- **THEN** it appends the line and leaves every other line as it was
