## MODIFIED Requirements

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
