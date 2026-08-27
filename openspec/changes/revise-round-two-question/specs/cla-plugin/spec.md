## ADDED Requirements

### Requirement: A second Revise round asks a different question

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

### Requirement: The enumeration is made answerable, and its answer is checkable

A dispatch carrying the round-≥2 question SHALL supply the three things without which the
enumeration cannot honestly be produced. The question alone is not the mechanism; asking for a list
an agent has no way to build yields a confident list nobody built.

**The orchestrator SHALL name the resource.** It holds the finding, the remedy and the reason that
remedy was chosen; a dispatched agent holds a diff. The resource SHALL be named concretely enough to
bound the search — a function's call sites, a function's branches returning a given value, the
readers of a config key — rather than left for each agent to infer. An unnamed resource yields a
different scope per agent and nothing comparable between them.

**The dispatch SHALL grant the search.** The round's prompt inlines a scoped diff and instructs the
agent not to re-read it, and a sibling instance is by definition outside that diff. The prompt SHALL
therefore state that the agent may read and search the repository to answer this question, under the
read-only discipline the sub-agent brief already carries. Without the grant the question is
unanswerable as briefed.

**The return SHALL cite the search it ran**, and an enumeration that cites none is a **missing**
result rather than an empty one. A confident "no other instance" costs an agent nothing to write, so
the citation, not the conclusion, is what the orchestrator checks — by re-running the cited search
and comparing its hits against the enumerated list.

#### Scenario: The prompt names a bounded resource

- **WHEN** a round ≥ 2 is dispatched over a previous fix
- **THEN** the prompt names the specific resource or shape that fix concerns
- **AND** it does not leave each agent to infer the subject of the enumeration

#### Scenario: The agent is told it may search

- **WHEN** the dispatch carries the enumeration question
- **THEN** it states that the agent may read and search the repository to answer it
- **AND** that grant coexists with the instruction not to re-read the inlined diff, which governs the
  diff rather than the repository

#### Scenario: An uncited enumeration is not an empty one

- **WHEN** a return states that no other instance exists but names no search
- **THEN** the result is treated as missing rather than as an empty enumeration
- **AND** the round does not record it as a measured zero

### Requirement: The Revise round cap is a ceiling, not the loop's exit condition

Wherever the Revise round cap is stated, the skill SHALL also state that the loop ordinarily ends at the exit gate rather than at the cap.

`--pr-rounds` defaults to `2`. The loop's step "triage every Critical and Important finding" requires
each such finding to be resolved in the round that surfaced it, and the exit gate then counts
*untriaged* Critical and Important findings alongside *open* ones, exiting only when both are zero.
A reader who takes `default 2` as a promise of two rounds is reasoning about the wrong control, which
is precisely the misreading that makes the round-count question look already answered.

**The untriaged count is NOT zero by construction, and this requirement SHALL NOT say that it is.**
An earlier draft did. A rejection carrying no reason that resolves against the brief's own defect or
fact rows counts as untriaged at the gate, and the loop's own step 5 branches on the cap being
exhausted with findings still untriaged — a state a by-construction zero would forbid. The gate is
also two counts, not one: a loop with open findings is ended by the cap, so a zero untriaged count
would not on its own establish what ends the loop.

**That is what the text says, and practice diverges from it.** The run ledger records `rounds_used`
of 1, 2, 2 against a cap of 2 — two of three logged runs ran a second round the gate as written
should have ended. The statement this requirement obliges SHALL describe the exit gate as the
control **without asserting that a second round does not occur**, because a live specification
claiming a behaviour the ledger contradicts is a false statement with a specification's authority.
Reconciling the divergence — closing it upward or downward — is explicitly NOT this requirement's
job: closing it upward is the default change this change declines, and closing it downward would
delete an observed behaviour on the strength of a document.

This requirement is satisfied by an accurate statement at the sites that name the cap and at the exit
gate itself. It SHALL NOT change the cap's value, the exit gate's threshold, or anything that alters
how often a second round runs.

#### Scenario: The cap is named in the reference and in the skill stub

- **WHEN** a reader encounters the `--pr-rounds` default in either the Revise reference or the
  orchestrator skill's Revise stub
- **THEN** the same sentence tells them the default is a ceiling rather than a target
- **AND** it does not claim the untriaged count is zero by construction, because a reason-less
  rejection routes to untriaged and the cap does end a loop that still holds open findings

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
