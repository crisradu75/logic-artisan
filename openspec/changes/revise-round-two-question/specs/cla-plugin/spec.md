## ADDED Requirements

### Requirement: A second Revise round asks a different question

A Revise round N ≥ 2 dispatched over a previous round's fix diff SHALL be framed by a question distinct from round 1's, and MUST NOT be dispatched as a repeat of round 1 over a smaller diff.

Two rounds fall outside that condition because neither has a "this fix" to ask about: a round entered
on an empty `PREV_FIX_SHA`, which reviews the whole PR, and a rejection-only re-entry, which
dispatches against open findings rather than a diff. On those the question SHALL be skipped rather
than asked ill-posed, and the round's `sibling_instance` SHALL be `null` rather than `0`, so the skip
is legible in the record instead of resting on prose the record cannot carry.

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

#### Scenario: A round with no fix to ask about skips the question

- **WHEN** a round ≥ 2 is entered on an empty `PREV_FIX_SHA`, or as a rejection-only re-entry
  dispatched against open findings
- **THEN** the round-≥2 question is not part of that dispatch, because there is no previous fix for
  it to concern
- **AND** that round's `sibling_instance` is `null`, so the skip is not later read as a measured zero

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

**That check SHALL resolve into one of three outcomes, each with a stated consequence**, because a
check whose failing branches are unwritten is a check that passes by default:

- **Cited and consistent** — the re-run search's hits are the enumerated list. The enumeration is
  taken as a result, and its confirmed sibling instances are counted into that round's
  `sibling_instance`, restricted to the Critical-plus-Important findings `found` counts, since
  `sibling_instance` is a subset of `found`.
- **Cited but inconsistent** — the re-run search returns hits the enumeration does not list. The
  unlisted hits SHALL be treated as unexamined and checked by the orchestrator before triage, rather
  than being read as instances the agent cleared.
- **Uncited** — the enumeration is missing rather than empty. The agent SHALL be re-dispatched once
  with the resource named; if the return is uncited again, the round's `sibling_instance` SHALL be
  `null` rather than `0`, and the outcome SHALL be captured as a Handoff issue.

That re-dispatch is an ordinary agent dispatch: its findings enter the round's counts and triage the
way any other agent's do, and it counts once toward the run record's dispatch and routing totals.
Only the enumeration *check* is count-neutral — it decides whether the round has an enumeration, and
changes no finding count by itself.

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
- **AND** the agent is re-dispatched once with the resource named
- **AND** if the second return is still uncited, the round records `sibling_instance` as `null` and
  the outcome is captured as a Handoff issue, rather than recorded as a measured zero

#### Scenario: A cited search that disagrees with its own enumeration

- **WHEN** the orchestrator re-runs the cited search and it returns instances the enumeration does
  not list
- **THEN** those unlisted instances are treated as unexamined and checked before triage
- **AND** they are not read as instances the agent inspected and cleared

#### Scenario: The re-dispatch is an ordinary dispatch

- **WHEN** an agent is re-dispatched because its enumeration was uncited
- **THEN** any findings it returns enter that round's counts and triage like any other agent's
- **AND** the dispatch is counted once in the run record's dispatch and routing totals
- **AND** the enumeration check itself changes no finding count

### Requirement: The Revise round cap is a ceiling, not the loop's exit condition

Wherever the Revise round cap is stated in the Revise reference or the orchestrator skill's Revise stub, the skill SHALL also state that the cap is a ceiling rather than a target.

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

**That is what the text says, and practice diverges from it.** Measured over
`cla.io/retro/spec-to-pr-runs.jsonl` with `python -c "import json;[print(r.get('change'),p.get('rounds_used'))
for r in map(json.loads,open('cla.io/retro/spec-to-pr-runs.jsonl',encoding='utf-8')) for p in
r['phases'] if p['name']=='Revise']"`: six records, `rounds_used` of `1, 2, 2, 2, (skipped), 2`
against a cap of 2 — **four of the five runs that ran Revise used a second round** the gate as
written should have ended.

So the statement this requirement obliges is deliberately narrow. It SHALL say that the cap is a
ceiling rather than a target, and it SHALL NOT assert what ordinarily ends the loop, because both
available assertions are false: the exit gate as written does not describe four of five logged runs,
and the cap does not describe the fifth. A live specification claiming a behaviour the ledger
contradicts is a false statement with a specification's authority. Reconciling the divergence —
closing it upward or downward — is explicitly NOT this requirement's job: closing it upward is the
default change this change declines, and closing it downward would delete an observed behaviour on
the strength of a document.

This requirement is satisfied by an accurate statement at the two sites that name the cap. It SHALL
NOT oblige an annotation at the exit gate itself: an earlier draft did, and the annotation it asked
for rested on the withdrawn "ordinarily ends at the gate" premise. It SHALL NOT change the cap's
value, the exit gate's threshold, or anything that alters how often a second round runs.

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
