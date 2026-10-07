# orchestration Specification

## Purpose

How the build-and-ship skills (`spec-to-pr`, `lite-pr`, `multi-pr`, `multi-lite`) carry a change through implementation, testing, review fixes and merge, and how they brief and check the agents they dispatch.

## Requirements

### Requirement: A review fix is proven by breaking it and watching a test fail

A skill that applies fixes for review findings SHALL, before committing them, break what each fix touches (not only what it targets) and confirm a test fails. A fix earns the same evidence as any other change; "the finding is handled" is not that evidence. The skill SHALL state this as steps the agent performs, not as a call to a runner script at the plugin root, which a consuming repo may not have. Every shipped file that states this check SHALL also say that a clean run proves only the breakages the author tried, and that a caught breakage proves only that the suite reacts to it.

#### Scenario: The check is stated as steps, not a plugin-root script

- **WHEN** a shipped skill's review-fix step states the check
- **THEN** it describes breaking what the fix touches and confirming a test fails
- **AND** it names no `${CLAUDE_PLUGIN_ROOT}` script to run
- **AND** the check stays required even though the plugin ships no mutation runner

#### Scenario: A breakage no test catches

- **WHEN** a deliberate breakage of the fix leaves every test passing
- **THEN** the gap is fixed, or named with a reason in the skill's final report

#### Scenario: A caught breakage is not enough

- **WHEN** a test fails on a deliberate breakage
- **THEN** the assertion that failed is read and confirmed to state the wanted behaviour
- **AND** the failure alone is not recorded as proof that the code or the test is right
- **AND** every shipped file stating the check says so, not only the one edited last

### Requirement: A batch orders changes by shared state and stale specs, not only by code dependencies

A skill that sequences a batch of changes SHALL, before the batch runs, check each change for two things a dependency list cannot show, and SHALL name both wherever it states its merge policy, summaries included:

- **Shared environment state.** A change that migrates a shared environment, seeds shared data or provisions infrastructure SHALL merge before the next change starts, even if nothing depends on its code. The skill SHALL decide this for each change from its artifacts, in every autonomy mode, show how it reached a "no", and enforce the ordering when merging. A policy that performs no merges SHALL report the conflict rather than proceed.
- **Stale spec baselines.** A change with a MODIFIED block SHALL be re-validated with `openspec validate <change> --strict` against the live specs as they are when it runs.

The skill SHALL also report which capabilities more than one change touches, with how many changes it scanned and how many had spec deltas.

#### Scenario: An independent change that moved shared state still merges first

- **WHEN** a change in a batch applies a migration, seeds shared data, or provisions shared infrastructure
- **THEN** it must merge before the next change, even though no other change depends on its code
- **AND** that ordering is recorded next to the change's dependency list

#### Scenario: A stale delta baseline is checked whether or not a sibling overlaps

- **WHEN** a change carries a MODIFIED block
- **THEN** it is re-validated against the live specs as they are when it runs
- **AND** this happens even when no other change touches that capability

#### Scenario: A check that could not run is not reported as a clean batch

- **WHEN** listing a change's spec deltas exits non-zero
- **THEN** it is reported as a failed check, not as "no overlap"
- **AND** the result says how many changes were scanned and how many had deltas

#### Scenario: The shared-state ordering is enforced at merge

- **WHEN** sequencing finds that a named change moves shared state
- **THEN** multi-pr merges that change before starting the next one
- **AND** recording the ordering in a file nothing acts on does not count

#### Scenario: The decision is made in every autonomy mode

- **WHEN** a mode answers the pre-flight gate with recommended defaults
- **THEN** the shared-state decision is still made for each change from its artifacts, and shown with its reasoning

### Requirement: A small-change chain merges only what it tested and reviewed, under a policy confirmed per run

A skill that chains small-change runs and may merge their pull requests SHALL merge only under a policy the user confirmed for that run at its single gate. It SHALL offer one policy that merges every clean candidate as the chain goes, and one that merges only what a later candidate needs (a dependency, or a change that moves shared environment state). An invocation that pre-confirms the plan without naming a policy gets the narrower one.

Before any merge, under either policy, the skill SHALL establish that the candidate is clean:

