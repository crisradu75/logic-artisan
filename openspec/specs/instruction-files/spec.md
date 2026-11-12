# instruction-files Specification

## Purpose

**Serves:** the plugin's skills and the maintainers whose repos keep rules in `CLAUDE.md`, `AGENTS.md` or both.

Which instruction files a skill reads and where it writes a new rule.

## Requirements

### Requirement: Every instruction file is read

A skill that reads a repo's standing rules SHALL read every instruction file that exists, `CLAUDE.md` and `AGENTS.md`, at the root and in the folder of the affected area, and SHALL read both when both exist.

#### Scenario: A repo with both files

- **WHEN** a skill reads the rules of a repo that has a `CLAUDE.md` and an `AGENTS.md`
- **THEN** it reads both

#### Scenario: Shipped text that names the rules file

- **WHEN** any shipped skill or agent text sends a model to a repo's `CLAUDE.md`
- **THEN** it also names `AGENTS.md` or the shared instruction-files reference

### Requirement: A rule is written to the file the repo already uses

When a skill adds a rule or lesson to a repo's instruction file, it SHALL write to the only file at the root when one exists, to `AGENTS.md` when `CLAUDE.md` imports or links it, and, when both exist and are not linked, to `CLAUDE.md`, saying in its report which file and why.

#### Scenario: One file at the root

- **WHEN** only `CLAUDE.md` exists at the root
- **THEN** the rule goes into it

#### Scenario: CLAUDE.md imports AGENTS.md

- **WHEN** both files exist and `CLAUDE.md` holds the line `@AGENTS.md`
- **THEN** the rule goes into `AGENTS.md`

#### Scenario: Both files, not linked

- **WHEN** both files exist and neither imports the other
- **THEN** the rule goes into `CLAUDE.md` and the report says which file and why

### Requirement: An instruction file is never created silently

When a repo has neither `CLAUDE.md` nor `AGENTS.md`, a skill that would add a rule SHALL ask the user which one to create and SHALL NOT create one without that answer.

#### Scenario: Neither file exists

- **WHEN** a skill has a rule to record and the repo has no instruction file
- **THEN** it asks which file to create and creates none until the user answers
