## ADDED Requirements

### Requirement: A merge commit that drops lines the other side added warns

The guard hooks SHALL warn, without blocking, when a commit that concludes a merge would leave out lines the merged-in side added since the merge base, naming each such file and some of its lost lines.

#### Scenario: One side taken whole

- **WHEN** an agent resolves a conflict by taking its own side of a file whole and commits the merge
- **THEN** the commit goes ahead with a warning naming the file and the other side's lines it lacks

#### Scenario: Both sides kept

- **WHEN** the resolution keeps every line the other side added
- **THEN** no warning is shown

#### Scenario: A line replaced on purpose

- **WHEN** the resolution replaces a line the other side added with a different one
- **THEN** the commit goes ahead with a warning naming that line and asking for a deliberate drop to be stated in the commit message
