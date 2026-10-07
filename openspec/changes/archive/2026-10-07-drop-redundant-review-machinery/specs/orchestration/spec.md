## MODIFIED Requirements

### Requirement: Sequencing edges beyond the source dependency graph

A skill that sequences a batch of changes SHALL find, before the batch runs, two edges a dependency list cannot express, and SHALL name both wherever it states its merge policy, including hoisted summaries.

- **Shared environment state.** A change that migrates a shared environment, seeds shared fixture data or provisions infrastructure SHALL be merged before the next change starts, whether or not anything depends on its code. The skill SHALL decide this per change from its artifacts, show how it reached a "no", decide it in every autonomy mode, and deliver it to the change it affects through the channel that carries inherited obligations. A policy that performs no merges SHALL surface the conflict rather than proceed.
- **Stale spec baselines.** A change carrying a MODIFIED block SHALL be re-validated against the live specs as they are when it runs (`openspec validate <change> --strict`), whether or not a sibling touches the same capability.
- The skill SHALL report which capabilities more than one change touches, with its denominator (changes scanned, changes with spec deltas, capabilities found), and SHALL report a failed enumeration as a failure, not as "no overlap".

#### Scenario: An independent change that moved shared state still merges first

- **WHEN** a change in a batch applies a migration, seeds shared fixture data, or provisions shared infrastructure
- **THEN** it creates a merge-before-next edge even though no other change depends on its code
- **AND** the sequencing step records that edge next to the change's dependency list

#### Scenario: A policy summary does not describe only the dependency edge

- **WHEN** a skill states a merge-policy default in terms of dependents and independents
- **THEN** the statement names the shared-environment-state edge as well as the source dependency
- **AND** it does so in the hoisted summary too, not only in the detailed reference

#### Scenario: A stale delta baseline is checked whether or not a sibling overlaps

- **WHEN** an in-scope change carries a MODIFIED block
- **THEN** it is re-validated with `openspec validate <change> --strict` against the live specs as they are when it runs
- **AND** the check runs even when no other in-scope change touches that capability
- **AND** the capabilities touched by more than one in-scope change are additionally named

#### Scenario: A check that could not run is not reported as a clean batch

- **WHEN** the enumeration of a change's spec deltas exits non-zero
- **THEN** it is reported as a failed check rather than as a change contributing no capabilities
- **AND** the result carries how many changes were scanned and how many carried deltas

#### Scenario: A finding reaches the review it is for

- **WHEN** sequencing produces a shared-state edge for a named change
- **THEN** it is delivered in the invocation that starts that change, by the channel already carrying inherited obligations
- **AND** recording it in a run artifact that nothing reads back does not satisfy the requirement

#### Scenario: The determination survives an autonomy mode

- **WHEN** a mode pre-answers the pre-flight gate with recommended defaults
- **THEN** the shared-state determination is still made per change, from artifacts
- **AND** it appears with its derivation in that mode's required output

### Requirement: The live specification set is validated where it is written

A skill that writes or hand-edits the live specs SHALL run `openspec validate --specs` before the commit that lands the edit; validating a change does not cover the live specs. This includes edits that pass through no delta and no archive. A failure SHALL halt, and in a chain of changes it SHALL be caught before that change's pull request merges. Warnings, such as a long requirement, are not failures.

#### Scenario: EVERY write site validates the live set, not only the change

- **WHEN** any phase in any skill materializes or edits the live specification set
- **THEN** that phase validates the live set before the commit that lands the edit
- **AND** a result naming a broken specification halts and surfaces rather than proceeding to commit
- **AND** a skill with one compliant write site and another that writes without validating does not satisfy this

#### Scenario: The no-delta, no-archive write site runs the check

- **WHEN** a skill edits a live specification in place, creating no delta and running no archive
- **THEN** that skill's own step runs the live-set validation before its commit
- **AND** this is satisfied by the check running at that site, not by another file describing the rule

#### Scenario: A chain validates before it merges

- **WHEN** a change in a sequence leaves the live specification set failing validation
- **THEN** it is treated as a structural failure that halts the sequence
- **AND** the check runs before that change's pull request is merged, so the failing specifications do not reach the base branch and the branch is still available to fix on
- **AND** it is not deferred to the next change, whose archive would fail instead

#### Scenario: A check that could not run is not reported as a broken specification

- **WHEN** the validation exits non-zero without naming a failing specification
- **THEN** it is reported as a tooling fault
- **AND** it is not attributed to the change's own specifications, and does not halt a sequence as a structural failure

#### Scenario: A run that validated nothing is not a pass

- **WHEN** the validation reports that it found no items to validate
- **THEN** that is distinguished from a clean result rather than recorded as success
- **AND** a repository not using the specification tooling has that stated once rather than accruing vacuous passes
