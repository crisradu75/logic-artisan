# domain-instructions

## MODIFIED Requirements

### Requirement: Agent rules file
The `AGENTS.md` the setup skill writes SHALL state, in under 200 lines, the domain's folders, the loop's folders and test set included, the note file-name patterns, how notes link, who may change each folder, the privacy rules and what not to do, and SHALL name no `index.md` or `log.md`.

#### Scenario: Agents file within limits
- **WHEN** the plugin's tests fill the `AGENTS.md` template with an invented domain
- **THEN** the result is under 200 lines, holds a write rule for `sources`, `attachments`, `_meta/query-log`, `_meta/conventions.md`, `AGENTS.md`, `mnemo.schema.yml`, `hubs`, `archive` and `_meta/tests`, and names neither `index.md` nor `log.md`
