# run-ledgers — rationale

Why each requirement in `spec.md` exists. The spec states the behaviour; this file keeps the
evidence and reasoning behind it, moved verbatim when the requirements were compacted (#293).
Headings name the requirement each section explains.

## A retro aggregator treats a malformed record as one lost record

Its input is a ledger every producer writes as prose instructing a model, so a record of an unexpected shape is the expected case rather than the exceptional one; an aggregator that aborts on one hands the whole repository's retrospective to whichever record is worst. Measured before this requirement existed: a single record carrying a count where a list belonged aborted the aggregate for a repository holding 26 runs.

## Shape drift that costs a metric is tallied in the structured output

The two are not alternatives. The rule is deliberately scoped to that class rather than to every warning: an entry-level note that changes no metric is worth a line on stderr and not a counter, and a rule wide enough to cover both would be satisfied by neither. A warning is written to a stream nobody reads after the fact, while the JSON is what the retro reasons from — so a class that only warns is invisible at exactly the moment it matters, and the metric it degraded reads identically to one computed over every record. This is not a new rule: `codify_aggregate.py`'s module docstring already states it, and this requirement makes it binding on both aggregators rather than on whichever one happened to be written more carefully.

## A partial sample is visible beside the record count

`runs_analyzed` reporting N while a phase metric ran on fewer than N is not a defect in the metric; it becomes one only when nothing in the output says so. Measured: 20 records across three repositories were dropped from every phase-derived metric while the reported sample size stayed whole.

## An aggregator reads several ledgers in one run

A retrospective's conclusions are bounded by its sample, and a single repository's sample is routinely too thin to carry them — measured here at 8 records against a fleet of 156, where the local sample put round-cap exhaustion at 4 of 5 and the fleet put it at 6 of 129. The two figures disagree because the local one is five records, not because either is wrong. Naming one path for a result drawn from several is worse than naming none, because it reads as provenance.

## A declined default names the ledger evidence that would reverse it

The proposal to make a second Revise round unconditional is declined. The evidence for it is a single
chain of three to four changes, one still in flight when it was recorded; every change that reached a
round 2 found something, which is a rate of one hundred percent on a denominator of four and is
suggestive rather than a base rate. A default is a cost every run pays and is priced against a base
rate, so the default stays where it is.

The two-chain floor is the originating decision's own. The eight-change denominator and the majority
bar are stated judgements rather than measurements, labelled as such so a later pass argues with a
written number instead of inventing one.

## The Revise record attributes findings to the round that surfaced them

That condition is not answerable from the run ledger as it stands: the Revise phase record carries
`rounds_used`, and the per-agent finding counts are summed across every round, so nothing attributes
a finding to the round that surfaced it.

## The two `found` counts are related by a stated inequality

The per-agent field credits one finding to every agent that surfaced it and counts phantoms, while
this one is deduplicated after triage. The inverting case — an INT-CAP/INT-SYC or SIR-TEST
re-verification hit, or a Critical on an orchestrator-specified remedy — exists because
`revise_findings_by_tier` is keyed strictly by canonical agent id. An assumed equality between two fields spelled `found` is
exactly the kind of invariant a later reader would act on, and an unqualified inequality is the same
mistake in the other direction.

## A round with no measurement logs `sibling_instance` as null

Round 1's `0` is a definition rather than a measurement: it has no previous fix.

## A ledger field kept for a deferred decision states the test it qualifies under

The run-log schema's rule is that it lists only fields the aggregator reads. A field kept for a
deferred decision rather than for the aggregator is an exception to that rule.

A deferral and the field that excuses it, authored together, certify each other, and anyone could
qualify an unread field by adding a paragraph naming it.

## The qualifying test names the plugin's own spec

The schema ships verbatim into consuming repos, where a path-shaped test naming this repo's spec tree
can never be evaluated.
