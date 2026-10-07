# run-ledgers Specification

## Purpose

How skills record their runs and how those records are read: aggregators that survive malformed records, and the evidence a ledger must carry for a deferred or declined decision.

## Requirements

### Requirement: A retro aggregator survives a malformed record and counts what it skipped

A retro aggregator SHALL treat a malformed record as one lost record, never as a lost run. Its input is a ledger every producer writes as prose instructing a model, so a record of an unexpected shape is the expected case rather than the exceptional one; an aggregator that aborts on one hands the whole repository's retrospective to whichever record is worst. Measured before this requirement existed: a single record carrying a count where a list belonged aborted the aggregate for a repository holding 26 runs.

**Drift that costs an aggregator a field its metrics are computed from SHALL be tallied into structured output, not only warned about.** The two are not alternatives. The rule is deliberately scoped to that class rather than to every warning: an entry-level note that changes no metric is worth a line on stderr and not a counter, and a rule wide enough to cover both would be satisfied by neither. A warning is written to a stream nobody reads after the fact, while the JSON is what the retro reasons from — so a class that only warns is invisible at exactly the moment it matters, and the metric it degraded reads identically to one computed over every record. This is not a new rule: `codify_aggregate.py`'s module docstring already states it, and this requirement makes it binding on both aggregators rather than on whichever one happened to be written more carefully.

**A count that skipped records SHALL be discoverable beside the count of records read.** `runs_analyzed` reporting N while a phase metric ran on fewer than N is not a defect in the metric; it becomes one only when nothing in the output says so. Measured: 20 records across three repositories were dropped from every phase-derived metric while the reported sample size stayed whole.

**An aggregator SHALL be able to read more than one ledger in a single run, and SHALL NOT attribute a multi-ledger result to a single ledger's path.** A retrospective's conclusions are bounded by its sample, and a single repository's sample is routinely too thin to carry them — measured here at 8 records against a fleet of 156, where the local sample put round-cap exhaustion at 4 of 5 and the fleet put it at 6 of 129. The two figures disagree because the local one is five records, not because either is wrong. Naming one path for a result drawn from several is worse than naming none, because it reads as provenance.

#### Scenario: One malformed record does not abort the aggregate

- **WHEN** a ledger holds a record whose field carries a different container type than the aggregator expects
- **THEN** the aggregator skips that field, analyzes every other record, and exits successfully
- **AND** it does not abort, and does not return an empty result for the whole ledger

#### Scenario: A skipped record is counted, not only warned about

- **WHEN** an aggregator skips a field because its container shape drifted
- **THEN** the drift is tallied into the structured output, naming the field
- **AND** the tally is not satisfied by a message on the diagnostic stream alone

#### Scenario: A degraded sample is visible beside the reported one

- **WHEN** some records are dropped from a metric while the reported record count includes them
- **THEN** the output carries a count of the records that drifted, so a reader can tell a whole sample from a partial one
- **AND** a clean ledger reports zero there rather than omitting the field, so zero is a measurement rather than an absence

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

A default this workflow declines to change on thin evidence SHALL carry a reversal condition stated against the run ledger.

The proposal to make a second Revise round unconditional is declined. The evidence for it is a single
chain of three to four changes, one still in flight when it was recorded; every change that reached a
round 2 found something, which is a rate of one hundred percent on a denominator of four and is
suggestive rather than a base rate. A default is a cost every run pays and is priced against a base
rate, so the default stays where it is.

The deferral SHALL name its reversal condition, verbatim:

> Revisit the `--pr-rounds` default when `findings_by_round` covers at least eight changes across at
> least two distinct chains in which a round ≥ 2 ran, and a round ≥ 2 surfaced at least one Critical
> or Important finding on a majority of them.

The two-chain floor is the originating decision's own. The eight-change denominator and the majority
bar are stated judgements rather than measurements, and SHALL be labelled as such where they appear,
so a later pass argues with a written number instead of inventing one.

That condition is not answerable from the run ledger as it stands: the Revise phase record carries
`rounds_used`, and the per-agent finding counts are summed across every round, so nothing attributes
a finding to the round that surfaced it. The Revise phase record SHALL therefore carry
`findings_by_round`: an array, in round order, with one entry per dispatched round, each entry
recording the round number, that round's deduplicated Critical-plus-Important `found` count, and
`sibling_instance` — of that `found`, how many were the shape the round-≥2 question targets, being a
defect the previous round's fix introduced or a sibling instance the previous round's fix missed,
which is `0` on round 1.

The field is optional and additive: records written before it stay valid, and an absent field is
distinguishable from a round that found nothing, which is an entry with `found: 0`.

