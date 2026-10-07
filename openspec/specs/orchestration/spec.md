# orchestration Specification

## Purpose

How the build-and-ship orchestrators (`spec-to-pr`, `lite-pr`, `multi-pr`, `multi-lite`) carry a change through implementation, test, review fixes and merge: sequencing and merge policy, cross-change obligations, turn liveness, completeness and measurement evidence, fix briefs and the fix loop, delegate dispatch, Revise rounds, and resume.

## Requirements

### Requirement: Review-fix evidence gate

A skill that applies fixes for review findings SHALL require, before the commit that lands those fixes, that the fix be shown to be load-bearing: break what the fix touches and confirm a test fails. This gate SHALL be stated as **procedure the agent performs**, and a shipped skill SHALL NOT discharge it by mandating the invocation of a runner at the plugin root, because a consuming repo receives only the plugin's shippable assets and such a path may not resolve there.

The gate SHALL preserve, in the procedure text, the reasoning that makes it more than ceremony: that a fix for a Critical/Important finding is a change like any other and earns the same evidence the original code needed; that "the reviewer's finding is now handled" is not that evidence; that what is broken MUST be **what the fix touches**, not only what it targets, because correcting one return path routinely breaks another; and that a clean run is evidence about the mutants the author thought of and nothing else. A surviving mutant SHALL be fixed, or named in the skill's terminal report with a reason.

The gate SHALL further state that a **killed** mutant does not discharge it either: the kill establishes that the suite reacts to that edit, not that the code or the test is correct, so the assertion that killed the mutant SHALL be read and confirmed to state the wanted behaviour. Every shipped markdown file stating this gate SHALL carry that clause — a site restating the gate without it briefs its reader against a two-outcome contract in which a kill is self-certifying.

#### Scenario: The gate is stated without a plugin-root runner invocation

- **WHEN** a shipped skill's review-fix step states the mutation gate
- **THEN** the step describes the procedure to perform (break what the fix touches, confirm a test fails)
- **AND** it names no `${CLAUDE_PLUGIN_ROOT}` runner script to invoke

#### Scenario: The obligation survives the loss of its tooling

- **WHEN** the plugin no longer ships a mutation runner
- **THEN** the gate remains required before the fix commit
- **AND** an unresolved surviving mutant is still either fixed or named in the terminal report with a reason

#### Scenario: The named precedents are retained

- **WHEN** the gate's text is revised
- **THEN** it still states that the break must cover what the fix touches rather than only what it targets
- **AND** it still states that a clean run is evidence only about the mutants the author thought of

#### Scenario: A killed mutant does not discharge the gate

- **WHEN** a mutant is killed by an existing test
- **THEN** the gate requires the killing assertion to be read and confirmed to state the wanted behaviour
- **AND** the kill alone is not recorded as evidence that the code or the test is correct

#### Scenario: Every site stating the gate states the same contract

- **WHEN** more than one shipped markdown file states the mutation gate
- **THEN** each site carries the killed-mutant clause rather than only the site that was edited last

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

### Requirement: A small-change chain merges only what it tested and reviewed, under a policy confirmed per run

A skill that chains single small-change runs into a batch and may merge their pull requests SHALL merge only under a merge policy the user confirmed for that run, and SHALL offer a policy that merges every clean candidate as the chain goes as well as one that merges only what a later candidate needs — a candidate another depends on, or one whose changes move shared environment state. A chain that merges only what later candidates need leaves every other pull request open, each tested against the base it branched from and never against the others; merging each clean candidate as it passes makes every later candidate branch from, and test against, a base that already holds the earlier merges.

**The policy SHALL be confirmed at the run's single gate, and a mode that pre-answers that gate SHALL NOT widen merging on its own.** Where the invocation pre-confirms the plan without naming a policy, the narrower policy applies. A pre-confirmed plan is not an authorization to merge more than the invocation asked for.

**"Clean" SHALL mean more than a review verdict.** Before any merge, under either policy, the skill SHALL establish each of:

- no Critical or Important review finding is unresolved. Findings SHALL be counted from the reviewers' own reports rather than from a summary that need not list them. A finding the small-change run fixed counts as settled only when a change addressing it exists and that run reports no surviving mutant for it; a fix the chain applies itself SHALL be shown to work by breaking what it touches and confirming a test fails. A candidate whose findings cannot be counted — lost to a resume or to context loss — is unresolved;
- the pull request's head is the commit the run recorded, and the local checkout is exactly that commit with no uncommitted changes;
- the repository's full test gate is green on that commit. A source-affecting change with no test commands to run blocks the merge rather than passing; a change touching no source-affecting paths MAY skip the gate, and the skip SHALL be recorded and reported;
- the host reports no conflicts, no failing or still-pending checks, and no protection blocking the merge;
- the pull request's changed files have been checked for shared-environment state (a migration, seeded shared data, a provisioning step), with the derivation recorded. A match is a merge-before-next edge even when no candidate depends on it, and a check that could not run is treated as a match.

**A merge SHALL be confirmed by the host reporting it merged, not by the command's exit status.** A pull request that was only queued, or set to merge automatically later, SHALL be reported as such and SHALL NOT count as merged for a candidate that depends on it. A dependent candidate SHALL NOT run until its base is shown to contain that merge. A merge onto a base that moved after the branch was cut SHALL be reported as an untested merged tree.

**A resume SHALL NOT merge a head the run did not test and review, and SHALL NOT infer a candidate clean.** Commits pushed to a candidate's branch after the run recorded its head leave that pull request open for the user, whoever pushed them, and so does a pull request whose head the run never recorded. A candidate whose findings were not recorded before the interruption resumes as unresolved.

**A merge failure SHALL NOT halt the chain, except where it breaks every later candidate.** A candidate that cannot merge is left open with its reason, and anything that depends on it is skipped. A host that refuses the merge command itself SHALL stop further merging for the rest of the run rather than being retried under another spelling. A candidate whose changes move shared environment state and does not merge — whether a pre-merge check, an unresolved finding, or a moved head stops it — SHALL cause every later candidate to be skipped, per "Sequencing edges beyond the source dependency graph", and SHALL be reported first.

