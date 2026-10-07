## MODIFIED Requirements

### Requirement: Sequencing edges beyond the source dependency graph

A skill that sequences a batch of changes SHALL find, before the batch runs, two edges a dependency list cannot express, and SHALL name both wherever it states its merge policy, including hoisted summaries.

- **Shared environment state.** A change that migrates a shared environment, seeds shared fixture data or provisions infrastructure SHALL be merged before the next change starts, whether or not anything depends on its code. The skill SHALL decide this per change from its artifacts, show how it reached a "no", decide it in every autonomy mode, and enforce it when merging. A policy that performs no merges SHALL surface the conflict rather than proceed.
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

- **WHEN** sequencing finds a shared-state edge for a named change
- **THEN** multi-pr merges that change before starting the next one
- **AND** recording the edge in a run artifact that nothing acts on does not satisfy the requirement

#### Scenario: The determination survives an autonomy mode

- **WHEN** a mode pre-answers the pre-flight gate with recommended defaults
- **THEN** the shared-state determination is still made per change, from artifacts
- **AND** it appears with its derivation in that mode's required output

