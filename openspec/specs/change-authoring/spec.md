# change-authoring Specification

## Purpose

How an OpenSpec change is authored with this plugin: which artifacts a change needs, when `design.md` is written, how scenarios name their proof and stay unique, how a change with no behaviour change is recorded, and how the live specification set is read and validated.

## Requirements

### Requirement: A change is complete without design.md

An authoring or review skill SHALL treat a change as complete with proposal.md, tasks.md and at least one spec delta, or `skip_specs`, whether or not it has a design.md.

#### Scenario: A change without design.md passes the authoring post-check

- **WHEN** multi-spec's authoring agent writes a change that no stock trigger applies to
- **THEN** it writes no design.md and reports `done` with proposal.md, tasks.md and a spec delta present
- **AND** the post-check accepts the change

### Requirement: design.md is written only on a named stock trigger

An authoring skill SHALL write design.md only when a stock OpenSpec trigger applies (a cross-cutting change, a new dependency or data model, security, performance or migration complexity, or real ambiguity), and SHALL name that trigger in its report.

#### Scenario: A design.md names its trigger

- **WHEN** an authoring agent writes design.md
- **THEN** its report names the stock trigger that applied

### Requirement: A pinned-parameters block only for a load-bearing number

The multi-spec authoring brief SHALL require a pinned-parameters block only when design.md exists and the change has a load-bearing number, such as a threshold, cap or weight.

#### Scenario: A change with no load-bearing number

- **WHEN** an authoring agent writes a change with no threshold, cap, weight or similar load-bearing number
- **THEN** it adds no pinned-parameters block

### Requirement: Authoring requires no doc-sync task

The multi-spec authoring brief SHALL NOT require a separate doc-sync task in tasks.md.

#### Scenario: Tasks without a doc-sync task

- **WHEN** an authoring agent writes tasks.md
- **THEN** the post-check accepts it with no doc-sync task

### Requirement: The authoring brief points to the stock limits

The multi-spec authoring brief SHALL state OpenSpec's stock limits in one line and point to the `openspec/config.yaml` rules rather than copy OpenSpec's instruction text.

#### Scenario: The brief states the limits

- **WHEN** an authoring agent reads the brief
- **THEN** it finds the stock limits in one line with a pointer to the `openspec/config.yaml` rules

### Requirement: Every new or modified scenario names its proof

Each scenario a change adds, or whose text it changes, SHALL have a test task whose test carries a `scenario: <spec> / <heading>` comment line, or a tasks.md line `manual: <heading>: <reason>`. A pure heading rename, and a scenario carried forward unchanged in a MODIFIED block, SHALL be exempt.

#### Scenario: Authoring a scenario

- **WHEN** an authoring agent adds or modifies a scenario
- **THEN** its test carries a `scenario: <spec> / <heading>` comment line above it, or tasks.md carries `manual: <heading>: <reason>` for it

#### Scenario: A pure heading rename

- **WHEN** a change renames a scenario heading and leaves the scenario's body unchanged
- **THEN** the renamed scenario needs no new test task or `manual:` line

### Requirement: Scenario headings are unique within one spec

Scenario headings SHALL be unique within one spec, so `<spec> / <heading>` names one scenario. An authoring agent that adds a scenario whose heading another scenario in that spec already has SHALL rename the new heading.

#### Scenario: Authoring a heading that is already taken

- **WHEN** an authoring agent adds a scenario whose heading already names another scenario in that spec
- **THEN** it renames the new heading so that `<spec> / <heading>` stays unique

### Requirement: A change with no behaviour change carries no spec delta

A change with no externally visible behaviour change, such as a refactor, tooling or docs, SHALL set `skip_specs: true` in its `.openspec.yaml` and write no spec delta, rather than invent a requirement to satisfy validation.

#### Scenario: A docs-only change

- **WHEN** multi-spec's authoring agent writes a change that alters no behaviour
- **THEN** it sets `skip_specs: true` and writes no spec delta
- **AND** the post-check accepts the change

### Requirement: Live specs are read overview-first

A skill that reads live specs for context SHALL first list them with `openspec list --specs` and read an overview with `openspec show <id> --type spec --json --no-scenarios`, and SHALL read in full only the specs the change touches. A MODIFIED carry-forward SHALL still copy the full live requirement and all its scenarios.

#### Scenario: Authoring a change that touches one capability

- **WHEN** an authoring agent needs context from a repo with several capabilities
- **THEN** it reads the overview first and reads in full only the capability its delta touches