#### Scenario: The wider policy merges every clean candidate in order

- **WHEN** the user confirms the merge-each-clean policy and three independent candidates pass every pre-merge check
- **THEN** each merges as soon as it passes
- **AND** each later candidate branches from a base that holds the earlier merges

#### Scenario: A pre-confirmed run without a named policy merges only dependencies

- **WHEN** the invocation pre-confirms the plan and names no merge policy
- **THEN** only candidates a later candidate needs merged are merged
- **AND** the report states which policy applied and why

#### Scenario: A green review with an untested fix does not merge

- **WHEN** a candidate's review fixes were committed after its test phase, or an uncommitted fix sits in the working tree
- **THEN** the full test gate runs on the recorded head with a clean tree before any merge
- **AND** a red gate or a dirty tree leaves the pull request open with its reason

#### Scenario: A queued merge is not a merge

- **WHEN** the merge command exits successfully but the host reports the pull request still open, queued or set to merge automatically
- **THEN** the candidate is not recorded as merged
- **AND** a candidate depending on it is skipped

#### Scenario: A resume leaves pushed commits for the user

- **WHEN** a run resumes and a candidate's pull request head differs from the head the run recorded
- **THEN** that pull request is left open with a reason naming the moved head
- **AND** it is not re-reviewed, re-tested and merged by the resumed run

#### Scenario: Lost findings never count as clean

- **WHEN** a candidate's review findings cannot be counted, because a run resumed without them recorded or they were lost from context
- **THEN** the candidate is treated as carrying an unresolved finding
- **AND** it is not merged

### Requirement: Cross-change obligation carry

A skill that drives a SEQUENCE of changes SHALL treat an obligation one change creates for a later one as chain state that is both **recorded** and **delivered**, and SHALL NOT discharge it by recording alone. An obligation here is an addition a change's own review or fix round makes — a stored field, column, response key, or required behaviour — that the change itself does not consume, whose sole justification is that a named later change reads it. Such an obligation is invisible to every check scoped to a single change: the downstream change's artifacts stay internally consistent while never mentioning it.

The obligation SHALL be derived from what the prerequisite **actually became**, not from the batch as proposed. A chain plan's dependency list is a snapshot taken before any review round runs, and a prerequisite's review round is precisely where these obligations are created, so a downstream change reviewed against the plan is reviewed against a state its prerequisite has already left. The derivation SHALL also cover findings the run set aside as belonging to a **different** change: such a finding names its consumer explicitly, yet it is by construction absent from both the applied-findings list and the diff, so a derivation resting on those two alone discards the most explicit obligation available to it.

**The record SHALL remain readable across sessions.** Where the record lives in a per-run, date-named artifact, the reading step SHALL read the whole family of such artifacts rather than only the current run's, because a run resumed on a later date creates a new one — and a reader scoped to the current run's file makes every obligation an earlier session recorded invisible on precisely the path the mechanism exists to survive.

**Delivery SHALL travel in the invocation that starts the downstream change** — the same argument channel that already carries that change's caps and its stacked-chain base — so that recording an obligation and delivering it are not separable acts. A carry list the orchestrator writes and then does not feed into the dependent's own review is indistinguishable from never having written it, and SHALL NOT be accepted as satisfying this requirement.

When obligations are delivered, the downstream change's **pre-implementation** review SHALL emit one verdict per obligation — honoured, violated, or not addressed — as a required output field ahead of any other finding, and SHALL settle "not addressed" mechanically, by the absence of the obligation's literal token anywhere in that change's own artifacts, rather than by judgement. The count of verdict lines SHALL equal the count of delivered obligations; a missing line SHALL NOT read as a pass.

**The required field SHALL be defined where review behaviour is defined, not in the orchestrator that delivers it.** Where a plugin names one file as the single source of truth for a review's checks, report shape and verdict rubric, this field belongs in that file: an orchestrator-side copy prescribes a position in a template it does not own, and — where the review may be produced by dispatched agents rather than inline — reaches neither the agents' prompts nor the material they are given. The obligation SHALL be settled before any size or mode gate selects between review paths, so the answer does not depend on which path ran.

**A non-honoured verdict SHALL be wired into the verdict that selects the fix round**, not only reported: it SHALL be a Critical finding and SHALL exclude a "ready" verdict. A report that can pair "not addressed" with "ready" has a required field that changes nothing. Where the report format omits empty sections by default, this field SHALL be exempted — its honoured lines are the answer, and omitting them removes the evidence that anyone looked.

**A non-honoured obligation SHALL NOT be discharged by making the token match.** Pasting the token into narrative prose satisfies the mechanical check while changing nothing an implementer does; the discharge SHALL be an implementable task naming the field and its consumer, plus the requirement delta where the obligation is a required field or behaviour.

**Delivered obligations SHALL be answered on a resumed run.** Where phase-resumption is driven by a state probe, and that probe reports no state for the review phase, a resumed change skips review entirely — so the obligation step SHALL run regardless of the probe's verdict whenever obligations were delivered. The skill SHALL surface the verdict lines in its own terminal report so the delivering caller can count them against what it sent; without that count, a run that answered every obligation and one that discarded the delivery are indistinguishable to the caller — the same "written and fed nowhere" failure one layer up.

An empty carry SHALL be recorded explicitly rather than left as an absent section. It SHALL be recorded as the **derivation** — the counts each source yielded, at least one of them a command's output — and not as a bare marker word, because a bare marker is satisfiable by typing it and therefore only renames the "nobody looked" failure it is meant to exclude.

**A dedicated checker script SHALL NOT be added for this.** The per-obligation check is one `grep` for one token against one change directory, which the plugin's script bar — a script earns its place only by doing something a direct command plus a sentence of prose cannot do reliably — does not clear. The recurring failure was never that the grep was hard to run; it was that nobody was obliged to run it.

