# change-authoring Specification

## Purpose

What the plugin's skills must do when they author an OpenSpec change: which files a change needs, how scenarios name their proof, and how live specs are read. Most of these rules are also in `openspec/config.yaml`.

## Requirements

### Requirement: design.md is optional and written only for a named reason

An authoring or review skill SHALL treat a change as complete with proposal.md, tasks.md and either a spec delta or `skip_specs: true`. An authoring skill SHALL write design.md only when a stock OpenSpec trigger applies (a cross-cutting change, a new dependency or data model, security, performance or migration complexity, or real ambiguity), and SHALL name that trigger in its report.

#### Scenario: A change without design.md passes the authoring post-check

- **WHEN** multi-spec's authoring agent writes a change that no trigger applies to
- **THEN** it writes no design.md and reports `done` with proposal.md, tasks.md and a spec delta present
- **AND** the post-check accepts the change

#### Scenario: A design.md names its trigger

- **WHEN** an authoring agent writes design.md
- **THEN** its report names the trigger that applied

### Requirement: A pinned-parameters block only for a number that changes behaviour

The multi-spec authoring brief SHALL require a pinned-parameters block only when design.md exists and the change has a number that changes behaviour, such as a threshold, cap or weight.

#### Scenario: A change with no such number

- **WHEN** an authoring agent writes a change with no threshold, cap, weight or similar number
- **THEN** it adds no pinned-parameters block

### Requirement: The authoring brief points to the stock limits and asks for no doc-sync task

The multi-spec authoring brief SHALL state OpenSpec's stock limits in one line and point to the `openspec/config.yaml` rules rather than copy OpenSpec's instructions. It SHALL NOT require a separate doc-sync task in tasks.md.

#### Scenario: The brief states the limits

- **WHEN** an authoring agent reads the brief
- **THEN** it finds the stock limits in one line with a pointer to the `openspec/config.yaml` rules

#### Scenario: Tasks without a doc-sync task

- **WHEN** an authoring agent writes tasks.md
- **THEN** the post-check accepts it with no doc-sync task

### Requirement: Every new or modified scenario names its proof

Each scenario a change adds, or whose text it changes, SHALL have a test task whose test carries a `scenario: <spec> / <heading>` comment line, or a tasks.md line `manual: <heading>: <reason>`. A pure heading rename, and a scenario carried forward unchanged in a MODIFIED block, are exempt.

#### Scenario: Authoring a scenario

- **WHEN** an authoring agent adds or modifies a scenario
- **THEN** its test carries a `scenario: <spec> / <heading>` comment line above it, or tasks.md carries `manual: <heading>: <reason>` for it

#### Scenario: A pure heading rename

- **WHEN** a change renames a scenario heading and leaves the scenario's body unchanged
- **THEN** the renamed scenario needs no new test task or `manual:` line

### Requirement: Scenario headings are unique within one spec

Scenario headings SHALL be unique within one spec, so `<spec> / <heading>` names one scenario. An authoring agent that adds a scenario with a heading already used in that spec SHALL rename the new heading.

#### Scenario: Authoring a heading that is already taken

- **WHEN** an authoring agent adds a scenario whose heading already names another scenario in that spec
- **THEN** it renames the new heading so that `<spec> / <heading>` stays unique

### Requirement: A change with no behaviour change carries no spec delta

A change with no externally visible behaviour change, such as a refactor, tooling, docs, or a rule about how a skill file is worded, SHALL set `skip_specs: true` in its `.openspec.yaml` and write no spec delta, rather than invent a requirement to pass validation.

#### Scenario: A docs-only change

- **WHEN** multi-spec's authoring agent writes a change that alters no behaviour
- **THEN** it sets `skip_specs: true` and writes no spec delta
- **AND** the post-check accepts the change

### Requirement: Live specs are read overview-first

A skill that reads live specs for context SHALL list them with `openspec list --specs`, read an overview with `openspec show <id> --type spec --json --no-scenarios`, and read in full only the specs the change touches. A MODIFIED block SHALL still copy the full live requirement and all its scenarios.

#### Scenario: Authoring a change that touches one capability

- **WHEN** an authoring agent needs context from a repo with several capabilities
- **THEN** it reads the overview first and reads in full only the capability its delta touches

### Requirement: Change artifacts are short and plain

A change's spec delta SHALL state behaviour only, in plain words, without history, reasons, measurements or coined terms. Its design.md, when written, SHALL fit one page, giving each decision with one line of why and one line per rejected alternative. Its tasks SHALL cite headings rather than line numbers, and a `measured:` note SHALL give the value.

#### Scenario: Authoring a change with a design decision

- **WHEN** an authoring agent writes a change that needs design.md
- **THEN** each decision is one choice, one line of why, and one line per rejected alternative
- **AND** the spec delta states behaviour without history or measurements
