## ADDED Requirements

### Requirement: A fix brief binds the defect and offers the remedy

A cla-plugin sub-agent brief whose purpose is to remedy a defect SHALL state the defect and the
proposed fix as separately-named fields carrying different authority, and SHALL NOT merge them into a
single instruction.

The **defect** — what is true now and why that is wrong — SHALL be **binding**: the dispatched agent
may not decide the defect is acceptable and stop. The **candidate remedy** — the fix the dispatching
orchestrator proposes — SHALL be **rejectable with reasons**, and a reasoned rejection SHALL be a
successful return rather than a failure return, so that the return status carries no penalty for
having been right.

The brief's terminal contract for such a dispatch SHALL ask for evidence that the **defect** is gone,
not evidence that the remedy landed. Concretely, `done` SHALL require the defect check named in the
brief — the command or read that exhibits the defect — re-run with its output showing the defect
absent, in addition to whatever work evidence the contract already requires. The contract SHALL state
explicitly that evidence the candidate remedy was applied is NOT evidence the defect is gone, because
a compliant agent that implements a wrong remedy returns work evidence that is entirely genuine, and
the regression it ships is indistinguishable from success under a contract keyed on the remedy.

A brief that cannot name a defect check SHALL be treated as a brief whose defect is not grounded,
rather than as a case exempt from the contract.

The dispatching skill SHALL NOT achieve this by adding a permission for the agent to disagree while
leaving the terminal contract unchanged. A permission stated beside an instruction that carries a
deliverable does not reach a compliant agent; what the terminal contract *requires* is the only lever
that does.

Where a brief format is shared across skills and cited by slot name, this SHALL be introduced as a
second form of the existing task slot rather than as an additional slot, so that citing sites naming
the slot list remain correct.

#### Scenario: A fix brief separates the two fields

- **WHEN** a skill dispatches an agent to remedy a defect
- **THEN** the brief names the defect in its own field, marked binding
- **AND** it names the candidate remedy in a separate field, marked rejectable
- **AND** the two are not merged into one instruction sentence

#### Scenario: The terminal contract asks for defect-gone evidence

- **WHEN** a fix dispatch's terminal contract is stated
- **THEN** `done` requires the brief's named defect check, re-run, with output showing the defect absent
- **AND** the contract states that evidence the remedy was applied is not evidence the defect is gone
- **AND** a return claiming `done` without defect-gone evidence is treated as not done

#### Scenario: A reasoned rejection is a successful return

- **WHEN** the dispatched agent finds the candidate remedy wrong
- **THEN** it returns a rejection status distinct from the blocked status, with its reason
- **AND** that return is treated as a successful outcome, not a delegate failure
- **AND** the orchestrator's response is to re-decide the remedy rather than to resolve a blocker

#### Scenario: The slot list is not renumbered

- **WHEN** the fix-brief form is added to a shared brief format cited by slot name
- **THEN** it is introduced as a second form of the existing task slot
- **AND** no slot is renamed, renumbered, or added
- **AND** every site citing the brief by slot name remains correct without edits

#### Scenario: A brief that cannot name a defect check

- **WHEN** an orchestrator authoring a fix brief cannot name a check that exhibits the defect
- **THEN** the brief is treated as one whose defect is not grounded
- **AND** it is NOT treated as a dispatch exempt from the terminal contract
- **AND** the stated remedy is to ground the defect before dispatching, not to waive the field

#### Scenario: Every site restating the terminal contract states the same one

- **WHEN** the terminal contract is restated outside the brief that defines it
- **THEN** every site briefing a dispatch that remedies a defect states the three-status form
- **AND** a site briefing a dispatch that never remedies a defect is left unchanged
- **AND** no fix dispatch briefs against a contract with fewer statuses than the definition carries

### Requirement: A rejected remedy has a receiving branch in the fix loop

A skill whose fix loop triages findings into outcomes SHALL define an outcome for a rejected remedy.
A rejection SHALL discharge the round's attempt at the finding without closing the finding, SHALL NOT
be counted as untriaged residue by the loop's exit gate, and SHALL NOT consume a round.

#### Scenario: A rejection is triaged rather than counted as residue

- **WHEN** a dispatched delegate returns a rejection of the candidate remedy
- **THEN** the fix loop's triage records it as a third outcome beside applied and deferred
- **AND** the exit gate does not count that finding as untriaged residue
- **AND** the round is not marked warn on account of the rejection

#### Scenario: A rejection reopens the remedy, not the finding

- **WHEN** a finding's remedy is rejected
- **THEN** the finding remains open and is re-attempted with a re-decided remedy
- **AND** the finding is not recorded as resolved by the rejection

#### Scenario: A rejection costs no round

- **WHEN** a round contains a rejected remedy
- **THEN** no round cap is raised and no additional round is consumed by the rejection

### Requirement: A brief's factual claims are checkable and carry their source

A cla-plugin brief that states a defect SHALL list the factual sub-claims the defect rests on — a
type's field list, a signature, a line number, a count — as separately-enumerated rows, each naming
the source that resolves it (a path with a line, or a runnable command). Such sub-claims SHALL NOT
ship as unattributed ground truth inside the defect prose, where nothing marks them as claims and
nothing tells the reader where they came from.

The dispatched agent's first action SHALL be to re-resolve each row against its named source, each row
resolving to verbatim evidence or an explicit not-found, per the grounding contract the plugin already
applies to review claims.

A wrong sub-claim SHALL NOT automatically void the defect. Three outcomes SHALL be distinguished:

1. Every row resolves as stated — the agent proceeds.
2. A row is wrong **and** the defect does not survive its correction — the agent returns the remedy
   rejected, with the corrected row, and does not implement.
3. A row is wrong **but** the defect survives its correction — the agent corrects the row, proceeds,
   and reports the correction.

Corrections SHALL be returned in a required field that is printed with an explicit empty marker when
there are none, and SHALL NOT be omitted when empty: an omitted field and a field nobody filled in are
indistinguishable to the reader, which defeats the purpose of requiring it.

#### Scenario: The defect's factual sub-claims are enumerated with sources

- **WHEN** a fix brief states a defect resting on a field list, a signature, a line number, or a count
- **THEN** each such claim appears as its own row rather than inside the defect prose
- **AND** each row names the path-with-line or the runnable command that resolves it

#### Scenario: The agent re-resolves the rows before implementing

- **WHEN** an agent receives a fix brief carrying fact rows
- **THEN** its first action is to re-resolve each row against its named source
- **AND** each row resolves to verbatim evidence or an explicit not-found

#### Scenario: A wrong sub-claim that the defect survives is corrected, not escalated

- **WHEN** a fact row is wrong and the defect remains real once the row is corrected
- **THEN** the agent corrects the row and proceeds with the work
- **AND** it returns the correction in the required corrections field

#### Scenario: A wrong sub-claim that the defect depends on stops the work

- **WHEN** a fact row is wrong and the defect does not survive the row's correction
- **THEN** the agent returns the remedy rejected with the corrected row
- **AND** it does not implement the candidate remedy

#### Scenario: The corrections field is never omitted

- **WHEN** an agent returns from a fix dispatch having found no wrong fact rows
- **THEN** the corrections field is present with an explicit empty marker
- **AND** it is not omitted from the return

### Requirement: An orchestrator-specified remedy is reviewed as a decision

A cla-plugin skill that applies fixes SHALL NOT let a remedy the orchestrator itself specified escape
the scrutiny a delegated remedy receives. A delegated remedy is reviewed by the agent that may reject
it; an orchestrator-applied remedy has no such reader, because the party that decided it is also the
party triaging the findings on it.

Where the fix is applied by the orchestrator itself — below a delegation threshold, or in a
pre-implementation artifact-fix loop where no delegate exists — the orchestrator's own post-fix
re-verification SHALL additionally check the applied remedy against the change's own design document,
specifically its rejected-alternatives or explicitly-rejected-decisions content, and confirm the
remedy does not reintroduce something that document rejected. The design document SHALL be the named
source for this check; the proposal and the task list SHALL NOT be substituted for it.

**A hit is a Critical finding on the fix itself, not a note.** Where the check finds that the applied
remedy reintroduces something the design document rejected, the skill SHALL treat it as a Critical
finding against that remedy and SHALL NOT let the fix stand on the reasoning that it resolved the
original finding — resolving one finding by reintroducing a rejected decision is the failure this
check exists to catch, and it is indistinguishable from success on the original finding's own
evidence. The remedy SHALL be withdrawn or re-specified, and where the design document's rejection is
the thing now judged wrong, that document SHALL be amended explicitly rather than contradicted
silently; "the fix brief said so" SHALL NOT be accepted as an amendment.

Each such remedy SHALL be **marked** on the round's finding record as orchestrator-specified, so that a
later reader can tell which changes had no independent author. Where a later review round runs over
that diff, the marked hunks SHALL be named to it along with the same rejected-alternatives check. Where
no later round runs, the marks SHALL surface in the skill's terminal report.

This obligation SHALL NOT be discharged by raising a round cap or by making an additional round
unconditional. The control is in-round and is deliberately weaker than an independent reader; the
skill's text SHALL say so rather than implying the two are equivalent.

#### Scenario: An orchestrator-applied fix is checked against the rejected alternatives

- **WHEN** the orchestrator applies a fix for a finding itself rather than delegating it
- **THEN** its post-fix re-verification reads the change's design document rejected-alternatives content
- **AND** it confirms the applied remedy does not reintroduce a rejected alternative

#### Scenario: The check finds a reintroduced rejected alternative

- **WHEN** the rejected-alternatives check finds that the applied remedy reintroduces a rejected decision
- **THEN** it is raised as a Critical finding against that remedy
- **AND** the remedy is withdrawn or re-specified rather than allowed to stand on having resolved the original finding
- **AND** where the rejection itself is judged wrong, the design document is amended explicitly rather than contradicted silently

#### Scenario: The remedy is marked for the next reader

- **WHEN** a fix round contains a remedy the orchestrator specified
- **THEN** that finding's record carries an orchestrator-specified marker
- **AND** a later review round over that diff is told which hunks carry the marker
- **AND** where no later round runs, the marker appears in the terminal report

#### Scenario: The control does not change a round cap

- **WHEN** this obligation is stated in a skill
- **THEN** no round cap or default round count is raised to satisfy it
- **AND** the text states that the in-round check is weaker than an independent reader

#### Scenario: The check reads the document as it stood before the remedy

- **WHEN** the orchestrator's remedy is itself an edit to the rejected-alternatives document
- **THEN** the check reads the committed version of that document, not the working tree
- **AND** a remedy is never adjudicated against a document the same remedy just edited

#### Scenario: A fix loop with no rejected-alternatives document is out of scope

- **WHEN** a skill applies orchestrator-specified fixes but operates on no change directory
- **THEN** it has no rejected-alternatives document and the check does not bind it
- **AND** the obligation is stated as conditional on such a document existing
- **AND** the absence of the document is not reported as a breach of the obligation