#### Scenario: The obligation is delivered, not merely recorded

- **WHEN** a change's review or fix round creates an obligation for a named later change in the chain
- **THEN** the obligation is recorded in the run's own notes with the token to grep for, the creating change, the owing change, and the failure if dropped
- **AND** the later change's invocation carries that obligation as an argument
- **AND** the recording step names the reading step, so a row written but never delivered is a defect rather than a completed step

#### Scenario: The carry is derived from the prerequisite's actual state

- **WHEN** a prerequisite's own review round adds a field after a dependent's artifacts were authored
- **THEN** the obligation is derived from the applied findings and the prerequisite's final diff
- **AND** it is not derived from the chain plan's description of that prerequisite

#### Scenario: The downstream review answers for each obligation by name

- **WHEN** a change is reviewed with inherited obligations delivered to it
- **THEN** the report opens with one honoured / violated / not-addressed line per obligation, before any other finding
- **AND** a token absent from the whole change directory yields "not addressed" without judgement
- **AND** a non-honoured verdict is a Critical finding applied to the artifacts before implementation

#### Scenario: The required field is defined where the reviewer reads it

- **WHEN** a plugin names one file as the single source of truth for review behaviour
- **THEN** the obligation field is defined in that file rather than in the orchestrator that delivers it
- **AND** it is settled before the gate that selects between an inline and a dispatched review
- **AND** the obligations reach whatever material a dispatched reviewer is given

#### Scenario: A non-honoured verdict changes the verdict

- **WHEN** a report carries a "not addressed" obligation line
- **THEN** the verdict cannot be "ready"
- **AND** the field is exempt from the rule that omits empty sections

#### Scenario: The discharge is implementable, not a matching token

- **WHEN** a "not addressed" obligation is fixed
- **THEN** the fix adds a task naming the field and its consumer
- **AND** a token pasted into narrative prose alone is re-flagged rather than accepted

#### Scenario: A resumed change still answers

- **WHEN** a change is resumed and the state probe reports no review-phase state
- **THEN** the obligation step runs anyway and emits its verdict lines
- **AND** the delivering caller can count those lines against the obligations it sent

#### Scenario: The record survives a resume on a later date

- **WHEN** the record lives in a per-run, date-named artifact and the run resumes on a later date
- **THEN** the reading step reads the whole family of those artifacts, not only the current run's

#### Scenario: An empty carry is written down as its derivation

- **WHEN** a change creates no obligation for any later change
- **THEN** that is recorded for that change as the counts its derivation sources yielded
- **AND** at least one of those counts is the output of a named command, so the entry is falsifiable rather than a word

### Requirement: Unattended-run turn liveness

A skill that drives a multi-step run designed to proceed without a human present SHALL state, among its hoisted skill-level rules, that a turn is never ended while nothing is pending that would re-invoke the session. The obligation SHALL be stated as a **check the agent can apply without judgement** — whether the message contains a tool call — rather than only as a prohibition on how a message reads, because the judgement form has been observed to fail in the one way that matters: an author writes a closing-shaped status report and then behaves like its reader.

The rule SHALL distinguish itself from the existing no-confirmation-prompt rules such skills already carry. Those forbid *asking permission*; this failure asks nothing, and an orchestrator hitting it believes it is continuing. The stated discriminator SHALL be whether a pending event will re-invoke the session — a backgrounded dispatch whose completion notification wakes it — and NOT whether a question was asked. The rule SHALL state that announcing the next step is not a mechanism.

The exhaustive set of conditions under which ending a turn is legitimate SHALL be exactly two: a backgrounded dispatch is genuinely in flight, or the run is complete. A skill SHALL NOT add a third. In particular it SHALL NOT admit "blocked on a decision already surfaced to the user", because that clause is satisfied by writing a paragraph and is therefore the shape a stalling orchestrator most easily adopts — a genuine blocker is surfaced with a tool call, which does not end the turn at all. Every skill stating this rule SHALL name the same two, so no two skills assert differently-sized exhaustive sets.

The rule SHALL be restated at the seam between units of work in whichever reference file carries that seam's procedure, because the seam is reached with the reference closed and the orchestrator running on the `SKILL.md` summary.

The rule's three properties — the mechanical check, the pending-event discriminator, and "announcing the next step is not a mechanism" — SHALL appear together in one block of prose rather than scattered across a file. A rule whose parts arrive separately can be gutted while each part survives somewhere, and a guard that checks for them file-wide cannot tell the two apart.

#### Scenario: The rule is stated mechanically, not only as a prohibition

- **WHEN** an unattended-run skill states its turn-liveness rule
- **THEN** the rule gives a check requiring no judgement (whether the message carries a tool call)
- **AND** it does not rest solely on the agent noticing that its own text reads as an ending

#### Scenario: The rule is distinguished from the no-pause rules

- **WHEN** the rule appears alongside an existing "no ready-to-continue pauses" rule
- **THEN** it states that the failure it covers asks the user nothing
- **AND** it names the pending-event discriminator rather than the asked-a-question one

#### Scenario: The seam carries its own restatement

- **WHEN** a skill's per-unit loop lives in a reference file
- **THEN** that file restates the obligation at the point where one unit ends and the next begins
- **AND** it says why the restatement is there rather than relying on the hoisted copy

#### Scenario: The exhaustive set is the same two everywhere

- **WHEN** two skills each state the turn-liveness rule
- **THEN** both name the same two legitimate conditions
- **AND** neither admits a third that a paragraph of prose could satisfy

#### Scenario: The rule's parts arrive together

- **WHEN** a skill states the rule
- **THEN** the mechanical check, the discriminator, and "announcing is not a mechanism" sit in one block
- **AND** a guard over them distinguishes that from the three merely appearing somewhere in the file

### Requirement: Completeness signals read the claim, not the glyph

