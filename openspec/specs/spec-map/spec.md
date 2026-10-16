# spec-map Specification

## Purpose
**Serves:** maintainers who keep one map from a product's capabilities and workflows to its specs.

What the plugin promises about declaring that map in a repo's facts and the scaffold setup offers for it.

## Requirements

### Requirement: A repo declares its spec map as a fact

A repo SHALL declare its spec map by listing one path or glob per bullet under a `## Spec map` heading in `cla.io/project-facts.md`, in any layout, so that a repo with no such heading, and no line that looks like it, has no map and sees no map output, and a heading that names no path exits non-zero.

#### Scenario: A glob in a custom layout

- **WHEN** the facts file lists `docs/products/*/overview.md` under `## Spec map`
- **THEN** every file matching it is a spec map

#### Scenario: No declaration

- **WHEN** the facts file has no `## Spec map` heading and no line that looks like one
- **THEN** the checker prints no line about a map and its exit code is unchanged

#### Scenario: A heading with no path

- **WHEN** the `## Spec map` heading has no bullet under it
- **THEN** the checker exits non-zero and names the line

### Requirement: A line that looks like the spec map heading is never silently ignored

When no declaration was read, `check_spec_proof.py` SHALL exit non-zero naming the line for a line outside any code fence or comment that looks like the `## Spec map` heading, such as `### Spec map` or `##Spec map`, and SHALL print a note that leaves its exit code unchanged for such a line inside a fence or comment.

#### Scenario: A near miss outside a fence

- **WHEN** the facts file has `##Spec map` in its text and no `## Spec map` heading
- **THEN** the checker exits non-zero and names the line

#### Scenario: A heading shown as an example

- **WHEN** the facts file shows `## Spec map` inside a code fence and declares no map
- **THEN** the checker prints a note naming the line and its exit code is unchanged

#### Scenario: Prose that only says the words

- **WHEN** the facts file says "we have no spec map yet" in a sentence
- **THEN** the checker prints nothing about a map

### Requirement: Setup offers a three-layer spec map scaffold

`/cla:cla-setup` SHALL offer a repo with `openspec/` a spec map scaffold of three layers, capabilities, then the workflows that deliver them, then the specs each workflow step links, holding links only, and SHALL write it only on the user's yes, at the path the user chooses.

#### Scenario: The user accepts

- **WHEN** the user says yes and names a path
- **THEN** setup writes the scaffold there and records that path under `## Spec map`

#### Scenario: The user declines

- **WHEN** the user says no
- **THEN** setup writes no map and no `## Spec map` heading

### Requirement: A spec a change in progress removes is gone for the map rule

A spec whose every requirement a change in progress removes, with none added or modified, SHALL count as gone for the spec map rule: the change may drop its map link and pass, and a map link that stays is reported as a problem.

#### Scenario: The link goes with the spec

- **WHEN** a change removes every requirement of a spec and drops that spec's map link
- **THEN** the checker reports no unlinked spec for it

#### Scenario: The link stays

- **WHEN** a change removes every requirement of a spec and a map file still links it
- **THEN** the checker names the link and exits non-zero
