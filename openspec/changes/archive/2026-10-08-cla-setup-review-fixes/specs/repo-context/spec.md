## REMOVED Requirements

### Requirement: Setting up a repo with cla-setup

**Reason**: A pattern in the clone's own exclude file is not the repo's line.
**Migration**: Replaced by "Setting up a repo's cla.io tree", which accepts only a `.gitignore` in the repo.

### Requirement: Repo facts in one file

**Reason**: It moved whole incidents, rules included, out of the overlays.
**Migration**: Replaced by "Repo facts and overlay rules on setup".

## ADDED Requirements

### Requirement: Setting up a repo's cla.io tree

`/cla:cla-setup` SHALL create whatever is missing of a repo's `cla.io/` tree (the `decisions/`, `feedback/`, `retro/` and `lessons-learned/` directories, the empty run ledger, and the feedback notes and lessons files) and the `.gitignore` line that keeps chain run notes untracked, SHALL create no overlay, and SHALL change no existing file except to append that line when no `.gitignore` in the repo ignores the notes.

#### Scenario: A fresh repo

- **WHEN** `/cla:cla-setup` runs in a repo with no `cla.io/` directory and no `.gitignore`
- **THEN** it creates the directories, the empty ledger, the seeded files and a `.gitignore` holding the run-notes line, and no overlay

#### Scenario: A repo already set up

- **WHEN** `/cla:cla-setup` runs where some of the tree exists and `.gitignore` already holds the run-notes line
- **THEN** every existing file is left as it was and only the missing pieces are created

#### Scenario: Only this clone or machine ignores the notes

- **WHEN** the user's global git excludes or the clone's own exclude file ignores the run notes but no `.gitignore` in the repo does
- **THEN** `/cla:cla-setup` appends the line to `.gitignore` and leaves every other line as it was

### Requirement: Repo facts and overlay rules on setup

`/cla:cla-setup` SHALL propose the repo's facts (install, build, test and dev commands, ports, workspace members, and paths) for `cla.io/project-facts.md` from its manifests, config and overlays, SHALL keep in each overlay every rule it states, with any path or command only that rule uses, moving only an incident's story to the lessons log, and SHALL write a file, delete an overlay left with no rule, or add a token-list entry only on the user's yes.

#### Scenario: A repo with no facts file

- **WHEN** `/cla:cla-setup` runs in a repo with no `cla.io/project-facts.md` and the user agrees to its proposal
- **THEN** it creates the file, filled from the repo's manifests and config

#### Scenario: A command kept in an overlay

- **WHEN** an overlay holds the repo's test command
- **THEN** `/cla:cla-setup` proposes moving it into `cla.io/project-facts.md` and changes neither file without the user's yes

#### Scenario: A rule inside a dated incident

- **WHEN** an overlay's dated incident states a rule for this repo
- **THEN** the proposal keeps that rule in the overlay in a line or two and moves only the story to the lessons log

## MODIFIED Requirements

### Requirement: Optional per-skill overlays

A skill SHALL read the repo's commands, paths, ports, install steps and env files from `cla.io/project-facts.md`, except a path or command only one of its overlay's rules uses, SHALL treat its overlay `cla.io/overlays/<skill>.md` and any `*.local.md` file it reads as optional repo-specific settings, and SHALL run to completion on its generic procedure when they are absent.

#### Scenario: No overlay

- **WHEN** a skill runs in a repo with no overlay for it
- **THEN** it completes using its generic procedure and the facts file

#### Scenario: An overlay that is present

- **WHEN** a skill runs in a repo whose overlay sets a value for it
- **THEN** the skill uses that value

#### Scenario: A fact left in an old overlay

- **WHEN** the facts file lacks a fact a skill needs and that skill's overlay exists
- **THEN** the skill tells the user to run `/cla:cla-setup` to move it
