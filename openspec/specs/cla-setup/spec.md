# cla-setup Specification

## Purpose

**Serves:** maintainers who set up a repo to use the plugin.

What `/cla:cla-setup` creates, proposes and asks when it sets a repo up.

## Requirements

### Requirement: OpenSpec authoring rules on setup

`/cla:cla-setup` SHALL create `openspec/config.yaml` with the shipped `rules:` block when `openspec/` has no config, and otherwise SHALL list each shipped rule the existing config lacks, leaving that file unchanged unless the user agrees to update it.

#### Scenario: No config file

- **WHEN** `/cla:cla-setup` runs in a repo with `openspec/` and neither `openspec/config.yaml` nor `openspec/config.yml`
- **THEN** it creates `openspec/config.yaml` holding the shipped rules block

#### Scenario: An existing config.yaml or config.yml

- **WHEN** `/cla:cla-setup` runs in a repo whose `openspec/config.yaml` or `openspec/config.yml` exists
- **THEN** no new config file is created, the existing one is unchanged, and each shipped rule it lacks is listed as missing or outdated

#### Scenario: The user agrees to update the rules

- **WHEN** `/cla:cla-setup` has listed missing or outdated rules and the user agrees to update them
- **THEN** the listed rules are added to the existing config and the repo's own rules stay

### Requirement: Retired ledgers on setup

`/cla:cla-setup` SHALL list each retired run ledger present in the repo's `cla.io/retro/` and delete them only on the user's explicit yes, leaving every other file there untouched.

#### Scenario: Retired ledgers present

- **WHEN** `/cla:cla-setup` runs where `cla.io/retro/` holds a retired ledger beside the live ones
- **THEN** it lists only the retired ledger and deletes nothing until the user agrees

#### Scenario: The user declines

- **WHEN** the user answers anything but yes
- **THEN** every listed ledger is kept and reported as kept

#### Scenario: The codify ledger

- **WHEN** `cla.io/retro/` holds the codify-learnings ledger
- **THEN** `/cla:cla-setup` lists it as a retired ledger

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

### Requirement: Setup asks the test-proof question once

In a repo with `openspec/` and no `Test proof granularity` line in `cla.io/project-facts.md`, `/cla:cla-setup` SHALL ask once whether tests prove each requirement or each scenario, recommending requirement, and SHALL write the answer as that one line only on the user's yes.

#### Scenario: No granularity line yet

- **WHEN** `/cla:cla-setup` runs in a repo with `openspec/` whose facts file has no `Test proof granularity` line
- **THEN** it asks the question with requirement recommended and writes the line only after the user's yes

#### Scenario: A line already present

- **WHEN** the facts file already holds a `Test proof granularity` line
- **THEN** `/cla:cla-setup` does not ask and keeps the line as written