- no Critical or Important finding is unresolved, counted from the reviewers' own reports. A fix counts only if it exists and its run reports no uncaught breakage; a fix the chain applies itself is proven by breaking it and seeing a test fail. Findings that cannot be counted (lost to a resume or to context loss) count as unresolved;
- the pull request's head is the commit the run recorded, and the local checkout is exactly that commit with no uncommitted changes;
- the full test suite passes on that commit. A source-affecting change with no test command blocks the merge; a change touching no source-affecting paths may skip the suite, and the skip is reported;
- the host reports no conflicts, no failing or pending checks, and no branch protection blocking the merge;
- the changed files were checked for shared environment state, with the reasoning recorded. A match, or a check that could not run, means the candidate must merge before the next.

A merge SHALL count only when the host reports it merged; a queued or merge-later pull request is reported as such. A dependent candidate SHALL NOT run until its base contains that merge, and a merge onto a base that moved since the branch was cut SHALL be reported as an untested merged tree. A resumed run SHALL NOT merge a head it did not record, test and review. A failed merge leaves that pull request open with its reason and skips its dependents without halting the chain, except that a host refusing the merge command itself stops all further merging for the run (with no retry under another spelling), and a shared-state candidate that does not merge, for any reason, skips every later candidate and is reported first.

#### Scenario: The wider policy merges every clean candidate in order

- **WHEN** the user confirms the merge-each-clean policy and three independent candidates pass every pre-merge check
- **THEN** each merges as soon as it passes
- **AND** each later candidate branches from a base that holds the earlier merges

#### Scenario: A pre-confirmed run without a named policy merges only dependencies

- **WHEN** the invocation pre-confirms the plan and names no merge policy
- **THEN** only candidates a later candidate needs are merged
- **AND** the report states which policy applied and why

#### Scenario: A green review with an untested fix does not merge

- **WHEN** a candidate's review fixes were committed after its test phase, or an uncommitted fix sits in the working tree
- **THEN** the full test suite runs on the recorded head with a clean tree before any merge
- **AND** a failing suite or a dirty tree leaves the pull request open with its reason

#### Scenario: A queued merge is not a merge

- **WHEN** the merge command succeeds but the host reports the pull request still open, queued, or set to merge automatically
- **THEN** the candidate is not recorded as merged
- **AND** a candidate depending on it is skipped

#### Scenario: A resume leaves pushed commits for the user

- **WHEN** a run resumes and a candidate's pull request head differs from the head the run recorded, or no head was recorded
- **THEN** that pull request is left open with a reason
- **AND** the resumed run does not re-review, re-test or merge it

#### Scenario: Lost findings never count as clean

- **WHEN** a candidate's review findings cannot be counted, because a run resumed without them recorded or they were lost from context
- **THEN** the candidate is treated as having an unresolved finding and is not merged

### Requirement: An obligation one change creates for a later change is delivered to it

An obligation here is something a change's review or fix round adds (a field, column, response key or behaviour) that the change does not use itself, only a named later change. A skill that drives a sequence of changes SHALL:

- derive obligations from what the earlier change actually became (its applied findings, its final diff, and findings it set aside as belonging to another change), not from the batch plan;
- record each one, and read the record from every run-notes file, not only the current run's, since a run resumed on a later date writes a new file;
- deliver it in the invocation that starts the later change, alongside that change's other arguments; recording without delivering does not count;
- record "no obligations" for a change as the counts each source yielded, at least one from a command, never as a bare word.

The later change's pre-implementation review SHALL open with one verdict line per delivered obligation (honoured, violated, or not addressed), decided before choosing between review paths and defined in the file that defines review behaviour, so dispatched reviewers get it too. "Not addressed" SHALL mean the obligation's token appears nowhere in the change's artifacts. A missing line is not a pass, and a non-honoured verdict SHALL be a Critical finding that rules out "ready". On a resumed change the obligation step SHALL run even if no review state is found, and the final report SHALL show the verdict lines so the caller can count them. The check SHALL stay a grep, not a new script.

#### Scenario: The obligation is delivered, not merely recorded

- **WHEN** a change's review or fix round creates an obligation for a named later change
- **THEN** the run notes record the token to grep for, the creating change, the owing change, and what breaks if it is dropped
- **AND** the later change's invocation carries the obligation as an argument

#### Scenario: The carry is derived from the prerequisite's actual state

- **WHEN** an earlier change's review round adds a field after a dependent change's artifacts were written
- **THEN** the obligation is derived from the earlier change's applied findings and final diff, not from the chain plan

#### Scenario: The downstream review answers for each obligation by name

- **WHEN** a change is reviewed with obligations delivered to it
- **THEN** the report opens with one honoured / violated / not-addressed line per obligation, before any other finding
- **AND** a token absent from the whole change directory yields "not addressed" without judgement
- **AND** a "not addressed" line rules out a "ready" verdict, and is shown even where empty sections are normally omitted

