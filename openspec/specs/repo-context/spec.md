# repo-context Specification

## Purpose

Where a repo keeps the facts and records the plugin's skills read and write, and the skills and checkers that maintain them.

## Requirements

### Requirement: Setting up a repo's cla.io directory

`/cla:cla-init` SHALL create whatever is missing of a repo's `cla.io/` tree (the `decisions/`, `feedback/`, `retro/` and `lessons-learned/` directories, empty run ledgers, the feedback notes and lessons files, and empty overlay stubs) and SHALL never change a file that already exists.

#### Scenario: A fresh repo

- **WHEN** `/cla:cla-init` runs in a repo with no `cla.io/` directory
- **THEN** it creates the directories, empty ledgers, seeded files and overlay stubs under the repo root

#### Scenario: A repo already set up

- **WHEN** `/cla:cla-init` runs where some of the tree exists
- **THEN** every existing file is left as it was and only the missing pieces are created

### Requirement: cla-init seeds OpenSpec authoring rules without clobbering

cla-init SHALL create `openspec/config.yaml` with the shipped `rules:` block when `openspec/` has no config, and otherwise SHALL list each shipped rule the existing config lacks, leaving that file unchanged unless the user agrees to update it.

#### Scenario: No config.yaml

- **WHEN** cla-init runs in a repo with `openspec/` and neither `openspec/config.yaml` nor `openspec/config.yml`
- **THEN** it creates the file with the rules block and reports `created`

#### Scenario: An existing config.yaml or config.yml

- **WHEN** cla-init runs in a repo whose `openspec/config.yaml` or `openspec/config.yml` exists
- **THEN** no new config file is created, the existing one is unchanged, and each shipped rule it lacks is listed as missing or outdated

#### Scenario: The user agrees to update the rules

- **WHEN** cla-init has listed missing or outdated rules and the user agrees to update them
- **THEN** the listed rules are added to the existing config and the repo's own rules stay

### Requirement: Shared repo facts

`/cla:sync-context` SHALL write the repo's shared facts (workspace members, build, test and dev commands, ports, the paths swept for docs, and package and path names) into `cla.io/project-facts.md` from the repo's own manifests and config, creating the file when missing and proposing, never adding, new entries for `cla.io/project-tokens.local.md`.

#### Scenario: A repo with no facts file

- **WHEN** `/cla:sync-context` runs in a repo with no `cla.io/project-facts.md`
- **THEN** it creates the file and fills it from the repo's manifests and config

#### Scenario: A new package name

- **WHEN** it finds a package name the token list does not have
- **THEN** it proposes adding it and adds nothing without the user's yes

### Requirement: Per-skill overlays

A skill SHALL take repo-specific checks and facts from its optional overlay `cla.io/overlays/<skill>.md` and any `*.local.md` file beside it, and SHALL run to completion without the repo detail when the overlay is absent or empty.

#### Scenario: No overlay

- **WHEN** a skill runs in a repo with no overlay for it
- **THEN** it completes using its generic procedure

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
