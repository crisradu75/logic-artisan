# review-scan

## MODIFIED Requirements

### Requirement: Deferred metadata is not checked
The review skill SHALL report no note for lacking an optional field such as `questions` or `links`, or a field the plugin does not define such as `mnemo_schema_version`, SHALL report no domain for lacking a `hubs`, `archive` or `_meta/tests` folder, and SHALL neither create nor ask for an `index.md`.

#### Scenario: Notes with base fields only
- **GIVEN** a domain repo whose invented notes carry only valid base and type fields, with no `index.md`
- **WHEN** the review runs
- **THEN** the findings list holds no finding about those fields, folders or `index.md`, and no such file is created