#### Scenario: The required field is defined where the reviewer reads it

- **WHEN** the plugin names one file as the source of truth for review behaviour
- **THEN** the obligation field is defined there, not in the skill that delivers it
- **AND** the obligations reach whatever material a dispatched reviewer is given

#### Scenario: The discharge is implementable, not a matching token

- **WHEN** a "not addressed" obligation is fixed
- **THEN** the fix adds a task naming the field and its consumer, plus a requirement change where the obligation is a required field or behaviour
- **AND** a token pasted into prose alone is flagged again

#### Scenario: A resumed change still answers

- **WHEN** a change with delivered obligations is resumed and the resume probe finds no review state
- **THEN** the obligation step runs anyway and its verdict lines appear in the final report

#### Scenario: The record survives a resume on a later date

- **WHEN** the record lives in dated run-notes files and the run resumes on a later date
- **THEN** the reading step reads every such file, not only the current run's

#### Scenario: An empty carry is written down as its derivation

- **WHEN** a change creates no obligation for any later change
- **THEN** that is recorded as the counts each source yielded, at least one being a named command's output

### Requirement: An unattended run does not end a turn while work is pending

A skill that drives a multi-step run meant to proceed without a human SHALL state, among its top-level rules and in one block, that a turn never ends unless something pending will wake the session again. The block SHALL give:

- the check: does this message contain a tool call;
- the test: will a pending event (a background dispatch whose completion wakes the session) re-invoke it. This differs from the no-confirmation-prompt rules, because this failure asks the user nothing;
- that announcing the next step does not continue the run.

Ending a turn is legitimate in exactly two cases, named the same in every skill: a background dispatch is in flight, or the run is complete. No third case, such as "blocked on a decision already shown to the user", SHALL be added; a real blocker is raised with a tool call. Where a skill's per-unit loop lives in a reference file, that file SHALL restate the rule where one unit ends and the next begins.

#### Scenario: The rule is stated as a check, in one block

- **WHEN** an unattended-run skill states the rule
- **THEN** it gives the tool-call check, the pending-event test, and "announcing is not continuing" together in one block
- **AND** it does not rely only on the agent noticing that its text reads like an ending

#### Scenario: The rule is distinguished from the no-pause rules

- **WHEN** the rule appears beside a "no ready-to-continue pauses" rule
- **THEN** it says the failure it covers asks the user nothing
- **AND** it uses the pending-event test, not "was a question asked"

#### Scenario: The handover between units restates the rule

- **WHEN** a skill's per-unit loop lives in a reference file
- **THEN** that file restates the rule where one unit ends and the next begins, and says why it is restated there

#### Scenario: The exhaustive set is the same two everywhere

- **WHEN** two skills each state the rule
- **THEN** both name the same two legitimate cases and neither adds a third

### Requirement: A task list is not reported complete on tick marks alone

A skill that reports a task list complete SHALL NOT rely only on tick marks or on an artifacts-ready flag. A ticked task that asserts a measurement (a value, a count, a mutation-test result) SHALL carry the measured value on its line, and the skill SHALL re-measure a small sample itself. spec-to-pr's Implement post-check SHALL also search the tree for each test a ticked task names. The skill SHALL state the convention that a task stays `[ ]` until done, with the reason it is still open written beneath it.

#### Scenario: A measurement-bearing task carries its measurement

- **WHEN** a task asserts a confirmed value, a count, or a mutation-test result
- **THEN** the ticked line records the measured value
- **AND** a sample of such tasks is re-measured rather than trusted

#### Scenario: A ticked test task whose test is missing

- **WHEN** a ticked task names a test that the search does not find
- **THEN** the run records a Handoff issue and writes the test before leaving Implement

### Requirement: A measurement names the command that produced it

At each step that creates a commit, after its pre-commit state check and before the commit, a skill SHALL require every measurement the change asserts (a count, a coverage figure, "verified", "zero X", any number given as fact, in the diff, commit message or PR body) to carry a `Measured-by: <command>` trailer naming a command runnable as written. The author finds the claims; no keyword scan does.

#### Scenario: A change asserting a measurement carries its command

- **WHEN** a commit's change asserts a count, a coverage figure, or any number given as fact
- **THEN** the commit message carries one trailer per claim, naming a command runnable as written

#### Scenario: A claim with no command is edited, not carried

- **WHEN** the author cannot name a command for a measurement the change asserts
- **THEN** the command is run now, or the claim is deleted
- **AND** the claim never ships with the command owed

