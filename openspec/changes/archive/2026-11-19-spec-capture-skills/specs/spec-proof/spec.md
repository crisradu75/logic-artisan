## MODIFIED Requirements

### Requirement: A checker reports a change over its whole-change budget

`check_spec_proof.py` SHALL report each active change whose Markdown files hold more words in total, or whose specs hold more requirements in total, than the budget the repo's `openspec/config.yaml` rules state, reading both numbers from that file, and SHALL say when the config states no budget and so none was enforced.

#### Scenario: A change over its requirement budget

- **WHEN** an active change holds more requirements across all its specs than the config allows
- **THEN** the checker names the change and exits non-zero

#### Scenario: A change over its word budget

- **WHEN** the total words over every Markdown file of an active change exceed the config's word budget
- **THEN** the checker names the change and exits non-zero

#### Scenario: A config with no budget

- **WHEN** the config states no change budget
- **THEN** the checker enforces nothing for it and says no budget was enforced

### Requirement: A change can opt in to the protected budget

`check_spec_proof.py` SHALL hold a change whose proposal carries the line `Budget: protected` to the protected budget sentence in the config instead of the repo's, SHALL report any other `Budget:` value, or that line with no protected sentence in the config, and SHALL exit 2 on a budget number it cannot read.

#### Scenario: A change opts in to the protected budget

- **WHEN** a change's proposal carries the line `Budget: protected` and the config states a protected budget sentence
- **THEN** that change is held to the protected numbers and every other change to the repo's

#### Scenario: A Budget line the checker cannot honour

- **WHEN** a proposal's `Budget:` line has another value, or says `protected` with no protected sentence in the config
- **THEN** the checker reports a problem for that change

#### Scenario: A budget number in unreadable wording

- **WHEN** the config gives a budget number as words or with a space or a dot as thousands separator
- **THEN** the checker exits 2 naming the wording
