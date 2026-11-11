# repo-context Specification

## Purpose

**Serves:** the plugin's skills and the maintainers who rely on a repo's facts and records.

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

- **WHEN** the facts file names a path under a top-level directory that was since renamed or removed, committed or only staged
- **THEN** the checker reports that file, line and path and exits 1

#### Scenario: A path that was never in this repo

- **WHEN** the facts file names a path such as `skills/x/y.py` or `owner/name.js` whose first part was never a top-level directory of this repo
- **THEN** the checker does not report it, and if git cannot give the repo's history it says so on stderr and checks as before

#### Scenario: A machine-local file

- **WHEN** the facts file names a machine-local file such as `.claude/settings.local.json` that git does not track and that is absent from this clone
- **THEN** the checker does not report it

### Requirement: Checking the plugin text for repo names

The plugin SHALL ship a checker a consuming repo runs as `python3 <path>` that reports, with path, token, line and excerpt, every place the installed plugin's text holds a token from `cla.io/project-tokens.local.md` or a developer's absolute path, exiting 0 when clean, 1 on a match, and 2 when it cannot run.

#### Scenario: A repo name in a skill

- **WHEN** a skill's body names a token from the repo's token list
- **THEN** the checker reports the path, token, line and excerpt and exits 1

#### Scenario: No token list

- **WHEN** the repo has no `cla.io/project-tokens.local.md`
- **THEN** the token check passes and says why

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