#### Scenario: A change asserting nothing certifies nothing

- **WHEN** a change asserts no measurement
- **THEN** the commit carries no trailer, not even `Measured-by: none`

#### Scenario: The rule is stated at every commit step

- **WHEN** a skill has more than one commit-creating step
- **THEN** the rule is stated at each, not only at the first, and not among authoring-time guidance

#### Scenario: A standing gate is not a claim the change asserts

- **WHEN** a change runs the tests, linters and conformance scripts every commit runs
- **THEN** those results get no trailer

### Requirement: Deferred findings are separated by reason

A skill reporting findings it did not apply SHALL list them under three named subsections: blocked on something missing now, waiting for a trigger that has not happened yet, and skipped for neither reason. A skipped item SHALL be findable with a grep, so a policy breach does not require re-reading every item.

#### Scenario: A skipped item is distinguishable from a legitimate hold

- **WHEN** a fix round reports items it did not apply
- **THEN** each appears under one of the three named subsections
- **AND** under a no-deferrals policy, a non-empty "skipped" list fails the reporting step

### Requirement: The test-quality rules are read where tests are written

The plugin SHALL keep, in a shared reference read when tests are written, the rules that decide whether a test can fail at all. Its opening SHALL say which rules apply to any test and which apply only to a gate (a check whose job is to detect something). It SHALL also cover planting, meaning deliberately introducing the failure a gate should catch:

- a plant that missed is described by conditions the reader can check: diff the file and confirm the change is in the data, re-parse it and confirm it is well-formed, read the failure message for the planted value;
- planting only exercises the code that exists, so anything parsing an external format is listed from its primary source before planting against it;
- a plant that lands and is caught still proves nothing alone: read the catching assertion and confirm it states the wanted behaviour. The riskiest case is a plant that is the simpler form of the code;
- advice on when planting is worth its cost does not narrow the review-fix check, which stays unconditional.

For a new alarm, threshold or minimum-sample rule, the reference SHALL require stating the volume it will meet in ordinary operation, where that figure comes from, and the outcome at both ends of that range. It SHALL say that a plant against the live tree does not reach this case, and that a neighbouring rule (feeding the check bad state) does, provided the bad state is sized to real volume.

#### Scenario: A reader is routed before being asked to read gate doctrine

- **WHEN** the shared test-quality reference is opened
- **THEN** its opening says which sections apply to any test and which only to a gate

#### Scenario: The cost guidance does not narrow the review-fix gate

- **WHEN** the reference says planting is unnecessary for some assertions
- **THEN** it says this leaves the review-fix check unchanged

#### Scenario: A missed plant is described by checkable conditions

- **WHEN** the reference describes a plant that did not land on the value under test
- **THEN** it names conditions that tell a landed plant from a missed one
- **AND** a problem of a different shape gets its own remedy rather than being forced into that form

#### Scenario: A plant that lands and is caught is still examined

- **WHEN** a reader's plant landed and a test caught it
- **THEN** the reference says the catch proves only that the suite reacts to the edit
- **AND** it directs the catching assertion to be read and confirmed
- **AND** it names the simpler-form plant as the riskiest case

#### Scenario: A correct guard that cannot fire at its real volume is covered

- **WHEN** the reference is read by someone adding an alarm, threshold, or minimum-sample rule
- **THEN** it requires the ordinary operating volume, and its source, to be stated
- **AND** it requires both outcomes at that volume: the alarm can fire, and fires only when it should
- **AND** it says a plant against the live tree does not reach this, and states when the bad-state rule does

### Requirement: A fix brief makes the defect binding and the proposed fix rejectable

A brief that dispatches an agent to fix a defect SHALL state the defect and the proposed fix in separate fields. The defect is binding: the agent may not decide it is acceptable. The proposed fix may be rejected with reasons, and a reasoned rejection SHALL be a successful return with its own status, distinct from blocked. `done` SHALL require the brief's defect check (the command or read that shows the defect) re-run with output showing the defect gone, and the brief SHALL say that evidence the fix was applied is not that evidence. A dispatch over several findings SHALL return an outcome per finding as well as an overall status; a single finding returns a one-row list.

Where a brief format is shared across skills and cited by slot name, the fix form SHALL be a second form of the existing task slot, not a new slot.

#### Scenario: The terminal contract asks for defect-gone evidence

- **WHEN** a fix dispatch's terminal contract is stated
- **THEN** `done` requires the brief's defect check, re-run, with output showing the defect gone
- **AND** a `done` without that evidence is treated as not done

