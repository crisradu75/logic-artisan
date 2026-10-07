# run-ledgers Specification

## Purpose

How skills record their runs and how those records are read: aggregators that survive bad records and say what they lost, and the run-log fields that a deferred decision waits on.

## Requirements

### Requirement: A malformed record costs one record, and the loss is counted

A retro aggregator SHALL treat a malformed record as one lost record, never a lost run: it skips the bad field, analyzes every other record, and exits successfully. When the skipped field feeds a metric, the aggregator SHALL count it in its structured output, naming the field, not only warn about it. The output SHALL show beside the record count how many records were dropped this way, reporting zero for a clean ledger rather than omitting it.

#### Scenario: One malformed record does not abort the aggregate

- **WHEN** a ledger holds a record whose field has a different container type than the aggregator expects
- **THEN** the aggregator skips that field, analyzes every other record, and exits successfully
- **AND** it does not return an empty result for the whole ledger

#### Scenario: A skipped record is counted, not only warned about

- **WHEN** an aggregator skips a field because its shape changed
- **THEN** the structured output counts it under the field's name
- **AND** a message on stderr alone does not satisfy this

#### Scenario: A degraded sample is visible beside the reported one

- **WHEN** some records are dropped from a metric while the reported record count includes them
- **THEN** the output carries a count of those records, so a reader can tell a whole sample from a partial one
- **AND** a clean ledger reports zero there rather than omitting the field

### Requirement: An aggregator reads several ledgers in one run

An aggregator SHALL be able to read several ledgers in one run, and SHALL NOT report a single ledger's path as the source of a result drawn from several. Given one path or none, it SHALL behave as it did before.

#### Scenario: Several ledgers aggregate into one result

- **WHEN** an aggregator is given more than one ledger path in a single run
- **THEN** it analyzes the records of all of them together
- **AND** the output names every path it read
- **AND** it reports no single-ledger source field for the result

#### Scenario: The single-ledger contract is unchanged

- **WHEN** an aggregator is given one ledger path, or none
- **THEN** it resolves and reports that one path as before
- **AND** a caller written against the single-ledger output works unmodified

### Requirement: A declined default names the ledger evidence that would reverse it

A default this workflow declines on thin evidence SHALL state the run-ledger condition that would reverse it. A second Revise round stays conditional until:

> Revisit the `--pr-rounds` default when `findings_by_round` covers at least eight changes across at least two distinct chains in which a round ≥ 2 ran, and a round ≥ 2 surfaced at least one Critical or Important finding on a majority of them.

Wherever this appears, the eight-change count and the majority bar SHALL be labelled as judgements, not measurements.

#### Scenario: The deferral is stated with its reversal condition

- **WHEN** a reader asks why a second Revise round is not the default
- **THEN** the skill states the deferral, the evidence behind it, and the reversal condition verbatim
- **AND** the eight-change count and the majority bar are labelled as judgements

### Requirement: The Revise record counts findings per round

The Revise phase record SHALL carry an optional `findings_by_round` array, one entry per dispatched round in round order, each with:

- `round`;
- `found`: that round's deduplicated Critical-plus-Important count;
- `sibling_instance`: how many of `found` were a defect the previous round's fix introduced or a sibling instance it missed. Round 1 records `0`. A later round records `null` when it was never asked that question, or its answer stayed uncited after the one re-dispatch, and `0` when it was asked and found none.

A record without the field stays valid, is not producer drift, and is not read as a round that found nothing. The schema SHALL state that, over agent-surfaced findings, the per-agent `found` sum is at least the per-round sum, since one finding reported by two agents counts twice per agent and once per round. It SHALL name the equality case (each finding reported by one agent), which is not drift, and the inverting case: a finding the orchestrator raises counts per round but in no agent's bucket.

#### Scenario: A run with two rounds is logged with per-round attribution

- **WHEN** the Revise phase runs two rounds and the run record is appended
- **THEN** `findings_by_round` holds one entry per round in round order
- **AND** round 1's entry carries `sibling_instance: 0`
- **AND** round 2's entry carries that round's own deduplicated Critical-plus-Important count and its sibling-instance count

#### Scenario: An older record without the field stays valid

- **WHEN** a run record written before this field existed is read from the ledger
- **THEN** the missing `findings_by_round` is not an error and is not counted as producer drift
- **AND** it is not read as a round that found nothing, which would be an entry with `found: 0`

#### Scenario: The two `found` counts are related by an inequality, not a prohibition

- **WHEN** a reader compares `findings_by_round`'s per-round `found` totals with the per-agent counts on the same record
- **THEN** the schema states the per-agent sum is greater than or equal to the per-round sum, and why
- **AND** it names the equality case, so a match is not read as producer drift
- **AND** it names the inverting case of a finding the orchestrator raises

#### Scenario: A round that produced no measurement is not logged as a zero

- **WHEN** a round ≥ 2 was never asked the question, or its answer stayed uncited after the one re-dispatch
- **THEN** that round's `sibling_instance` is `null`, not `0`
- **AND** a reader can tell it apart from a round that was asked and found none (`0`) and from a record with no `findings_by_round` at all

### Requirement: A ledger field kept for a deferred decision states when it qualifies and when it lapses

The run-log schema lists only fields an aggregator reads. For a field kept instead for a deferred decision, the schema SHALL state the test it qualifies under: a requirement archived into the plugin's own live spec names the field as the evidence its reversal condition reads, not prose in the same change. The test SHALL name the plugin's spec as the authority, not a path a consuming repo would resolve against its own tree. The schema SHALL also state the exit: when the condition is met or that requirement is removed, the field is added to the aggregator or dropped, and it SHALL say when that check happens.

#### Scenario: The exception names a test the change cannot self-certify

- **WHEN** a reader asks why a field no aggregator reads is listed in the schema
- **THEN** the schema states that the field qualifies only through a requirement archived into the plugin's live spec, not through prose in the same change

#### Scenario: A consumer can evaluate the test

- **WHEN** the schema is read in a repo that installed the plugin from the marketplace
- **THEN** the test names the plugin's own spec as the authority
- **AND** it does not require the reader to resolve a path against their own repository's spec tree

#### Scenario: The exception states when it lapses

- **WHEN** the requirement naming the field is removed, or its reversal condition is met
- **THEN** the schema says the field returns to the main rule
- **AND** it names when that check happens, since nothing runs it automatically