The schema note SHALL state the relation between the two fields spelled `found` as an **inequality
with its equality case named**, not as a prohibition on equality. Restricted to findings an agent
surfaced, the sum of the per-agent `found` is **greater than or equal to** the sum of
`findings_by_round`'s `found`: the per-agent field credits one finding to every agent that surfaced
it and counts phantoms, while this one is deduplicated after triage. The two are **equal whenever
every finding was surfaced by exactly one agent**, which is common, so a match SHALL NOT be read as
producer drift. The note SHALL also name the one case that inverts the relation: a finding the
orchestrator originates rather than an agent — an INT-CAP/INT-SYC or SIR-TEST re-verification hit, or
a Critical on an orchestrator-specified remedy — enters the per-round total and no per-agent bucket,
because `revise_findings_by_tier` is keyed strictly by canonical agent id. An assumed equality
between two fields spelled `found` is exactly the kind of invariant a later reader would act on, and
an unqualified inequality is the same mistake in the other direction.

`sibling_instance` SHALL have a spelling for "no measurement was produced", distinct from both a
measured `0` and an absent `findings_by_round`. That spelling is JSON `null`. It is written when the
round was never asked the question, and when the round was asked and its enumeration stayed uncited
after the one re-dispatch. A round that was asked and found no sibling instance writes `0`. Round 1
writes `0`, which is a definition rather than a measurement: it has no previous fix.

#### Scenario: The deferral is stated with its reversal condition

- **WHEN** a reader asks why a second Revise round is not the default
- **THEN** the skill states the deferral, the evidence behind it, and the reversal condition verbatim
- **AND** the eight-change denominator and majority bar are labelled as judgements rather than
  measurements

#### Scenario: A run with two rounds is logged with per-round attribution

- **WHEN** the Revise phase runs two rounds and the run record is appended
- **THEN** `findings_by_round` holds one entry per round in round order
- **AND** round 1's entry carries `sibling_instance: 0`
- **AND** round 2's entry carries that round's own deduplicated Critical-plus-Important count and its
  sibling-instance subset

#### Scenario: An older record without the field stays valid

- **WHEN** a run record written before this field existed is read from the ledger
- **THEN** the absent `findings_by_round` is not an error and is not counted as producer drift
- **AND** it is not read as a round that found nothing, which would be an entry with `found: 0`

#### Scenario: The two `found` counts are related by an inequality, not a prohibition

- **WHEN** a reader compares `findings_by_round`'s per-round `found` totals with the per-agent
  finding counts on the same record
- **THEN** the schema states the per-agent sum is greater than or equal to the per-round sum, and
  why: one finding surfaced by two agents is credited twice per-agent and once per-round
- **AND** it names the equality case — every finding surfaced by exactly one agent — so a match is
  not read as producer drift
- **AND** it names the inverting case — a finding the orchestrator originates, which lands in the
  per-round total and in no per-agent bucket

#### Scenario: A round that produced no measurement is not logged as a zero

- **WHEN** a round ≥ 2 was never asked the question, or was asked and its enumeration stayed uncited
  after the one re-dispatch
- **THEN** that round's `sibling_instance` is `null`, not `0`
- **AND** a reader can distinguish it from a round that was asked and found no sibling instance,
  which is `0`, and from a record predating the field, which has no `findings_by_round` at all

### Requirement: A ledger field kept for a deferred decision states the test it qualifies under

The run-log schema's rule is that it lists only fields the aggregator reads. A field kept for a
deferred decision rather than for the aggregator is an exception to that rule, and the schema SHALL
state the exception's qualifying test and its exit rather than asserting the exception for one field.

**The test SHALL be one the field's own change cannot satisfy by itself.** A deferral and the field
that excuses it, authored together, certify each other, and anyone could qualify an unread field by
adding a paragraph naming it. A field therefore qualifies only when a requirement that has been
reviewed and archived into this plugin's live spec names it as the evidence that requirement's own
reversal condition reads — not prose written beside the field in the same change.

**The test SHALL be resolvable by a reader of the shipped file.** The schema ships verbatim into
consuming repos, where a path-shaped test naming this repo's spec tree can never be evaluated. The
test SHALL therefore name the plugin's own spec as the authority rather than a repo-relative
directory the consumer would resolve against their own tree.

**The exception SHALL state its exit**: when the reversal condition is met, or the requirement naming
the field is removed, the field falls back under the main rule — added to the aggregator or dropped.

#### Scenario: The exception names a test the change cannot self-certify

- **WHEN** a reader asks why a field the aggregator never reads is listed in the schema
- **THEN** the schema states that the field qualifies only on a requirement archived into the
  plugin's live spec, not on prose in the same change
- **AND** it gives the reason: a deferral and its own field would otherwise certify each other

#### Scenario: A consumer can evaluate the test

- **WHEN** the schema is read in a repo that installed the plugin from the marketplace
- **THEN** the qualifying test names the plugin's own spec as the authority
- **AND** it does not require the reader to resolve a path against their own repository's spec tree

#### Scenario: The exception states when it lapses

- **WHEN** the requirement naming the field is removed, or its reversal condition is met
- **THEN** the schema says the field loses the exception and returns to the main rule
- **AND** it names when that check happens, since nothing runs it automatically