#### Scenario: A reasoned rejection is a successful return

- **WHEN** the agent finds the proposed fix wrong
- **THEN** it returns a rejection status, distinct from blocked, with its reason
- **AND** the orchestrator treats it as a success and decides the fix again, rather than resolving a blocker

#### Scenario: The slot list is not renumbered

- **WHEN** the fix form is added to a shared brief format cited by slot name
- **THEN** no slot is renamed, renumbered or added, and every citing site stays correct unedited

#### Scenario: A brief that cannot name a defect check

- **WHEN** the orchestrator cannot name a check that shows the defect
- **THEN** the defect is treated as not grounded, to be grounded before dispatch
- **AND** the brief is NOT treated as exempt from the terminal contract

#### Scenario: Every site restating the terminal contract states the same one

- **WHEN** the terminal contract is restated outside the brief that defines it
- **THEN** every site briefing a fix dispatch states the three-status form
- **AND** a site briefing a dispatch that never fixes a defect is left unchanged

#### Scenario: A permission to disagree does not satisfy the requirement

- **WHEN** a skill adds prose letting the agent disagree with the proposed fix
- **AND** `done` still only requires evidence that the fix was applied
- **THEN** the requirement is NOT satisfied

#### Scenario: A dispatch over a set of findings reports each one

- **WHEN** a fix dispatch covers more than one finding
- **THEN** its return carries an overall status and one outcome row per finding
- **AND** a finding whose fix was rejected can be identified from that list

### Requirement: The fix loop handles a rejected fix

A fix loop SHALL give a rejected proposed fix its own outcome beside applied and deferred. A rejection leaves the finding open, is not counted as untriaged, and does not use up a round. The loop's exit check SHALL count untriaged findings and open findings separately and exit clean only when both are zero. The final report SHALL list rejected-but-open findings in their own section, apart from deferred findings and Suggestions. Where a rejection shows that a fact the defect rested on is wrong and the defect does not survive the correction, the finding SHALL be closed as disproved, with the corrected fact as evidence.

#### Scenario: A rejection is triaged rather than counted as residue

- **WHEN** a dispatched agent rejects the proposed fix
- **THEN** triage records it as its own outcome beside applied and deferred
- **AND** the exit check does not count it as untriaged, and the round is not warned or used up on its account

#### Scenario: A rejection reopens the remedy, not the finding

- **WHEN** a finding's proposed fix is rejected
- **THEN** the finding stays open and is retried with a new fix, not recorded as resolved

#### Scenario: The exit gate does not release the loop on an open finding

- **WHEN** a round ends with a rejected finding still open and nothing untriaged
- **THEN** the loop is not reported clean
- **AND** with rounds left it goes round again; at the cap the round is warned and the finding recorded as left over

#### Scenario: A rejected finding has a home in the terminal report

- **WHEN** a run ends with a rejected finding still open
- **THEN** the final report lists it in its own section, not as a deliberate deferral or a Suggestion

#### Scenario: A rejection citing a disproved defect closes the finding

- **WHEN** the rejection's reason is that the defect does not survive correcting a fact it rested on
- **THEN** the finding is closed, not retried, with the corrected fact as evidence
- **AND** it is not recorded as fixed

### Requirement: A brief's factual claims are checkable and carry their source

A brief that states a defect SHALL list each fact the defect rests on (a field list, a signature, a line number, a count) as its own row, naming the source that settles it (a path with a line, or a command) and tagging whether the writer checked it or is relaying another agent's report. Review reports' claim tables do not need the tag. The agent SHALL first re-check each row, quoting the source or saying not found, and the brief SHALL state that rule in its own text. A wrong row does not automatically void the defect. Corrections SHALL be returned in a field that is always present, with an explicit empty marker when there are none.

#### Scenario: The defect's factual sub-claims are enumerated with sources

- **WHEN** a fix brief states a defect resting on a field list, a signature, a line number, or a count
- **THEN** each such fact is its own row, outside the defect prose
- **AND** each row names its path-with-line or command, and whether it was checked or relayed unchecked

#### Scenario: The agent re-resolves the rows before implementing

- **WHEN** an agent receives a fix brief with fact rows
- **THEN** it first re-checks each row against its source, quoting the evidence or saying not found

#### Scenario: A wrong sub-claim that the defect survives is corrected, not escalated

- **WHEN** a fact row is wrong but the defect is still real once it is corrected
- **THEN** the agent corrects the row, proceeds, and reports the correction

#### Scenario: A wrong sub-claim that the defect depends on stops the work

