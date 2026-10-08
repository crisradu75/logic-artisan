# repo-context Specification

## Purpose

Where a repo keeps the facts and records the plugin's skills read and write, and the skills and checkers that maintain them.

## Requirements

### Requirement: Internal terminology

A skill that settles a naming question SHALL record it in `cla.io/terminology.md` within the same session, as an entry `**Term**: what it IS. _Avoid_: alias-1, alias-2`, and no skill SHALL read or change a glossary the repo keeps for external or business terms.

#### Scenario: A name is settled

- **WHEN** a session settles what an internal thing is called
- **THEN** `cla.io/terminology.md` holds the entry before the session ends, creating the file if needed

### Requirement: Checking recorded paths

The plugin SHALL ship a checker a consuming repo runs as `python3 <path>` that names the file, line and path of every repo path in `cla.io/project-facts.md` or an overlay that no longer exists, exiting 0 when none is stale, 1 when some are, and 2 when it cannot run.

#### Scenario: A renamed directory

- **WHEN** the facts file names a directory that was since renamed
- **THEN** the checker reports that file, line and path and exits 1

### Requirement: Checking the plugin text for repo names

The plugin SHALL ship a checker a consuming repo runs as `python3 <path>` that reports, with path, token, line and excerpt, every place the installed plugin's text holds a token from `cla.io/project-tokens.local.md` or a developer's absolute path, exiting 0 when clean, 1 on a match, and 2 when it cannot run.

#### Scenario: A repo name in a skill

- **WHEN** a skill's body names a token from the repo's token list
- **THEN** the checker reports the path, token, line and excerpt and exits 1

#### Scenario: No token list

- **WHEN** the repo has no `cla.io/project-tokens.local.md`
- **THEN** the token check passes and says why

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