A skill that reports a task list complete SHALL NOT rest that report solely on checkbox state. A checkbox count is a presence check on the glyph: it cannot distinguish a task that was done from one that was ticked. An artifact-presence flag is weaker still — it does not read task state at all — so neither is evidence that the work behind a task happened.

A task whose text asserts a **measurement** — a confirmed value, a count, a mutation-test result — SHALL record the measured value inline on the ticked line rather than the tick standing as its own evidence, and the post-check SHALL re-measure a small sample rather than trusting the ticks wholesale.

The skill SHALL state the underlying convention as well as enforcing it: a task is `[ ]` until it is done, and the prose beneath it explains why it is still open.

**A mechanical scan of a ticked task's body for self-negating text is NOT required, and the reason is recorded so it is not re-attempted blind.** It was built and withdrawn: measured over this repo's own archived `tasks.md` corpus — 173 ticked tasks — such a scan reached 6 lines, produced 0 true positives and 4 false positives, and its trip words collided with vocabulary the skills use deliberately. A repo whose task prose sits on the task line rather than beneath it gets no coverage from the obvious implementation. Anyone rebuilding it SHALL first measure the target corpus, and SHALL reuse the task parser the plugin already ships rather than hand-rolling one. Full evidence: GitHub issue #105.

#### Scenario: A measurement-bearing task carries its measurement

- **WHEN** a task asserts a confirmed value, a count, or a mutation-test result
- **THEN** the ticked line records the measured value
- **AND** a sample of such tasks is re-measured rather than trusted

### Requirement: A measurement names the command that produced it

A skill with a commit-creating step SHALL require, at every such step, that each measurement the
change asserts — a count, a coverage figure, "verified", "zero X", any number offered as fact, in the
diff, the commit message or the PR body — carries a `Measured-by: <command>` trailer naming a command
runnable as written.

- A claim with no runnable command SHALL be backed by running the command now, or deleted. It never
  ships with the command owed.
- A change asserting no measurement SHALL carry no trailer, and never a null line such as
  `Measured-by: none`.
- Checks every commit runs anyway (tests, linters, conformance scripts) are not claims and SHALL NOT
  get a trailer.
- The rule SHALL be stated at each pre-commit stop, where the author is already assembling the claims,
  not in authoring-time guidance. The author finds the claims; no keyword scan over the diff does.

#### Scenario: A change asserting a measurement carries its command

- **WHEN** a Ship step commits a change whose text asserts a count, a coverage figure, or any number offered as fact
- **THEN** the commit message carries one trailer per claim naming the exact command that produced it
- **AND** the command is a real invocation runnable as written

#### Scenario: A claim with no command is edited, not carried

- **WHEN** the author cannot name a command for a measurement the change asserts
- **THEN** the claim is either backed by running the command now or deleted and restated as reasoning
- **AND** no exit exists in which the claim ships with the command owed

#### Scenario: A change asserting nothing certifies nothing

- **WHEN** a change asserts no measurement
- **THEN** the commit message carries no measurement trailer
- **AND** a null certification line is not written in its place

#### Scenario: The rule binds at every commit chokepoint

- **WHEN** a skill states the obligation for a commit-creating step
- **THEN** it is stated after that step's pre-commit state check and before its commit, not among the skill's authoring-time guidance
- **AND** a skill with more than one commit-creating step states it at each, rather than at the first and by reference elsewhere

#### Scenario: A standing gate is not a claim the change asserts

- **WHEN** a change runs the pre-ship test suite, linters, and conformance scripts every commit runs
- **THEN** those results earn no trailer
- **AND** a trailer is written only for a number the change puts into the diff or the message

### Requirement: Deferred findings are separated by reason

A skill reporting findings it did not apply SHALL split them into named subsections distinguishing a hold that cannot be resolved now, a hold whose trigger has not fired, and an item skipped for neither reason. The third SHALL be mechanically detectable, so that a policy breach is found by a grep rather than by re-reading every item.

Collapsing all three under one label SHALL be treated as a defect rather than a formatting preference: undifferentiated, a genuine breach and a legitimate hold read identically, which leaves only two options — accept the section unread, or re-read it in full on every change.

#### Scenario: A skipped item is distinguishable from a legitimate hold

- **WHEN** a fix round reports items it did not apply
- **THEN** each appears under one of the three named subsections
- **AND** a non-empty "skipped" list fails the reporting phase under a no-deferrals policy

### Requirement: Planting doctrine is carried where tests are authored

The plugin SHALL carry, in a shared reference read at the point tests are authored, the rules that decide whether a test can fail at all. That reference SHALL distinguish rules applying to any test from rules applying only to a **gate** — a check whose feature is detecting something — and SHALL say which is which at its head, so a reader writing an ordinary unit test is not sent through gate doctrine that does not apply to them.

Where the reference states how a planted failure goes wrong, it SHALL give **checkable conditions rather than an exhortation**. "Confirm what moved" is not a condition; "diff the file and confirm the change is in the data, re-parse it and confirm it is well-formed, and read the failure message for the value you planted" is three.

The reference SHALL state that planting exercises only the implementation that exists, and therefore cannot reach an input the author never enumerated — and SHALL direct that anything parsing an external contract is enumerated from its primary source **before** it is planted against.

**A landed plant that dies.** The conditions above separate a plant that reached the value under test from one that missed. The reference SHALL also carry the case they do not reach, where the plant lands, the mutant dies, and the kill still establishes nothing: a test written from a wrong mental model kills mutants exactly as reliably as a correct one, so the green result reads as confirmation of the error. It SHALL give this trap its own remedy — read the killing assertion and confirm it states the wanted behaviour — rather than folding it into the did-it-land conditions, which every instance of it passes. It SHALL name the shape carrying the highest risk: a mutant that is the **simpler** form of the code, where if the simpler form is correct then the test defending the original is defending the defect.

**Scope boundary.** Guidance about when planting is worth its cost is routing, and SHALL NOT be read as narrowing any other obligation. In particular the **Review-fix evidence gate** stays unconditional: a fix for a review finding earns its evidence regardless of which technique supplies it. A reference stating both SHALL say so explicitly, because the two sit close enough to be read as one.