- **WHEN** a fact row is wrong and the defect does not survive its correction
- **THEN** the agent returns the fix rejected, with the corrected row, and does not implement it

#### Scenario: The corrections field is never omitted

- **WHEN** an agent finds no wrong fact rows
- **THEN** the corrections field is present with an explicit empty marker

### Requirement: A fix the orchestrator chose itself is checked against rejected alternatives

Where the orchestrator applies a fix itself rather than through a dispatched agent, its post-fix re-check SHALL compare the fix with the rejected alternatives in the change's `design.md`, not the proposal or tasks. A fix that brings back a rejected alternative is a Critical finding on the fix: it SHALL be withdrawn or re-specified, or, if the rejection is now judged wrong, `design.md` SHALL be amended explicitly; "the brief said so" is not an amendment. Where delegated and orchestrator-applied fixes can occur in the same round, each orchestrator-applied fix SHALL be marked on its existing triage record; in a loop with no delegate, the skill states once that every fix is the orchestrator's. Raising a round cap SHALL NOT be used to meet this, and the skill SHALL say this in-round check is weaker than an independent reviewer.

#### Scenario: An orchestrator-applied fix is checked against the rejected alternatives

- **WHEN** the orchestrator applies a fix itself and it brings back an alternative `design.md` rejected
- **THEN** it is raised as a Critical finding against the fix
- **AND** the fix is withdrawn or re-specified, or `design.md` is amended explicitly

#### Scenario: The remedy is marked for the next reader

- **WHEN** a round contains a fix the orchestrator chose
- **THEN** that finding's record is marked orchestrator-specified
- **AND** a later review round is told which changes carry the mark and runs the same check on them, or, if none runs, the mark appears in the final report

#### Scenario: The control does not change a round cap

- **WHEN** this rule is stated in a skill
- **THEN** no round cap or default round count is raised to satisfy it

#### Scenario: The check reads the document as it stood before the remedy

- **WHEN** the orchestrator's fix itself edits the rejected alternatives in `design.md`
- **THEN** the check reads `design.md` as captured at the start of the fix round
- **AND** capturing it does not require it to be committed

#### Scenario: A fix loop with no rejected-alternatives document is out of scope

- **WHEN** a skill applies its own fixes but works on no change directory
- **THEN** neither the check nor the marking applies, and their absence is not reported as a breach

### Requirement: A dispatched agent waits for its checks to finish

A brief SHALL tell the dispatched agent to run every check (build, lint, test or other) in the foreground, wait for it however long it takes, and not end its turn while a command it started is running, and SHALL say why: the agent's turn ending is its return, so a background result can never reach it. This SHALL NOT change the orchestrator's right to end a turn with a background dispatch in flight, nor add a third reason to end a turn. A check too long for one foreground call SHALL NOT be delegated; an agent that meets one returns blocked naming it. That time limit SHALL be checked against the running harness at dispatch time, not written into the skill as a constant.

#### Scenario: The brief requires foreground gates

- **WHEN** a skill briefs an agent that will run a check
- **THEN** the brief requires it to run in the foreground and be waited for, whatever its expected duration
- **AND** it forbids ending the turn while a started command is still running

#### Scenario: The orchestrator's own backgrounding is unchanged

- **WHEN** the rule is stated beside the turn-ending rule
- **THEN** an orchestrator may still end a turn with a background dispatch in flight, and no third case is added

#### Scenario: A gate too long to run in one call is not delegated

- **WHEN** a check's expected duration approaches what one foreground call allows
- **THEN** the skill does not delegate it, and an agent that meets one returns blocked naming it rather than backgrounding it

### Requirement: A return without a status is treated as blocked

For a dispatch whose brief declares a set of statuses, the orchestrator SHALL check whether the return carries one of them before acting on its prose. A return with none SHALL be treated as blocked however finished it reads, and a `done` without the evidence its contract requires is treated as not done. No new status SHALL be added for this. Each such event SHALL be recorded as a Handoff issue, not absorbed by quietly finishing the work. A dispatch whose brief declares no statuses (a read-only gatherer, a reviewer returning findings) is out of scope.

#### Scenario: An evidence-free return is blocked

- **WHEN** a dispatched agent returns without a status token
- **THEN** the orchestrator treats the return as blocked, whether or not its prose reads as finished
- **AND** the check is a scan for the token, not a judgement of how the return reads

#### Scenario: A dispatch with no declared status contract is out of scope

- **WHEN** an agent's brief declares no statuses
- **THEN** its return is not treated as blocked for lacking a status token

