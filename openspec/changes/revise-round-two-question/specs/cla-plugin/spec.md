## ADDED Requirements

### Requirement: A second review round asks a different question

A Revise round N ≥ 2 SHALL be framed by a question distinct from round 1's, and MUST NOT be dispatched as a repeat of round 1 over a smaller diff.

Round 1 asks whether the diff is correct. A later round exists because the previous round's own fix
is new, unreviewed code written under time pressure by whoever had just diagnosed the defect, and the
defects it produces have a characteristic shape: the fix recreates the defect it removed, at a second
site, or it repairs the reported instance and leaves a sibling instance untouched. The question the
round asks SHALL therefore be, verbatim:

> Does this fix introduce the defect it fixed, somewhere else? Enumerate every other instance of the
> resource or shape the fix concerns.

The **enumeration is the deliverable, not the re-read.** The round's dispatch SHALL name every other
instance of the resource or shape the previous round's fix concerns, and state per instance whether
the defect is present there. An empty enumeration is a stated result — "no other instance exists" —
and SHALL NOT be an omitted step, for the same reason the deferred-findings sections print `(none)`
under an empty heading rather than dropping it: an absent section and an unexamined one read
identically.

The question and its enumeration obligation SHALL appear in the Revise reference's round-N ≥ 2
section, where the round's dispatch is assembled, AND as a load-bearing invariant in the
orchestrator skill's Revise stub, which is required to remain self-sufficient when the reference is
not reloaded.

#### Scenario: A later round is dispatched with the distinct framing

- **WHEN** the Revise loop dispatches a round N ≥ 2 over the previous fix commit's diff
- **THEN** the dispatch carries the round-≥2 question verbatim, not round 1's framing
- **AND** it instructs the reviewer to enumerate every other instance of the resource or shape the
  previous round's fix concerns

#### Scenario: The fix's own safety addition recreates the defect elsewhere

- **WHEN** round 1's fix for a count-versus-match divergence adds a cap that reintroduces the same
  divergence at a second call site
- **THEN** the round-2 enumeration lists that second site as an instance of the same shape
- **AND** the reintroduced divergence is reported as a finding of that round rather than shipping

#### Scenario: No other instance exists

- **WHEN** the round-2 reviewer finds that the resource or shape the fix concerns occurs nowhere else
- **THEN** it reports the enumeration as empty with that statement
- **AND** the empty enumeration is recorded as a result, not treated as a step that was skipped

#### Scenario: Round 1 is not asked the round-2 question

- **WHEN** the Revise loop dispatches round 1
- **THEN** the round-≥2 question is not part of that dispatch, because round 1 has no previous fix
  for it to be adversarial about

### Requirement: The Revise round cap is a ceiling, not the loop's exit condition

Wherever the Revise round cap is stated, the skill SHALL also state that the loop ordinarily ends at the exit gate rather than at the cap.

`--pr-rounds` defaults to `2`. The loop's step "triage every Critical and Important finding" requires
each such finding to be resolved into Applied or Deferred-Known-Issue **in the round that surfaced
it**, and the exit gate then counts *untriaged* Critical and Important findings and exits at zero. As
written, that count is zero by construction at the end of round 1, so the loop exits there and the
default cap never binds. A reader who takes `default 2` as a promise of two rounds is reasoning about
the wrong control, which is precisely the misreading that makes the round-count question look already
answered.

This requirement is satisfied by an accurate statement at the sites that name the cap and at the exit
gate itself. It SHALL NOT change the cap's value, the exit gate's threshold, or anything that alters
how often a second round runs.

#### Scenario: The cap is named in the reference and in the skill stub

- **WHEN** a reader encounters the `--pr-rounds` default in either the Revise reference or the
  orchestrator skill's Revise stub
- **THEN** the same sentence tells them the loop ordinarily ends at the exit gate, not at the cap
- **AND** it names the reason: every Critical and Important finding is triaged in the round that
  surfaced it, so the untriaged count is zero when round 1 finishes

#### Scenario: The clarification changes no numbers

- **WHEN** the clarification has been applied
- **THEN** the `--pr-rounds` default remains `2`, `--review-rounds` remains `1`, and `--test-rounds`
  remains `3`
- **AND** the per-loop caps table carries the same values it carried before the edit

#### Scenario: A run that stops after one round is not a capped run

- **WHEN** a run's record shows the Revise phase used one round against a cap of two
- **THEN** that run is read as having exited at the gate with every finding triaged, not as having
  been cut short by a budget

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
distinguishable from a round that found nothing, which is an entry with `found: 0`. The schema note
SHALL state that `findings_by_round`'s `found` is NOT expected to equal the sum of the per-agent
finding counts, because the per-agent field credits one finding to every agent that surfaced it while
this one counts a round's findings after triage dedup — an assumed equality between two fields
spelled `found` is exactly the kind of invariant a later reader would act on.

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

#### Scenario: The two `found` counts are not reconciled against each other

- **WHEN** a reader compares `findings_by_round`'s per-round `found` totals with the per-agent
  finding counts on the same record
- **THEN** the schema tells them the two are not expected to be equal, and why: one finding surfaced
  by two agents is credited twice per-agent and once per-round
