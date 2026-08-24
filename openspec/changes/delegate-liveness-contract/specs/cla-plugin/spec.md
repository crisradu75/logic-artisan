## ADDED Requirements

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
