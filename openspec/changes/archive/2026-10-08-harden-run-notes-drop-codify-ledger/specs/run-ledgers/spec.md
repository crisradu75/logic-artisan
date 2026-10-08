## REMOVED Requirements

### Requirement: Only checked run records are written

**Reason**: Rewritten as "Only checked spec-to-pr run records are written": the codify-learnings ledger is retired, since nothing read it.
**Migration**: A skill still writing the codify ledger gets a refusal line and finishes its run; `/cla:cla-init` offers to delete the file.

### Requirement: Run records ride the work's pull request

**Reason**: It covered "a skill's run record" in general, more than any recipe does. Rewritten as "The spec-to-pr run record rides its pull request" and "Chain run notes ride the last open pull request".
**Migration**: None; the behaviour it described is kept and narrowed to what the recipes do.

## ADDED Requirements

### Requirement: Only checked spec-to-pr run records are written

The writer SHALL append only to the spec-to-pr ledger, refusing a record for any other ledger or one whose fields or field values do not match the spec-to-pr record shape, printing one line that names the ledger it accepts or every field that does not match and leaving the ledger unchanged, and a skill whose record is refused SHALL correct it and try once more, then finish its run whether or not the record was written.

#### Scenario: Phases written as an object

- **WHEN** a spec-to-pr record gives its phases as an object instead of a list
- **THEN** the writer refuses it with a line naming `phases`, and the ledger is unchanged

#### Scenario: The retired codify ledger

- **WHEN** a skill writes to the codify-learnings ledger
- **THEN** the writer refuses it with a line naming the spec-to-pr ledger, and writes nothing

#### Scenario: A record refused twice

- **WHEN** a skill's corrected record is refused again
- **THEN** the skill reports that the record was not written and its run still finishes

### Requirement: The spec-to-pr run record rides its pull request

`/cla:spec-to-pr` SHALL commit its run record only on the branch of the pull request it opened, never on the base branch, and when it opened none SHALL leave the record uncommitted and say so in its report.

#### Scenario: A run that opened a pull request

- **WHEN** a run ends with its pull request open
- **THEN** its run record is committed on that pull request's branch

#### Scenario: A run that opened none

- **WHEN** a run ends without opening a pull request
- **THEN** its run record stays uncommitted and its report says so

### Requirement: Chain run notes ride the last open pull request

`/cla:multi-lite` and `/cla:multi-pr` SHALL commit only their own run's notes, only onto the branch of their last pull request still open at that moment and never onto the base branch, leaving the notes uncommitted, saying so and pushing nothing when no pull request is open, and a re-run SHALL read back its own committed notes even when another run's notes were committed later.

#### Scenario: A chain ends with a pull request open

- **WHEN** a chain finishes with at least one of its pull requests open
- **THEN** its own notes, and no other run's, are committed on the last open one's branch

#### Scenario: The last pull request merges before the commit

- **WHEN** the last open pull request merges and its branch is deleted just before the notes would be committed
- **THEN** the notes stay uncommitted, the report says so, and the deleted branch is not pushed again

#### Scenario: Another run committed notes later

- **WHEN** a chain is re-run after a different run's notes were committed onto another open pull request
- **THEN** the re-run reads back its own notes, not the other run's
