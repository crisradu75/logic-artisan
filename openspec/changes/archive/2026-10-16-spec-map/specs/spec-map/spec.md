## ADDED Requirements

### Requirement: A repo declares its spec map as a fact

A repo SHALL declare its spec map by listing one path or glob per bullet under a `## Spec map` heading in `cla.io/project-facts.md`, in any layout, so that with no such heading there is no map and no map check reports anything, and a heading that names no path, or that reads as this heading in another form, exits non-zero.

#### Scenario: A glob in a custom layout

- **WHEN** the facts file lists `docs/products/*/overview.md` under `## Spec map`
- **THEN** every file matching it is a spec map

#### Scenario: No declaration

- **WHEN** the facts file has no `## Spec map` heading
- **THEN** the checker prints no line about a map and its exit code is unchanged

#### Scenario: A heading the checker cannot read as a declaration

- **WHEN** the `## Spec map` heading has no bullet under it, or the heading is written `### Spec map`
- **THEN** the checker exits non-zero and names the line

### Requirement: Setup offers a three-layer spec map scaffold

`/cla:cla-setup` SHALL offer a repo with `openspec/` a spec map scaffold of three layers, capabilities, then the workflows that deliver them, then the specs each workflow step links, holding links only, and SHALL write it only on the user's yes, at the path the user chooses.

#### Scenario: The user accepts

- **WHEN** the user says yes and names a path
- **THEN** setup writes the scaffold there and records that path under `## Spec map`

#### Scenario: The user declines

- **WHEN** the user says no
- **THEN** setup writes no map and no `## Spec map` heading