**Unreachability at the operating point.** The reference SHALL also carry the sibling case, where the enumerated input space is correct and the guard is nonetheless unreachable because the volume it meets in ordinary operation sits outside the range where it acts: a minimum-sample precondition larger than any real batch, a threshold pinned against a backfill-sized sample or against a different statistic than the code measures, or an alarm over an aggregate too coarse to see the sub-population that failed.

It SHALL require any new alarm, threshold or minimum-sample precondition to state the volume it will meet in ordinary steady-state operation **and the source of that figure**, so the number can be re-derived rather than guessed — the omission that produces this defect is an author choosing a number while holding a backfill-sized sample, which requiring the number alone leaves available. It SHALL require the guard's outcome to be stated at both ends of that range, since one end distinguishes "cannot fire" from "fires constantly" and neither end alone does.

It SHALL state where this sits relative to the planting rules rather than leaving the reader to infer it, and SHALL NOT claim the planting rules reach none of it. A plant against the live tree does not reach it — the comparison it fires is correct, and what goes unexamined is the precondition gating when that comparison runs — but a neighbouring rule whose remedy is to supply the check with bad state DOES reach it, conditionally on that state being sized to the real operating point. Where such a condition exists it SHALL be stated, because a reader told the neighbouring rules are irrelevant is steered away from the only remedy the reference offers.

#### Scenario: A reader is routed before being asked to read gate doctrine

- **WHEN** the shared test-quality reference is opened
- **THEN** its head names which sections apply to any test and which apply only to a gate

#### Scenario: The cost guidance does not narrow the review-fix gate

- **WHEN** the reference says a planted failure is unnecessary for some assertions
- **THEN** it states that this leaves the review-fix evidence obligation unchanged

#### Scenario: A trap is stated as something the reader can check

- **WHEN** the reference describes a plant that FAILED TO LAND on the value under test
- **THEN** it names the conditions distinguishing a landed plant from one that missed
- **AND** a trap of a different shape gives its own remedy rather than being forced into that form

#### Scenario: A plant that lands and kills is still examined

- **WHEN** the reference is read by someone whose plant landed and whose mutant died
- **THEN** it states that the kill proves the suite reacts to the edit, not that the code or the test is correct
- **AND** it directs the killing assertion to be read and confirmed to state the wanted behaviour
- **AND** it names the simpler-form mutant as the highest-risk shape

#### Scenario: A correct guard that cannot fire at its real volume is covered

- **WHEN** the reference is read by someone adding an alarm, threshold, or minimum-sample precondition
- **THEN** it requires the volume that alarm will meet in ordinary steady-state operation to be stated
- **AND** it requires both directions to be answered at that volume — that the alarm can fire, and that it fires only when it should
- **AND** it states that a plant against the live tree reaches none of this, because the comparison it fires is correct and what goes unexamined is the precondition gating when that comparison runs
- **AND** where a neighbouring rule's remedy does reach it, the condition under which it does is stated rather than left implicit

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

**Where a fix dispatch is briefed over more than one finding, its return SHALL carry a per-finding
outcome in addition to an overall status.** A dispatch spanning a set of findings whose return
carries only one status cannot express the ordinary mixed result — most findings remedied, one
remedy rejected — and forcing it into a single status either discards the completed work or hides
the rejection. Since every branch that consumes such a return triages, counts, and reports **per
finding**, the return SHALL be per finding too. A dispatch over a single finding SHALL use the same
contract, returning a one-row list, so that there is one contract rather than two.

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

#### Scenario: A permission to disagree does not satisfy the requirement

- **WHEN** a skill adds prose permitting the dispatched agent to disagree with the proposed fix
- **AND** the terminal contract's evidence requirement is left keyed on the remedy having been applied
- **THEN** the requirement is NOT satisfied
- **AND** the stated remedy is to change what `done` requires, not to add a further permission

#### Scenario: A dispatch over a set of findings reports each one

- **WHEN** a fix dispatch is briefed over more than one finding at once
- **THEN** its return carries one overall status AND one outcome row per finding the brief enumerated
- **AND** a finding whose remedy is rejected is identifiable from that list rather than only from the overall status
- **AND** a dispatch over a single finding returns a one-row list under the same contract

### Requirement: A rejected remedy has a receiving branch in the fix loop

A skill whose fix loop triages findings into outcomes SHALL define an outcome for a rejected remedy.
A rejection SHALL discharge the round's attempt at the finding without closing the finding, SHALL NOT
be counted as untriaged residue by the loop's exit gate, and SHALL NOT consume a round.

**Triaged and closed SHALL be distinguished, and the exit gate SHALL test both.** A loop whose exit
gate counts only untriaged findings SHALL NOT be considered to satisfy this requirement: a rejected
finding is triaged and still open, so such a gate reports the loop clean while a Critical finding is
live, and the skill's own completion signal then endorses shipping it. The gate SHALL count
*untriaged* findings (in no outcome) and *open* findings (in an outcome but not closed) separately,
SHALL require both to be zero to exit clean, and where open findings remain with budget available
SHALL re-enter the loop rather than exit.

**The terminal report SHALL carry a bucket for a rejected-but-open finding**, distinct from the
bucket for consciously-deferred findings and from the bucket for suggestion-level residue. An
outcome a report cannot print is an outcome nobody reads.

**Where a rejection cites a disproved defect, the finding SHALL be closed rather than re-attempted.**
Where the agent's stated reason is that a factual claim the defect rested on is wrong and the defect
does not survive its correction, re-deciding the remedy is the wrong next move — there is no defect
left to remedy — and a loop that re-attempts it will do so until its cap is exhausted. Such a finding
SHALL be recorded as closed by disproof, with the corrected claim as the evidence, and SHALL NOT be
recorded as fixed.

#### Scenario: A rejection is triaged rather than counted as residue

