# run-ledgers Specification

## Purpose

How skills record their runs and how those records are read: aggregators that survive malformed records, and the evidence a ledger must carry for a deferred or declined decision. The reasoning and measurements
behind each requirement are in `rationale.md`, under the same heading.

## Requirements

### Requirement: A retro aggregator treats a malformed record as one lost record

A retro aggregator SHALL treat a malformed record as one lost record, never as a lost run: it skips
the drifted field, analyzes every other record, and exits successfully.

#### Scenario: One malformed record does not abort the aggregate

- **WHEN** a ledger holds a record whose field carries a different container type than the aggregator expects
- **THEN** the aggregator skips that field, analyzes every other record, and exits successfully
- **AND** it does not abort, and does not return an empty result for the whole ledger

### Requirement: Shape drift that costs a metric is tallied in the structured output

Drift that costs an aggregator a field its metrics are computed from SHALL be tallied into
structured output, naming the field, not only warned about.

#### Scenario: A skipped record is counted, not only warned about

- **WHEN** an aggregator skips a field because its container shape drifted
- **THEN** the drift is tallied into the structured output, naming the field
- **AND** the tally is not satisfied by a message on the diagnostic stream alone

### Requirement: A partial sample is visible beside the record count

A count that skipped records SHALL be discoverable beside the count of records read. A clean
ledger reports zero there rather than omitting the field.

#### Scenario: A degraded sample is visible beside the reported one

- **WHEN** some records are dropped from a metric while the reported record count includes them
- **THEN** the output carries a count of the records that drifted, so a reader can tell a whole sample from a partial one
- **AND** a clean ledger reports zero there rather than omitting the field, so zero is a measurement rather than an absence

### Requirement: An aggregator reads several ledgers in one run

An aggregator SHALL be able to read more than one ledger in a single run, and SHALL NOT attribute a
multi-ledger result to a single ledger's path. Given one path or none, it SHALL behave as it did
before multi-ledger reading existed.

#### Scenario: Several ledgers aggregate into one result

- **WHEN** an aggregator is given more than one ledger path in a single run
- **THEN** it analyzes the records of all of them together
- **AND** the output names every path it read
- **AND** it does not report a single-ledger provenance field for a result drawn from several

#### Scenario: The single-ledger contract is unchanged

- **WHEN** an aggregator is given one ledger path, or none at all
- **THEN** it resolves and reports that one path exactly as it did before multi-ledger reading existed
- **AND** a caller written against the single-ledger output continues to work unmodified

### Requirement: A declined default names the ledger evidence that would reverse it

A default this workflow declines on thin evidence SHALL state the run-ledger condition that would
reverse it. A second Revise round stays conditional until:

> Revisit the `--pr-rounds` default when `findings_by_round` covers at least eight changes across at
> least two distinct chains in which a round ≥ 2 ran, and a round ≥ 2 surfaced at least one Critical
> or Important finding on a majority of them.

Its eight-change denominator and majority bar SHALL be labelled judgements where they appear.

#### Scenario: The deferral is stated with its reversal condition

- **WHEN** a reader asks why a second Revise round is not the default
- **THEN** the skill states the deferral, the evidence behind it, and the reversal condition verbatim
- **AND** the eight-change denominator and majority bar are labelled as judgements rather than
  measurements

### Requirement: The Revise record attributes findings to the round that surfaced them

The Revise phase record SHALL carry `findings_by_round`: an array in round order, one entry per
dispatched round, each recording the round number, that round's deduplicated Critical-plus-Important
`found`, and `sibling_instance`: how many of that `found` were the round-≥2 question's target, a
defect the previous round's fix introduced or a sibling instance it missed. Round 1 records `0`.

#### Scenario: A run with two rounds is logged with per-round attribution

- **WHEN** the Revise phase runs two rounds and the run record is appended
- **THEN** `findings_by_round` holds one entry per round in round order
- **AND** round 1's entry carries `sibling_instance: 0`
- **AND** round 2's entry carries that round's own deduplicated Critical-plus-Important count and its
  sibling-instance subset

