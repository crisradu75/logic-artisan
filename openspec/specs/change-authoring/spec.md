# change-authoring Specification

## Purpose

How an OpenSpec change is authored with this plugin: which artifacts a change needs, when `design.md` is written, how scenarios name their proof and stay unique, how a change with no behaviour change is recorded, and how the live specification set is read and validated.

## Requirements

### Requirement: The live specification set is validated where it is written

A skill that writes or hand-edits the live specification set SHALL validate that set's own parse integrity before the commit that lands the edit, and SHALL NOT treat validation of a *change* as covering it. The two are different objects: a change's validation reads the change, while the defect here is a structurally broken document under the live specification directory, which every per-change check passes over.

**The obligation attaches to the edit, not to the delta.** It SHALL cover any hand-edit to a live specification's prose — filling a placeholder section, rewording, adding a canonical heading — including edits that pass through no delta and no archive at all. A live specification is a parsed document rather than a prose file, and the guidance SHALL say so where such edits are performed, because the flow otherwise treats one as a comment.

**Where a step's own remediation instructs a hand-edit to a live specification, that step SHALL carry the validation with it.** A remediation that adds a canonical heading is itself capable of producing a duplicated heading, which closes the section and makes every requirement below it invisible to validation, listing and archiving while the file still reads correctly to a human.

**In a sequence of changes, a broken live set SHALL halt rather than warn.** Each change starts from the specification set the previous one left, so the failure compounds and surfaces at a later change's archive, far from the edit that caused it.

This requirement is distinct from any check comparing a delta's modified-requirement block against the live specification for silently dropped scenarios: that concerns the *content* a sync writes, whereas this concerns the live set's *parse integrity after any edit*, and the measured instance passed through no delta at all.

#### Scenario: EVERY write site validates the live set, not only the change

- **WHEN** any phase in any skill materializes or edits the live specification set
- **THEN** that phase validates the live set before the commit that lands the edit
- **AND** a result naming a broken specification halts and surfaces rather than proceeding to commit
- **AND** a skill with one compliant write site and another that writes without validating does not satisfy this

#### Scenario: The no-delta, no-archive write site runs the check

- **WHEN** a skill edits a live specification in place, creating no delta and running no archive
- **THEN** that skill's own step runs the live-set validation before its commit
- **AND** this is satisfied by the check running at that site, not by another file describing the rule

#### Scenario: A chain validates before it merges

- **WHEN** a change in a sequence leaves the live specification set failing validation
- **THEN** it is treated as a structural failure that halts the sequence
- **AND** the check runs before that change's pull request is merged, so the failing specifications do not reach the base branch and the branch is still available to fix on
- **AND** it is not deferred to the next change, whose archive would fail instead

#### Scenario: A check that could not run is not reported as a broken specification

- **WHEN** the validation exits non-zero without naming a failing specification
- **THEN** it is reported as a tooling fault
- **AND** it is not attributed to the change's own specifications, and does not halt a sequence as a structural failure

#### Scenario: A run that validated nothing is not a pass

- **WHEN** the validation reports that it found no items to validate
- **THEN** that is distinguished from a clean result rather than recorded as success
- **AND** a repository not using the specification tooling has that stated once rather than accruing vacuous passes

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