- **WHEN** a dispatched delegate returns a rejection of the candidate remedy
- **THEN** the fix loop's triage records it as a third outcome beside applied and deferred
- **AND** the exit gate does not count that finding as untriaged residue
- **AND** the round is not marked warn on account of the rejection

#### Scenario: A rejection reopens the remedy, not the finding

- **WHEN** a finding's remedy is rejected
- **THEN** the finding remains open and is re-attempted with a re-decided remedy
- **AND** the finding is not recorded as resolved by the rejection

#### Scenario: The exit gate does not release the loop on an open finding

- **WHEN** a round ends with a rejected finding triaged and still open, and no untriaged findings
- **THEN** the exit gate does not report the loop clean
- **AND** with budget remaining the loop re-enters rather than exiting
- **AND** at cap exhaustion the round is warned and the open finding is captured as residue

#### Scenario: A rejected finding has a home in the terminal report

- **WHEN** a run ends with a finding whose remedy was rejected and which is still open
- **THEN** the terminal report prints it under a bucket of its own
- **AND** it is not filed as a conscious deferral or as suggestion-level residue

#### Scenario: A rejection citing a disproved defect closes the finding

- **WHEN** the rejection's stated reason is that the defect does not survive the correction of a claim it rested on
- **THEN** the finding is closed rather than re-attempted with a re-decided remedy
- **AND** the corrected claim is recorded as the evidence of closure
- **AND** the finding is not recorded as fixed

#### Scenario: A rejection costs no round

- **WHEN** a round contains a rejected remedy
- **THEN** no round cap is raised and no additional round is consumed by the rejection

### Requirement: A brief's factual claims are checkable and carry their source

A cla-plugin brief that states a defect SHALL list the factual sub-claims the defect rests on — a
type's field list, a signature, a line number, a count — as separately-enumerated rows, each naming
the source that resolves it (a path with a line, or a runnable command). Such sub-claims SHALL NOT
ship as unattributed ground truth inside the defect prose, where nothing marks them as claims and
nothing tells the reader where they came from.

Each row SHALL additionally carry a **provenance tag** recording whether the claim was verified by the
party writing the brief or merely reported to it. Two values SHALL be distinguished: a claim someone
has actually resolved against its source, and a claim relayed from a dispatched agent's report without
independent resolution. Without the tag the source field says only where a claim *could* be checked,
not whether anyone did, and the rows the reader most needs to re-run are indistinguishable from the
rows already settled — which is the condition that let a four-field claim about a three-field type
ship as ground truth.

The tag SHALL apply to a brief's fact rows and SHALL NOT be required of a review report's claim table;
extending it there is a separate concern with a separate consumer.

The dispatched agent's first action SHALL be to re-resolve each row against its named source, each row
resolving to verbatim evidence or an explicit not-found, per the grounding contract the plugin already
applies to review claims. The brief SHALL state that resolving-quote-or-not-found rule in its own text
rather than only citing the document that defines it, because a dispatched agent reads the brief and
does not load the plugin's review checklist.

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
- **AND** each row carries a provenance tag saying whether the claim was independently resolved or relayed unverified

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

Each such remedy SHALL be **marked** as orchestrator-specified on the record the skill already keeps
for that finding's triage outcome, so that a later reader can tell which changes had no independent
author. The mark SHALL NOT be specified as a field of a structure the skill does not have. Where a
later review round runs over that diff, the marked hunks SHALL be named to it along with the same
rejected-alternatives check. Where no later round runs, the marks SHALL surface in the skill's
terminal report.

**Marking SHALL be required only where it discriminates.** In a fix loop that has no delegate at all,
every remedy is orchestrator-specified, so a per-remedy mark distinguishes nothing and its presence
would read as a signal it does not carry; there the fact SHALL be stated once for the loop instead.
Per-remedy marking SHALL be required where delegated and orchestrator-applied remedies can occur in
the same round. The adjudication check itself SHALL run on both.

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
- **THEN** the check reads that document as captured at the start of the fix round, before the round's edits
- **AND** a remedy is never adjudicated against a document the same remedy just edited
- **AND** the pre-edit content is obtained without requiring the document to be committed, since a fix loop that runs before the change is first committed would otherwise have no version to read

#### Scenario: A fix loop with no rejected-alternatives document is out of scope

- **WHEN** a skill applies orchestrator-specified fixes but operates on no change directory
- **THEN** it has no rejected-alternatives document and the check does not bind it
- **AND** the marking obligation does not bind it either, there being nothing for a later reader to check a mark against
- **AND** the obligation is stated as conditional on such a document existing
- **AND** the absence of the document is not reported as a breach of the obligation

### Requirement: A dispatched agent runs its gates in the foreground

A cla-plugin brief SHALL instruct the agent it dispatches to run every gate — build, lint, test, or
any other correctness command — in the foreground and to wait for it, however long it takes. The brief
SHALL state that the agent must not end its turn while a command it started is still running.

The rule SHALL key on **who is running the command**, not on the command's expected duration. A
duration threshold SHALL NOT be used for this decision, because duration is not what makes
backgrounding unsafe: a command of any length that a dispatched agent backgrounds before returning has
an unreachable result. The brief SHALL give the reason rather than only the prohibition — that a
backgrounded command does not survive the agent's return, and that ending its turn is what produces
that return, so no completion notification can reach it afterwards.

This SHALL NOT be stated as a third legitimate condition for ending a turn, and SHALL NOT weaken the
existing rule that an orchestrator session may end a turn with a backgrounded dispatch in flight. That
condition rests on a notification re-invoking the session, which is true of a session and false of a
dispatched agent; this requirement names the actor for whom the condition does not exist.

Where a gate's expected duration approaches or exceeds what a single foreground call permits in the
running harness, the skill SHALL NOT delegate that gate: the orchestrator runs it after the dispatch
returns, or dispatches the work without it and gates afterwards. An agent that meets such a gate SHALL
return the blocked status naming it rather than backgrounding it. The permitted foreground duration
SHALL be resolved against the running harness at dispatch time and SHALL NOT be written into the
shipped prose as a constant, since a constant is wrong in every harness whose limit differs.

