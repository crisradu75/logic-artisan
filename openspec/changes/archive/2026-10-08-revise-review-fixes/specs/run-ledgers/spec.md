## ADDED Requirements

### Requirement: Handoff suggests a retro on repeated trouble

After recording its run, `/cla:spec-to-pr` SHALL print one line suggesting `/cla:spec-to-pr-retro` when, among the repo's last five run records, the test phase used its whole round cap in at least three, the pull request review phase ended at its round cap with a warning or failure in at least three, or one warning reason appears in at least two, and SHALL print nothing otherwise, never blocking the run.

#### Scenario: Revise keeps ending at its cap with a warning or failure

- **WHEN** the pull request review phase ended at its round cap with a warning or failure in three of the last five runs
- **THEN** Handoff prints one line naming that and suggesting the retro

#### Scenario: Revise reaches its cap cleanly

- **WHEN** the pull request review phase used its whole round cap in each of the last five runs and never warned or failed
- **THEN** Handoff prints nothing for it

#### Scenario: A quiet ledger

- **WHEN** no phase hit its cap in three of the last five runs and no warning reason repeats
- **THEN** Handoff prints nothing extra and the run ends as before

## REMOVED Requirements

### Requirement: Handoff suggests a retro on recurring trouble

**Reason**: It named only a warning, while a review phase that failed at its cap counts too.

**Migration**: Restated as run-ledgers / Handoff suggests a retro on repeated trouble.