#### Scenario: No status is added for the case

- **WHEN** the rule is stated
- **THEN** the set of statuses is unchanged

#### Scenario: The firing is recorded

- **WHEN** a return is treated as blocked or not done for missing its status or evidence
- **THEN** the event is recorded as a Handoff issue, even when the orchestrator finishes the work itself

### Requirement: Only one party writes to a shared checkout at a time

Where dispatched agents work in the orchestrator's own checkout, the skill SHALL state the rule to both sides:

- **Agent side**, as standard text in every brief: name the forbidden repository-changing git commands, including commit, push, reset, checkout, switch, branch, stash and worktree; forbid killing or restarting a process the agent did not start, and deleting or regenerating a build, cache or dependency directory it did not create.
- **Orchestrator side**, as part of the skill's existing shared-checkout guidance, not left to the brief: while a dispatch is live or a command it started may be running, run no repository-changing git command and no check in that checkout, and delete or regenerate nothing the dispatch builds into.

The skill SHALL also say that a failure seen in a checkout the orchestrator disturbed during its own dispatch is not evidence of a regression, and must be reproduced from a quiet tree first.

#### Scenario: The agent-facing enumeration covers commit, push and reset

- **WHEN** a brief states which commands the agent may not run
- **THEN** it names commit, push and reset as well as checkout, switch, branch, stash and worktree
- **AND** it forbids killing a process, or deleting a build, cache or dependency directory, the agent did not start or create
- **AND** this text is standard in every brief, because every dispatch shares the checkout

#### Scenario: The orchestrator-facing half lives where the orchestrator reads

- **WHEN** the rule is written down
- **THEN** the orchestrator's half is in the skill's own shared-checkout guidance, not only in the brief

#### Scenario: Manufactured failures are not treated as regressions

- **WHEN** a failure appears in a checkout the orchestrator touched while its own dispatch was live
- **THEN** it is reproduced from a quiet tree before being investigated as a regression

#### Scenario: The response to a missing return is gated on a quiet tree

- **WHEN** the orchestrator must act on a return that missed its status or evidence
- **THEN** it first confirms by read-only means that nothing the dispatch started is still running
- **AND** a check too long for one call is run by the orchestrator itself, and only unfinished work is re-dispatched
- **AND** it never takes over the checkout before that confirmation

### Requirement: A dispatched agent stops rather than inventing evidence

Every brief SHALL carry, as standard text beside its evidence requirement, the rule that every value the agent returns is one it produced, not estimated, inferred, or copied from an earlier run or another file. An agent that cannot produce a required value SHALL return blocked, naming what it could not produce and why, and the brief SHALL say this is a successful return. This does not clash with the rule for wrong facts supplied in a brief: those are corrected or lead to rejecting the fix, while evidence the agent cannot produce leads to a blocked return, and neither adds a status.

#### Scenario: An unobtainable value produces a blocked return

- **WHEN** a dispatched agent cannot produce a value the contract requires
- **THEN** it returns blocked, naming the value and why
- **AND** the brief says this is a successful return

#### Scenario: An invented value is a reportable defect

- **WHEN** a returned value was estimated, inferred, or copied rather than produced
- **THEN** it is recorded as a defect (a Handoff issue), not tidied up as formatting

#### Scenario: Inbound and outbound claim rules do not collide

- **WHEN** a brief format states both this rule and the wrong-fact rule
- **THEN** a wrong fact in the brief leads to a correction or a rejected fix
- **AND** evidence the agent cannot produce leads to a blocked return
- **AND** neither adds a status

### Requirement: A second Revise round asks a different question

A Revise round 2 or later, run over the previous round's fix, SHALL ask, verbatim:

> Does this fix introduce the defect it fixed, somewhere else? Enumerate every other instance of the resource or shape the fix concerns.

The answer SHALL list each other instance and whether the defect is present there; "no other instance exists" is a stated result, not a skipped step. The question SHALL appear both in the Revise reference where the round's dispatch is built and in the skill's own Revise summary. A round with no previous fix to ask about SHALL skip the question: round 1, a later round entered with no previous fix commit (which reviews the whole pull request), and a later round re-entered only for rejected fixes. A later round that skips it records `sibling_instance` as `null`, not `0`.

#### Scenario: A later round is dispatched with the distinct framing

- **WHEN** the Revise loop runs round 2 or later over the previous fix commit's diff
- **THEN** the dispatch carries the question verbatim and asks for every other instance of what the fix concerns

#### Scenario: The fix's own safety addition recreates the defect elsewhere