#### Scenario: The brief requires foreground gates

- **WHEN** a skill briefs an agent that will run a correctness gate
- **THEN** the brief requires the gate to run in the foreground and to be waited for
- **AND** it forbids ending the turn while a started command is still running

#### Scenario: The rule keys on the runner, not the duration

- **WHEN** the foreground obligation is stated
- **THEN** it applies to the dispatched agent regardless of the gate's expected duration
- **AND** no duration constant is used to decide whether a gate may be backgrounded

#### Scenario: The orchestrator's own backgrounding is unchanged

- **WHEN** the obligation is stated alongside the existing turn-liveness rule
- **THEN** an orchestrator session may still end a turn with a backgrounded dispatch in flight
- **AND** no third legitimate turn-ending condition is introduced

#### Scenario: A gate too long to run in one call is not delegated

- **WHEN** a gate's expected duration approaches what one foreground call permits
- **THEN** the skill does not delegate that gate
- **AND** an agent that meets one returns blocked naming it rather than backgrounding it
- **AND** the permitted duration is resolved against the running harness rather than written as a constant

### Requirement: A return is classified by its evidence, not by its prose

A cla-plugin skill SHALL classify every return from a dispatch **whose brief declares a terminal-status contract** by a scan for the fields that brief required, performed before the return's prose is acted on. The scan SHALL check two things: that the return carries a status token from the closed set the brief named, and that it carries every evidence field the brief's terminal contract required.

**The scope is set by the brief, not by the fact of dispatching.** A dispatch whose brief declares no
status set and no evidence contract — a read-only gatherer returning a pass/fail table, a sweeper
returning a hit list, a reviewer returning severity-prefixed finding lines — is outside this
requirement, and a skill SHALL NOT classify such a return as blocked for lacking a token its brief
never asked for. This is the same test this change applies to its other obligations: a rule is
stated over a dispatch kind only where it is applicable to every instance of that kind. Where a
skill wants this protection for a gatherer-shaped dispatch, the way to get it is to give that brief a
terminal-status contract, not to widen the scan.

A return missing either SHALL be treated as **blocked**, whatever its prose says — including a return
that reads as finished, that reports a result, or that states it is waiting on something. The
classification SHALL be stated as a scan rather than a judgement, because the failure it covers
produces a return that reads exactly like a completion and the reader is the party least able to tell
the difference.

The skill SHALL NOT introduce an additional terminal status for this case. The existing statuses are
declared by the dispatched agent; this classification is made by the orchestrator about an agent that
declared nothing, so a status the agent could select is the wrong mechanism.

An evidence-free return SHALL be recorded as a contract firing in the run's issue record, on the same
footing as a return that claimed completion without evidence, so that the frequency of the failure is
observable rather than absorbed.

#### Scenario: An evidence-free return is blocked

- **WHEN** a dispatched agent returns without a status token or without a required evidence field
- **THEN** the orchestrator classifies the return as blocked
- **AND** it does so regardless of whether the return's prose reads as finished

#### Scenario: A dispatch with no declared status contract is out of scope

- **WHEN** a skill dispatches an agent whose brief declares no status set and no evidence contract
- **THEN** the return is not classified as blocked for lacking a status token
- **AND** the requirement's scope is read from the brief rather than from the fact that a dispatch occurred

#### Scenario: The classification is a scan, not a reading

- **WHEN** the classification rule is stated in a skill
- **THEN** it names the fields to look for and instructs the reader to look for them
- **AND** it does not rest on the reader judging how the return reads

#### Scenario: No status is added for the case

- **WHEN** the rule is stated
- **THEN** the terminal status set is unchanged
- **AND** the evidence-free return is classified as blocked rather than given a status of its own

#### Scenario: The firing is recorded

- **WHEN** a return is classified blocked for missing evidence
- **THEN** the event is recorded as a contract firing in the run's issue record
- **AND** it is not silently absorbed by recovering inline

### Requirement: One checkout has one writer, stated to both parties

A cla-plugin skill whose dispatched agents work in the orchestrator's own checkout SHALL state the
single-writer discipline in **both** directions, because a brief reaches only the agent and the party
that most needs binding is the one writing the brief.

**Agent-facing.** The brief's do-not-touch guidance SHALL name the repository-state-mutating commands
explicitly rather than stating the principle, and the enumeration SHALL include the commit and push
and reset verbs alongside the checkout, switch, branch, stash and worktree verbs, since an
implementing agent commits and a cleanup reset destroys work the orchestrator staged. It SHALL also
forbid two non-git shared resources: killing, restarting or cleaning up a process the agent did not
start, and deleting or regenerating a build, cache or dependency directory the agent did not create.

This guidance SHALL be standard in every dispatch rather than added per brief. The test for making it
standard SHALL be that no dispatch kind exists for which it is inapplicable — every dispatch shares the
orchestrator's checkout — which distinguishes it from a field whose honest content would be "not
applicable" in some dispatches and which therefore teaches readers to skim.

**Orchestrator-facing.** While a dispatch has not returned, or a command started under it may still be
running, the orchestrator SHALL run no repository-state-mutating git command and no gate in that
checkout, and SHALL delete or regenerate nothing that dispatch builds into. This SHALL be stated where
the orchestrator reads, and SHALL be placed as a further case of the skill's existing shared-checkout
guidance rather than as a separate section, because both cases are the same invariant — two agents
writing to one checkout — and separating one invariant into two documents lets them drift.

The skill SHALL additionally state that a failure observed in a checkout the orchestrator disturbed
while a dispatch of its own was live is **not evidence of a regression**, and SHALL require it to be
re-derived from a quiet tree before being investigated as one. This second half SHALL NOT be omitted on
the grounds that the first half prevents the situation: the recorded incident's cost was not the
interference but the investigation of self-inflicted failures as a possible real regression, which is
reached only after the first half has already failed.

