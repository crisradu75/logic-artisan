## ADDED Requirements

### Requirement: Seeding a repo's OpenSpec authoring rules

`/cla:cla-init` SHALL create `openspec/config.yaml` with the shipped `rules:` block when `openspec/` has no config, and otherwise SHALL list each shipped rule the existing config lacks, leaving that file unchanged unless the user agrees to update it.

#### Scenario: No config.yaml

- **WHEN** `/cla:cla-init` runs in a repo with `openspec/` and neither `openspec/config.yaml` nor `openspec/config.yml`
- **THEN** it creates `openspec/config.yaml` holding the shipped rules block

#### Scenario: An existing config.yaml or config.yml

- **WHEN** `/cla:cla-init` runs in a repo whose `openspec/config.yaml` or `openspec/config.yml` exists
- **THEN** no new config file is created, the existing one is unchanged, and each shipped rule it lacks is listed as missing or outdated

#### Scenario: The user agrees to update the rules

- **WHEN** `/cla:cla-init` has listed missing or outdated rules and the user agrees to update them
- **THEN** the listed rules are added to the existing config and the repo's own rules stay

## REMOVED Requirements

### Requirement: cla-init seeds OpenSpec authoring rules without clobbering

**Reason**: Its heading used an internal word, and a scenario named the skill's internal report value.

**Migration**: Restated as repo-context / Seeding a repo's OpenSpec authoring rules.
