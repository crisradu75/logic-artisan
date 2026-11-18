# Spec Delta

## ADDED Requirements

### Requirement: A write into an installed plugin copy asks first

The guard hooks SHALL ask the user, naming the copy, before an Edit or Write whose resolved target lies in the `cache/` or `marketplaces/` part of the plugins directory, or inside the plugin's own root when that root lies in the plugins directory, and SHALL stay silent for a plugin run from a working tree and for the plugin's data directory.

#### Scenario: Editing the installed copy

- **WHEN** an agent edits a file under `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`, directly or through a symbolic link
- **THEN** the user is asked before it runs, and is told the edit is lost on the next update and that a repo's rules go in `cla.io/overlays/<skill>.md` or `cla.io/project-facts.md`

#### Scenario: Editing a plugin run from its working tree

- **WHEN** the plugin was loaded with `--plugin-dir` from a git working tree and an agent edits a file in that tree
- **THEN** no prompt is shown

#### Scenario: Writing the plugin's data directory

- **WHEN** an agent writes a file under `~/.claude/plugins/data/<plugin-id>/`
- **THEN** no prompt is shown