#### Scenario: The agent-facing enumeration covers commit, push and reset

- **WHEN** a brief states which commands the dispatched agent may not run
- **THEN** the enumeration names the commit, push and reset verbs as well as checkout, switch, branch, stash and worktree
- **AND** it forbids killing a process the agent did not start
- **AND** it forbids deleting or regenerating a build, cache or dependency directory the agent did not create

#### Scenario: The prohibition is standard, not per-brief

- **WHEN** a skill dispatches any agent into the orchestrator's checkout
- **THEN** the prohibition is part of the standard brief rather than typed for that dispatch
- **AND** the justification given is that no dispatch kind exists for which it is inapplicable

#### Scenario: The orchestrator-facing half lives where the orchestrator reads

- **WHEN** the single-writer rule is written down
- **THEN** the orchestrator-facing half is placed in the skill's own shared-checkout guidance
- **AND** it is a further case of that guidance rather than a separate section
- **AND** it is not left to the brief, which reaches only the agent

#### Scenario: Manufactured failures are not treated as regressions

- **WHEN** a failure is observed in a checkout the orchestrator touched while its own dispatch was live
- **THEN** that failure is not treated as evidence of a regression
- **AND** it is re-derived from a quiet tree before being investigated as one

#### Scenario: The response to a missing return is re-dispatch, gated on quiet

- **WHEN** the orchestrator must act on a return that carried no evidence
- **THEN** it first confirms by read-only means that nothing the dispatch started is still running
- **AND** its default next move is one re-dispatch naming the omitted evidence fields
- **AND** it takes over the checkout only after that confirmation, never before it

### Requirement: A brief legitimises stopping rather than inventing a value

A cla-plugin brief SHALL state, as standard language in every dispatch rather than as a sentence typed
for a particular task, that every value its terminal contract asks for is one the dispatched agent
produced — not one it estimated, inferred, or carried over from an earlier run or another file.

The clause SHALL be placed adjacent to the evidence requirement it qualifies, because that requirement
is what creates the incentive it counteracts: a contract demanding a run summary puts an agent that
cannot run the command in a position where a plausible-looking value is the cheapest compliant output.
Placed elsewhere the clause is a statement of virtue; placed there it is the exception branch of the
rule above it.

An agent that cannot produce a required value SHALL return the blocked status naming the field it could
not fill and why, and the brief SHALL state that such a return is a **successful** return rather than a
failure, so that the honest answer carries no penalty. A value the agent did not itself produce SHALL be
a reportable defect, recorded as a contract firing, rather than treated as a formatting slip.

This SHALL compose with, and SHALL NOT contradict, the rule that a wrong factual claim supplied *in* a
brief is grounds for the agent to reject the proposed remedy. The two govern opposite directions:
inbound claims the orchestrator supplied are corrected or cause a remedy rejection; outbound evidence
the agent supplies is real or causes a blocked return. Neither resolves to proceeding with a guess, and
neither adds a terminal status beyond the shared set.

#### Scenario: The clause is standard and adjacent to the evidence requirement

- **WHEN** a skill states its brief's terminal contract
- **THEN** the no-invented-values clause is part of the standard contract text
- **AND** it sits beside the evidence requirement rather than elsewhere in the brief

#### Scenario: An unobtainable value produces a blocked return

- **WHEN** a dispatched agent cannot produce a value the contract requires
- **THEN** it returns blocked naming the field it could not fill and why
- **AND** the brief states that this is a successful return rather than a failure

#### Scenario: An invented value is a reportable defect

- **WHEN** a returned value was estimated, inferred, or carried over rather than measured
- **THEN** it is treated as a reportable defect and recorded as a contract firing
- **AND** it is not treated as a formatting problem to be tidied up

#### Scenario: Inbound and outbound claim rules do not collide

- **WHEN** both this clause and the inbound wrong-claim rule are stated in one brief format
- **THEN** a wrong claim the brief supplied leads to a correction or a remedy rejection
- **AND** evidence the agent cannot produce leads to a blocked return
- **AND** no terminal status beyond the shared set is introduced by either

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

### Requirement: A ticked task that names a test is checked for that test

spec-to-pr's Implement post-check SHALL search the tree for each test a ticked task names. A miss SHALL be recorded as a Handoff issue and the test finished inline, as for a done claim without evidence.

#### Scenario: A ticked test task whose test is missing

- **WHEN** a ticked task names a test that the search does not find
- **THEN** the run records a Handoff issue and writes the test before leaving Implement

### Requirement: multi-pr records Suggestions by default

multi-pr's recommended no-unresolved-issues policy SHALL fix every Critical and Important finding before a change counts done, and SHALL record Suggestion-level findings in `TODO.md` without fixing them. Fixing Suggestions too SHALL remain available as the full-severity choice at the Phase 1 gate.

#### Scenario: A change ships with a Suggestion open

- **WHEN** a change's Revise leaves only Suggestion-level findings under the default policy
- **THEN** the change counts done and the Suggestions are recorded in `TODO.md`

#### Scenario: The user picks full-severity

- **WHEN** the user picks the full-severity policy at the Phase 1 gate
- **THEN** Suggestion residue triggers a fix round before the change counts done

### Requirement: A change without design.md resumes at the right phase

spec-to-pr's resume probe SHALL report Implement's artifacts ready when OpenSpec reports `isComplete`, or when `applyRequires` is non-empty and every artifact it names has status `done`. A missing or empty `applyRequires` SHALL count as not ready.

#### Scenario: Resume on a change with no design.md

- **WHEN** `openspec status` reports `isComplete: false`, `applyRequires: ["tasks"]` and tasks `done`
- **THEN** the probe reports `implement: true`

#### Scenario: Required artifact not done

- **WHEN** an artifact in `applyRequires` is not `done` and `isComplete` is false
- **THEN** the probe reports `implement: false`

#### Scenario: No applyRequires

- **WHEN** `isComplete` is false and `applyRequires` is missing or empty
- **THEN** the probe reports `implement: false`

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
