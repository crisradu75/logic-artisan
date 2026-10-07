## MODIFIED Requirements

### Requirement: A change with no behaviour change carries no spec delta

A change with no externally visible behaviour change, such as a refactor, tooling, docs, or a rule about how a skill file is worded, SHALL set `skip_specs: true` in its `.openspec.yaml` and write no spec delta, rather than invent a requirement to pass validation.

#### Scenario: A docs-only change

- **WHEN** multi-spec's authoring agent writes a change that alters no behaviour
- **THEN** it sets `skip_specs: true` and writes no spec delta
- **AND** the post-check accepts the change

## ADDED Requirements

### Requirement: Change artifacts are short and plain

A change's spec delta SHALL state behaviour only, in plain words, without history, reasons, measurements or coined terms. Its design.md, when written, SHALL fit one page, giving each decision with one line of why and one line per rejected alternative. Its tasks SHALL cite headings rather than line numbers, and a `measured:` note SHALL give the value.

#### Scenario: Authoring a change with a design decision

- **WHEN** an authoring agent writes a change that needs design.md
- **THEN** each decision is one choice, one line of why, and one line per rejected alternative
- **AND** the spec delta states behaviour without history or measurements