### Requirement: `findings_by_round` is optional and additive

`findings_by_round` SHALL be optional: a record written before it stays valid and is not producer
drift. An absent field SHALL stay distinguishable from a round that found nothing, which is an entry
with `found: 0`.

#### Scenario: An older record without the field stays valid

- **WHEN** a run record written before this field existed is read from the ledger
- **THEN** the absent `findings_by_round` is not an error and is not counted as producer drift
- **AND** it is not read as a round that found nothing, which would be an entry with `found: 0`

### Requirement: The two `found` counts are related by a stated inequality

The schema SHALL state that, over agent-surfaced findings, the per-agent `found` sum is greater
than or equal to the `findings_by_round` `found` sum, and name the equality case (every finding
surfaced by exactly one agent); a match SHALL NOT be read as producer drift. It SHALL name the one
inverting case: an orchestrator-originated finding enters the per-round total, no per-agent bucket.

#### Scenario: The two `found` counts are related by an inequality, not a prohibition

- **WHEN** a reader compares `findings_by_round`'s per-round `found` totals with the per-agent
  finding counts on the same record
- **THEN** the schema states the per-agent sum is greater than or equal to the per-round sum, and
  why: one finding surfaced by two agents is credited twice per-agent and once per-round
- **AND** it names the equality case — every finding surfaced by exactly one agent — so a match is
  not read as producer drift
- **AND** it names the inverting case — a finding the orchestrator originates, which lands in the
  per-round total and in no per-agent bucket

### Requirement: A round with no measurement logs `sibling_instance` as null

`sibling_instance` SHALL be JSON `null` when a round was never asked the round-≥2 question, or was asked
and its enumeration stayed uncited after the one re-dispatch. A round asked that found no sibling
instance writes `0`; round 1 writes `0` by definition.

#### Scenario: A round that produced no measurement is not logged as a zero

- **WHEN** a round ≥ 2 was never asked the question, or was asked and its enumeration stayed uncited
  after the one re-dispatch
- **THEN** that round's `sibling_instance` is `null`, not `0`
- **AND** a reader can distinguish it from a round that was asked and found no sibling instance,
  which is `0`, and from a record predating the field, which has no `findings_by_round` at all

### Requirement: A ledger field kept for a deferred decision states the test it qualifies under

The run-log schema lists only fields the aggregator reads; a field kept for a deferred decision is
an exception. The schema SHALL state the exception's qualifying test, not assert it for one field.
The test SHALL be one the field's own change cannot satisfy: a reviewed requirement archived into
the plugin's live spec names the field as the evidence its reversal condition reads.

#### Scenario: The exception names a test the change cannot self-certify

- **WHEN** a reader asks why a field the aggregator never reads is listed in the schema
- **THEN** the schema states that the field qualifies only on a requirement archived into the
  plugin's live spec, not on prose in the same change
- **AND** it gives the reason: a deferral and its own field would otherwise certify each other

### Requirement: The qualifying test names the plugin's own spec

The qualifying test SHALL be resolvable by a reader of the shipped schema: it names the plugin's
own spec as the authority, not a repo-relative directory a consumer would resolve against their own
tree.

#### Scenario: A consumer can evaluate the test

- **WHEN** the schema is read in a repo that installed the plugin from the marketplace
- **THEN** the qualifying test names the plugin's own spec as the authority
- **AND** it does not require the reader to resolve a path against their own repository's spec tree

### Requirement: The exception states its exit

The schema SHALL state the exception's exit: when the reversal condition is met, or the requirement naming
the field is removed, the field falls back under the main rule — added to the aggregator or
dropped.

#### Scenario: The exception states when it lapses

- **WHEN** the requirement naming the field is removed, or its reversal condition is met
- **THEN** the schema says the field loses the exception and returns to the main rule
- **AND** it names when that check happens, since nothing runs it automatically
