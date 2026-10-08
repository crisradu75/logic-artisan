## REMOVED Requirements

### Requirement: Setting up a repo's cla.io directory

**Reason**: `/cla:cla-init` is merged into `/cla:cla-setup`, which no longer creates overlay stubs.
**Migration**: Run `/cla:cla-setup`; replaced by "Setting up a repo with cla-setup".

### Requirement: Seeding a repo's OpenSpec authoring rules

**Reason**: The command that seeds the rules is now `/cla:cla-setup`.
**Migration**: Replaced by "OpenSpec authoring rules on setup"; the rules block and the update-on-yes behaviour are unchanged.

### Requirement: Shared repo facts

**Reason**: `/cla:sync-context` is merged into `/cla:cla-setup`, and the facts file becomes the only home for facts.
**Migration**: Run `/cla:cla-setup`; replaced by "Repo facts in one file".

### Requirement: Per-skill overlays

**Reason**: Overlays now hold only a skill's own settings, never facts, and no skill requires one.
**Migration**: Replaced by "Optional per-skill overlays"; `/cla:cla-setup` proposes moving facts out of existing overlays.

### Requirement: Reporting retired ledgers

**Reason**: The command that reports them is now `/cla:cla-setup`.
**Migration**: Replaced by "Retired ledgers on setup"; the listing and delete-on-yes behaviour are unchanged.

## ADDED Requirements

### Requirement: Setting up a repo with cla-setup

`/cla:cla-setup` SHALL create whatever is missing of a repo's `cla.io/` tree (the `decisions/`, `feedback/`, `retro/` and `lessons-learned/` directories, the empty run ledger, and the feedback notes and lessons files) and the `.gitignore` line that keeps chain run notes untracked, SHALL create no overlay, and SHALL change no existing file except to append that line when the repo's own ignore rules lack it.

#### Scenario: A fresh repo

- **WHEN** `/cla:cla-setup` runs in a repo with no `cla.io/` directory and no `.gitignore`
- **THEN** it creates the directories, the empty ledger, the seeded files and a `.gitignore` holding the run-notes line, and no overlay

#### Scenario: A repo already set up

- **WHEN** `/cla:cla-setup` runs where some of the tree exists and `.gitignore` already holds the run-notes line
- **THEN** every existing file is left as it was and only the missing pieces are created

#### Scenario: Only this machine's global excludes ignore the notes

- **WHEN** the user's global git excludes file ignores the run notes but the repo's `.gitignore` does not
- **THEN** `/cla:cla-setup` appends the line to `.gitignore` and leaves every other line as it was

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

### Requirement: Repo facts in one file

`/cla:cla-setup` SHALL propose the repo's facts (install, build, test and dev commands, ports, workspace members, and paths) for `cla.io/project-facts.md` from the repo's own manifests and config, including facts it finds in overlays, and SHALL write that file, move a fact out of an overlay, delete an overlay holding only template headings, or add a `cla.io/project-tokens.local.md` entry only on the user's yes.

#### Scenario: A repo with no facts file

- **WHEN** `/cla:cla-setup` runs in a repo with no `cla.io/project-facts.md` and the user agrees to its proposal
- **THEN** it creates the file, filled from the repo's manifests and config

#### Scenario: A command kept in an overlay

- **WHEN** an overlay holds the repo's test command
- **THEN** `/cla:cla-setup` proposes moving it into `cla.io/project-facts.md` and changes neither file without the user's yes

#### Scenario: A new package name

- **WHEN** it finds a package name the token list does not have
- **THEN** it proposes adding it and adds nothing without the user's yes

### Requirement: Optional per-skill overlays

A skill SHALL read the repo's commands, paths, ports, install steps and env files only from `cla.io/project-facts.md`, SHALL treat its overlay `cla.io/overlays/<skill>.md` and any `*.local.md` file it reads as optional repo-specific settings, and SHALL run to completion on its generic procedure when they are absent.

#### Scenario: No overlay

- **WHEN** a skill runs in a repo with no overlay for it
- **THEN** it completes using its generic procedure and the facts file

#### Scenario: An overlay that is present

- **WHEN** a skill runs in a repo whose overlay sets a value for it
- **THEN** the skill uses that value

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