- **WHEN** round 1's fix for a mismatch between a count and its matches adds a cap that recreates the same mismatch at a second call site
- **THEN** round 2 lists that second site as another instance
- **AND** reports the recreated mismatch as a finding rather than letting it ship

#### Scenario: No other instance exists

- **WHEN** the round-2 reviewer finds nothing else of the same kind
- **THEN** it says so, and the empty list is recorded as a result

#### Scenario: A round with no fix to ask about skips the question

- **WHEN** the loop runs round 1, a later round with no previous fix commit, or a later round re-entered only for rejected fixes
- **THEN** the question is not part of that dispatch
- **AND** a later round's `sibling_instance` is `null`, so the skip is not read as a measured zero

### Requirement: A later Revise round's search for other instances is possible and checked

A dispatch carrying the round-2 question SHALL name the specific thing the previous fix concerns, concretely enough to bound the search (a function's call sites, the readers of a config key), and SHALL say the agent may read and search the repository to answer it, under the usual read-only rules. The return SHALL cite the search it ran, and the orchestrator SHALL re-run that search and compare:

- **hits match the list**: accept it, and count confirmed other instances among the round's Critical and Important findings in `sibling_instance`;
- **hits the list misses**: the orchestrator checks them itself before triage;
- **no citation**: the answer is missing, not empty. Re-dispatch once with the resource named; if still uncited, record `sibling_instance` as `null` and log a Handoff issue.

A re-dispatch is an ordinary dispatch: its findings are counted and triaged, and it counts once toward the run's dispatch totals. The comparison itself changes no finding count.

#### Scenario: The prompt names a bounded resource and allows a search

- **WHEN** round 2 or later is dispatched over a previous fix
- **THEN** the prompt names the specific resource or shape that fix concerns
- **AND** says the agent may read and search the repository, while still not re-reading the diff it was given

#### Scenario: An uncited enumeration is not an empty one

- **WHEN** a return says no other instance exists but cites no search
- **THEN** it is treated as missing and the agent is re-dispatched once with the resource named
- **AND** if still uncited, `sibling_instance` is `null` and a Handoff issue is logged

#### Scenario: A cited search that disagrees with its own enumeration

- **WHEN** re-running the cited search finds instances the list does not include
- **THEN** those instances are checked before triage, not treated as cleared

#### Scenario: The re-dispatch is an ordinary dispatch

- **WHEN** an agent is re-dispatched for an uncited answer
- **THEN** its findings enter the round's counts and triage like any other
- **AND** it counts once in the run's dispatch totals

### Requirement: The Revise round cap is a ceiling, not the loop's exit condition

Wherever the Revise reference or the skill's Revise summary states the `--pr-rounds` cap, it SHALL say the cap is a ceiling, not a target. It SHALL NOT claim the untriaged count is zero by construction, and SHALL NOT state what ordinarily ends the loop. This SHALL NOT change any cap value, the exit check, or how often a second round runs.

#### Scenario: The cap is named in the reference and in the skill stub

- **WHEN** a reader meets the `--pr-rounds` default in the Revise reference or the skill's Revise summary
- **THEN** the same sentence says the default is a ceiling, not a target
- **AND** it does not claim the untriaged count is zero by construction

#### Scenario: The clarification changes no numbers

- **WHEN** the clarification is applied
- **THEN** `--pr-rounds` stays `2`, `--review-rounds` stays `1`, and `--test-rounds` stays `3`

#### Scenario: A run that stops after one round is not a capped run

- **WHEN** a run's record shows Revise used one round against a cap of two
- **THEN** it is read as having exited with every finding triaged, not as cut short by the cap

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

- **WHEN** any step in any skill creates or edits a live spec, including an in-place edit with no delta and no archive
- **THEN** that step itself validates the live specs before its commit
- **AND** a result naming a broken spec halts the step instead of committing

#### Scenario: A chain validates before it merges

- **WHEN** a change in a sequence leaves the live specs failing validation
- **THEN** the sequence halts before that change's pull request merges, while its branch can still be fixed
- **AND** the failure is not left for the next change's archive to hit

#### Scenario: A check that could not run is not reported as a broken specification

- **WHEN** validation exits non-zero without naming a failing spec
- **THEN** it is reported as a tooling fault, not blamed on the change's specs, and does not halt a sequence

#### Scenario: A run that validated nothing is not a pass

- **WHEN** validation reports it found nothing to validate
- **THEN** that is not recorded as success
- **AND** a repository that does not use the spec tooling says so once rather than logging empty passes
