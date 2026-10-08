## MODIFIED Requirements

### Requirement: Installing a pinned release

The plugin SHALL install into a repo with `claude plugin marketplace add crisradu75/logic-artisan` followed by `claude plugin install cla@cris-logic-artisan --scope project`, giving the release the marketplace pins to an exact `cla--v<version>` tag, and a newer release on `/plugin marketplace update`.

#### Scenario: A fresh install

- **WHEN** a repo runs the two install commands
- **THEN** the plugin's skills, agents and guard hooks are available in that repo's sessions
- **AND** the installed version is the one the pinned tag names
