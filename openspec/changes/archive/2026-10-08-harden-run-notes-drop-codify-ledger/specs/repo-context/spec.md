## MODIFIED Requirements

### Requirement: Reporting retired ledgers

`/cla:cla-init` SHALL list each retired run ledger present in the repo's `cla.io/retro/` and delete them only on the user's explicit yes, leaving every other file there untouched.

#### Scenario: Retired ledgers present

- **WHEN** `/cla:cla-init` runs where `cla.io/retro/` holds a retired ledger beside the live ones
- **THEN** it lists only the retired ledger and deletes nothing until the user agrees

#### Scenario: The user declines

- **WHEN** the user answers anything but yes
- **THEN** every listed ledger is kept and reported as kept

#### Scenario: The codify ledger

- **WHEN** `cla.io/retro/` holds the codify-learnings ledger
- **THEN** `/cla:cla-init` lists it as a retired ledger
