## ADDED Requirements

### Requirement: An overlay cannot relax a stop, a protected-area rule or a field another skill reads

A skill SHALL apply its overlay `cla.io/overlays/<skill>.md` only to add rules or narrow its own, SHALL follow its own rule when an overlay line would relax a stop, a protected-area rule or a report field another skill reads, and SHALL tell the user which overlay line it did not apply.

#### Scenario: An overlay line removes a stop

- **WHEN** an overlay line tells a skill to skip a stop the skill itself requires
- **THEN** the skill stops as its own rule says and names the overlay line it did not apply

#### Scenario: An overlay changes the wording of a report

- **WHEN** an overlay changes the order or wording of a report in a way no other skill reads
- **THEN** the skill applies it
