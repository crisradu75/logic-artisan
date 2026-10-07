# change-review Specification

## Purpose

How a change is reviewed before implementation: the grounding contract for claims, reconciling reviewer severities, comparing MODIFIED blocks against the live requirement, the findings an oversized or unproven artifact earns, and multi-spec's batch review gate and its recorded verdicts. Where a requirement has reasoning, measurements or
compressed detail behind it, they are in `rationale.md`, under the same heading.

## Requirements

### Requirement: Grounding contract enumerates the claim shapes that do not look like claims

A CLA review workflow whose grounding contract binds every claim to evidence SHALL additionally
enumerate, beside that rule, the sentence shapes whose truth depends on something outside the artifact
but whose grammar is not assertive. The enumeration SHALL be stated as part of the grounding contract
rather than as further independent numbered checks appended to the workflow's check list.

#### Scenario: The shapes are named inside the grounding contract

- **WHEN** the review workflow's grounding contract is stated
- **THEN** the four claim shapes are enumerated as part of that contract
- **AND** they are not added as four further independent numbered checks

### Requirement: Each claim shape is stated as an executable check

**Four shapes SHALL be named**, each stated as a trigger, a resolution naming what to read and what to
resolve it against, a failure mode, and a severity floor. A shape stated only as an instruction to
confirm that a claim is grounded SHALL NOT satisfy this requirement.

#### Scenario: Each shape is executable rather than an instruction to verify

- **WHEN** a claim shape is stated
- **THEN** it names its trigger, the resolution steps naming what to read and what to resolve it against, its failure mode, and its severity floor
- **AND** a shape whose text only instructs the reviewer to confirm the claim is grounded is treated as not meeting the requirement

### Requirement: The claim-shape enumeration records its reason

The reason SHALL be recorded with the enumeration: the failures this addresses are **recognition**
failures, not procedure failures.

#### Scenario: The enumeration carries its reason

- **WHEN** the claim shapes are stated in the contract
- **THEN** the text says why they are enumerated — that these are recognition failures, not procedure failures
- **AND** it is stated with the list rather than left to a reader to infer from the shapes themselves

### Requirement: Producible state is resolved against the data the system will run on

Shape 1, **producible state**, is triggered by an artifact specifying fixed example, demo, fixture,
or sample states a surface must show. Its resolution SHALL read the production function or query for
each state, resolve its gating predicate against the real data the system will run on, and record the
producing path with its corpus figure. Searched with none found SHALL resolve as **not producible**,
floor **Critical**; NOT searched SHALL resolve as unresolved, with no severity floor.

#### Scenario: An unproducible demo state resolves negative rather than unresolved

- **WHEN** a reviewer has searched for the production path that would produce a specified demo state and found none
- **THEN** the state resolves as not producible rather than as unresolved
- **AND** the requirement specifying it is graded Critical
- **AND** where the reviewer has not searched, the row resolves as unresolved instead and carries no severity floor

### Requirement: A named precedent is checked for extra strictness

Shape 2, **precedent strictness**, is triggered by an artifact naming an existing shipped
implementation as the precedent it mirrors, follows, or is modelled on. Its resolution SHALL read the
precedent's actual mechanism and, per provision the new requirement imposes, record whether the
precedent satisfies it, does not, or does not have it, and what extra strictness buys and who pays.
Floor: **Important**, **Critical** where it blocks implementation.

#### Scenario: A named precedent is read for what it actually enforces

- **WHEN** an artifact names a shipped implementation as the precedent it mirrors
- **THEN** the reviewer reads that precedent's mechanism and records, per provision the artifact imposes, whether the precedent satisfies it, does not, or does not have it
- **AND** for each provision the precedent does not satisfy, states what the extra strictness buys and who pays
- **AND** the shape states why no other check finds this: every other check asks whether the artifact is strong enough, and this one asks whether it is stronger than it needs to be

### Requirement: A guarantee is classified as a code or a deployment property

Shape 3, **guarantee class**, is triggered by an artifact stating that a mechanism prevents,
controls, serialises, or makes impossible a hazard. Its resolution SHALL classify the guarantee as a
code property, quoting the enforcing line, or a deployment property, which the artifact must say and
name the trigger that changes. Leaving it unclassified SHALL itself be the failure. Floor: no named
trigger is **Important**; a deployment property described as a code property is **Critical**.

#### Scenario: A guarantee is classified before it is accepted

- **WHEN** an artifact states that a mechanism prevents a hazard
- **THEN** the reviewer classifies the guarantee as a code property or a deployment property
- **AND** a code property is resolved by quoting the enforcing line
- **AND** a deployment property is accepted only where the artifact says so and names the trigger that changes it

### Requirement: A compensating-coverage claim is read, not accepted

Shape 4, **compensating coverage**: where a change gives up automated coverage for a named
alternative, the resolution SHALL be to read the named replacement and confirm what kind of assertion
it actually runs, then state its strength relative to what was given up. Floor: **Important** for an
unverified compensating claim, **Critical** where the replacement is measurably weaker than what it
replaced.

#### Scenario: A compensating-coverage claim is read rather than accepted

- **WHEN** a change gives up automated coverage in exchange for a named alternative
- **THEN** the reviewer reads the named replacement and records what kind of assertion it actually runs
- **AND** states the replacement's strength relative to what was given up

### Requirement: An exclusion's reach is enumerated

Shape 4, **exclusion reach**: where an exclusion entry is added to any keyed allowlist or denylist,
the resolution SHALL be to enumerate the components or modules reachable only through the excluded
surface and, for each, name where it is otherwise covered or state that it is not.

#### Scenario: An exclusion's reach is enumerated

- **WHEN** an exclusion entry is added to a keyed allowlist or denylist
- **THEN** the components or modules reachable only through the excluded surface are enumerated
- **AND** each is paired with where it is otherwise covered, or stated to be uncovered

### Requirement: The claim-shape list is open by signature

**The list SHALL be stated as open, by signature rather than by disclaimer.** The common signature
SHALL be given (a sentence is a claim when its truth depends on something outside the artifact though
its grammar is not assertive) with the grammars that hide one: an explanation, a comparison to
something shipped, a specification of output shape, and a trade. A sentence matching that signature
SHALL be in scope whether or not it appears among the named shapes.

#### Scenario: An unnamed shape matching the signature is in scope

- **WHEN** an artifact carries a sentence whose truth depends on code, corpus, precedent, deployment, or a test file, phrased as an explanation, a comparison, an output specification, or a trade
- **THEN** the contract covers it whether or not it matches one of the named shapes
- **AND** the contract states this as a signature rather than as a closing disclaimer

### Requirement: The claim shapes are portable

The shapes SHALL be stated so that no repository-specific mechanism, product name, or infrastructure
identifier from the reporting instances travels into the portable text.

#### Scenario: A shape carries no trace of the instance that produced it

- **WHEN** a shape is written from a specific reported failure
- **THEN** its text names no repository, product, module, route, or infrastructure identifier from that instance
- **AND** the shape is stated so a repository with a different architecture can still apply it
- **AND** a shape that can only fire in the reporting instance's kind of product is rewritten or dropped

### Requirement: Dispatched reviewers carry the claim shapes in full

A review that dispatches agents to produce its findings SHALL carry the shape list in those agents'
own briefs, in full and never as a pointer to the contract. A shape whose resolution requires
re-reading the change artifacts SHALL be stated as not delegable to that dispatch.

#### Scenario: The shapes reach the reviewers who produce the findings

- **WHEN** a review dispatches agents to produce its findings rather than adjudicating inline
- **THEN** the shape list is carried in those agents' own briefs, not only in the orchestrator's sweep
- **AND** the shape text is carried into each prompt in full, never as a pointer to the contract, because a dispatched agent does not load the skill and cannot resolve one
- **AND** a shape whose resolution requires re-reading the change artifacts is stated as not delegable to that dispatch

### Requirement: One numbered check reaches the claim shapes and is not delegated

**Exactly one numbered check SHALL be added to the workflow's check list**, pointing at the shape list
rather than restating it. No existing check SHALL be renumbered or reworded, and every enumeration of
the orchestrator's checks SHALL name the new one. **That check SHALL be stated as outside the mechanical
portion that defaults to a fact-gathering sub-agent**, in the paragraph where the delegation decision
is made.

#### Scenario: The sweep reaches the shapes and is not delegated

- **WHEN** the workflow's verification sweep runs
- **THEN** one numbered check points at the shape list, and every enumeration of the orchestrator's checks names it
- **AND** that check is stated as outside the mechanical portion that defaults to a fact-gathering sub-agent
- **AND** the exclusion appears in the paragraph where the delegation decision is made

### Requirement: Reviewer report severities are reconciled by the evidence behind them

A CLA review workflow that dispatches more than one reviewer and merges their reports SHALL state how
a finding reported by two of them at different severities is graded. The merged severity SHALL be taken
from the report whose evidence is **implementation-level** (a source line, a schema, a migration, a
query result) over one whose evidence is the specification delta or artifact text alone. The rule
SHALL key on the evidence attached to the finding, not on which reviewer reported it.

#### Scenario: Two reports grade one finding differently

- **WHEN** two dispatched reviewers report the same finding at different severities
- **THEN** the merged severity is taken from the report whose evidence is implementation-level
- **AND** the report whose evidence is the specification delta or artifact text alone does not set the severity

### Requirement: The higher severity stands only as a fallback

Where neither report's evidence is implementation-level, or both are, the **higher severity SHALL
stand**. This fallback SHALL NOT be stated as the primary rule.

#### Scenario: Neither report's evidence discriminates

- **WHEN** neither report's evidence for the severity is implementation-level, or both are
- **THEN** the higher severity stands
- **AND** this is stated as the fallback rather than as the rule

### Requirement: A severity tie-break is recorded on its finding

The tie-break SHALL be recorded on the finding it resolved, so that a reader can see one occurred, and
SHALL NOT add a line to the report, which is budgeted at one line per finding.

#### Scenario: The tie-break is visible without costing a report line

- **WHEN** a severity tie-break is applied
- **THEN** it is recorded on the finding it resolved
- **AND** no additional line is added to the report

### Requirement: The tie-break rule states its evidence without claiming measurement

**The rule's evidence SHALL be stated with it and SHALL NOT be presented as measured**: one
overlapping finding out of eighteen, from one change, observed under a different dispatch shape. The
text SHALL state that low overlap is the reviewer split working as intended and that the rule is
therefore expected to fire rarely.

#### Scenario: The rule carries its own evidence honestly

- **WHEN** the tie-break rule is stated
- **THEN** it names its single supporting instance and the total it came from
- **AND** it states that the instance came from a different dispatch shape
- **AND** it is not described as measured

### Requirement: A MODIFIED block is compared against the live requirement it replaces

A skill that reviews, archives, or sequences a change SHALL compare each `## MODIFIED Requirements`
block's scenario set against the live requirement that block will replace, and SHALL NOT treat the
block's internal completeness as evidence of retention. Nothing in this comparison blocks, edits, or
refuses a change.

#### Scenario: A delta that looks complete on its own face

- **WHEN** a modified block carries a full requirement text and a list of scenarios, while the live requirement it replaces carries more scenarios than the block does
- **THEN** the comparison reports the difference
- **AND** an instruction satisfied by reading the delta alone is treated as not covering this

#### Scenario: A change with no modified block

- **WHEN** a change's delta contains no modified-requirement block
- **THEN** the check is reported as not applicable, naming what was scanned
- **AND** it is not recorded as a passing comparison

### Requirement: The comparison attaches to the block, not the workflow

**The obligation attaches to the block, not to the workflow that produced it.** It SHALL apply
wherever a change carrying such a block is reviewed before implementation, prepared for archive, or
sequenced within a batch.

#### Scenario: A change outside a batch is still compared

- **WHEN** a change carrying a modified-requirement block is taken to a pull request on its own, passing through no cross-change sequencing step
- **THEN** the comparison runs anyway, at that change's own pre-implementation review and again before its archive
- **AND** a comparison available only to batch-sequenced changes does not satisfy this

### Requirement: The comparison baseline is the live specification at check time

**The comparison baseline SHALL be the live specification as it stands at the moment of the check**,
not as the delta was authored.

#### Scenario: The baseline is current, not as-authored

- **WHEN** the live requirement changed after the delta was written
- **THEN** the comparison reads the live specification as it stands at the moment of the check
- **AND** comparing against the text the delta was authored against does not satisfy this

### Requirement: A step that already locates the live requirement carries the comparison

**Where a step already locates the live requirement for another purpose, the comparison SHALL be
carried by that step** rather than added beside it. Confirming a modified block's heading exists is
not a comparison of its scenarios.

#### Scenario: Heading existence is not retention

- **WHEN** a step confirms that a modified block's requirement heading exists verbatim in the live specification
- **THEN** that step also compares the scenario headings under it
- **AND** a confirmed heading with an unexamined scenario set is recorded as unchecked, not as a pass

### Requirement: Renames are resolved before a comparison reports a loss

A retention comparison SHALL resolve the delta's requirement-rename mapping before matching a modified
block to a live requirement, and SHALL treat every remaining difference as a flag for adjudication
rather than as a confirmed loss. **Rename resolution SHALL NOT be claimed to eliminate false
positives**: a scenario renamed in place remains flagged.

#### Scenario: A requirement renamed by the same delta

- **WHEN** a modified block names a requirement that does not appear in the live specification, because the same delta's rename section renames it
- **THEN** the rename is resolved first and the block is matched to the live requirement under its old name
- **AND** the requirement is not reported as absent

#### Scenario: A scenario renamed in place is still flagged

- **WHEN** a live scenario's heading was rewritten in the delta to widen its scope, with its behaviour retained
- **THEN** it is flagged as missing and adjudicated as renamed
- **AND** the procedure does not claim to have distinguished it mechanically

### Requirement: A flag is adjudicated, never acted on alone

**Nothing SHALL refuse, halt, or auto-correct on a flag alone.** Each flagged scenario SHALL be
adjudicated to exactly one of: renamed, intentionally removed, or dropped. Only *dropped* is a finding.
An intentional removal SHALL cite the change's own artifacts; asserted without a citation it carries a
lower severity than a drop but is still reported.

#### Scenario: A flag does not block the change

- **WHEN** a comparison flags one or more scenarios
- **THEN** the change is not refused, halted, or edited by the comparison itself
- **AND** the flag is carried to whoever adjudicates it

### Requirement: An unadjudicated flag is treated as dropped

**An unadjudicated flag SHALL be treated as dropped, not as waived.**

#### Scenario: An unadjudicated flag is a finding

- **WHEN** a flagged scenario reaches the end of the step with no verdict recorded
- **THEN** it is treated as dropped and reported at the severity a dropped scenario carries
- **AND** it is not recorded as resolved because nothing contradicted it

### Requirement: A retention report states both directions and its denominator

A retention comparison SHALL report added scenario counts alongside missing ones, for every compared
requirement, including one where nothing is missing.

#### Scenario: A widening is distinguishable from a truncation

- **WHEN** a modified block carries more scenarios than the live requirement, while one live scenario heading is absent from it
- **THEN** the report states the live count, the delta count, the added count and the missing count together
- **AND** a reader distinguishes the widening from a truncation without opening either document

#### Scenario: A clean requirement is reported, not omitted

- **WHEN** a compared requirement's scenario sets match exactly
- **THEN** the report states its counts with both differences at zero
- **AND** omitting it is not treated as reporting it

### Requirement: A clean comparison still states what it examined

**A comparison that found nothing SHALL still report what it examined.** The report SHALL name how
many modified requirements were compared, across how many capabilities, how many were flagged, and how
many flags were adjudicated to each verdict.

#### Scenario: The run states its denominator

- **WHEN** a step finishes comparing a change's modified blocks
- **THEN** it reports how many requirements were compared across how many capabilities, how many were flagged, and how each flag was adjudicated
- **AND** a bare statement that nothing was found does not satisfy this

### Requirement: A failed enumeration is a failed check

**A failed enumeration SHALL be reported as a failed check, not as an empty result.**

#### Scenario: An enumeration that errored is not zero differences

- **WHEN** a command enumerating headings from either document exits non-zero
- **THEN** the check is reported as failed for that requirement
- **AND** the absent headings are not read as an empty set, and no requirement covered by that command is reported as clean

### Requirement: Review reads an absent design.md as absent

A change review SHALL stop as incomplete only when proposal.md is missing. When design.md is absent, the review SHALL read it as "(absent)" and pass "(no design.md)" to any dispatched agent.

#### Scenario: A change without design.md is reviewed

- **WHEN** review-change reviews a change that has no design.md
- **THEN** the review runs to a verdict instead of stopping
- **AND** every agent prompt carries "(no design.md)" in place of the design content

### Requirement: An oversized or restating artifact is an Important finding

A change review SHALL report an Important finding for a proposal over one page, an ADDED requirement over 500 characters or stating several behaviours, or an artifact that restates the proposal or the specs. A MODIFIED requirement SHALL be exempt from the length check, since OpenSpec forbids trimming it outside a change made to split it.

#### Scenario: An ADDED requirement is too long

- **WHEN** a delta adds a requirement of more than 500 characters
- **THEN** the review reports an Important finding naming it

#### Scenario: A long MODIFIED requirement

- **WHEN** a delta carries a MODIFIED requirement of more than 500 characters
- **THEN** the review reports no size finding for it

### Requirement: Cutting is a FIX FIRST remedy and is preferred

The review verdict rubric SHALL list cutting a restated or redundant section among the FIX FIRST remedies. When a finding can be fixed either by adding text or by cutting it, the review SHALL prefer the cut.

#### Scenario: A finding that a cut resolves

- **WHEN** a finding can be resolved by removing a section that restates another artifact
- **THEN** the recommended fix is the cut

### Requirement: Design headings do not buy the large-change review

The review size gate SHALL NOT count design decisions, however headed, and SHALL select the 3-agent review from files, subtasks, capabilities and claims alone. Its complexity-concentration override SHALL fire only when 15 or more subtasks are concentrated in one or two files.

#### Scenario: Many decision headings in a narrow change

- **WHEN** a change touches two files, has 8 subtasks and 6 `### D` headings in design.md
- **THEN** the size gate selects the small-change path

### Requirement: A scenario with no proof is an Important finding

A change review SHALL report as an Important finding a scenario the change adds or rewrites that has neither a test task nor a `manual: <heading>: <reason>` line.

#### Scenario: A scenario with no proof

- **WHEN** a delta adds a scenario and tasks.md has neither a test task for it nor a `manual: <heading>: <reason>` line
- **THEN** the review reports an Important finding naming the scenario

### Requirement: A repeated scenario heading is an Important finding

A change review SHALL report as an Important finding a scenario heading the change adds that repeats another scenario heading in the same spec.

#### Scenario: A repeated scenario heading

- **WHEN** a delta adds a scenario whose heading already names another scenario in the same spec
- **THEN** the review reports an Important finding naming the heading

### Requirement: A test task naming no marker is a Suggestion

A change review SHALL report as a Suggestion, which SHALL NOT block the verdict, a test task that does not name the `scenario: <spec> / <heading>` comment its test will carry.

#### Scenario: A test task that names no marker

- **WHEN** a test task proves a scenario but does not name the `scenario: <spec> / <heading>` comment its test will carry
- **THEN** the review reports a Suggestion, which does not block the verdict

### Requirement: A change multi-spec already reviewed skips the checklist pass

spec-to-pr's Review SHALL skip the checklist pass only when the change directory is clean, its files still match the digest in its `review.json`, and that record says READY, or FIX FIRST with every Critical and Important finding applied and none deferred. It SHALL still run the inherited-obligation check, the MODIFIED-block retention comparison and the doc-sweep, and SHALL log Review as `skip` with the verdict it trusted.

#### Scenario: A change multi-spec passed

- **WHEN** spec-to-pr runs on a clean change whose files match its `review.json` digest
- **AND** the record says `FIX FIRST`, `all_applied: true` and no deferred finding
- **THEN** Review skips the checklist pass and logs `skip` with reason `reviewed by multi-spec: FIX FIRST`

#### Scenario: A change multi-spec did not pass

- **WHEN** the record says `RETHINK`, or `all_applied: false`, or lists a deferred finding
- **THEN** Review runs the full checklist and reports each deferred finding as a known issue

#### Scenario: A change with no usable review record

- **WHEN** the change has no `review.json`, or it does not parse as JSON
- **THEN** Review runs the full checklist

#### Scenario: A change edited after multi-spec's review

- **WHEN** a later commit, or an uncommitted edit, touched the change directory
- **THEN** Review runs the full checklist

#### Scenario: A passed batch merged with a merge commit

- **WHEN** a READY change's proposals PR was merged with a merge commit
- **THEN** its files still match the record's digest, and Review skips the checklist pass

#### Scenario: An edit squashed in after multi-spec's review

- **WHEN** a commit pushed to the proposals PR after its review edited the change, and the PR was squash-merged
- **THEN** the change's files no longer match the record's digest, and Review runs the full checklist

### Requirement: multi-spec records each change's review verdict

multi-spec's review gate SHALL write `review.json` into every change directory it reviews, whatever the verdict, in the commit that applies its fixes. The record SHALL state the verdict, whether every Critical and Important finding was applied, each deferred Critical or Important finding, a digest of the reviewed files, and the date.

#### Scenario: A READY change gets a review record

- **WHEN** multi-spec's gate rates a change READY with nothing to fix
- **THEN** the gate's commit adds that change's `review.json` with `verdict: READY` and `all_applied: true`

#### Scenario: A finding deferred out of scope

- **WHEN** the gate defers an Important finding as out of scope
- **THEN** the change's record lists it under `deferred` and sets `all_applied: false`

#### Scenario: A review record passes strict validation

- **WHEN** a change directory carries its `review.json`
- **THEN** `openspec validate <name> --strict` and `openspec archive` still pass

### Requirement: multi-spec's batch review is size-gated per change

multi-spec's batch review SHALL apply the checklist's size gate to each change, and SHALL dispatch the three review agents only when at least one change in the batch is large.

#### Scenario: A batch of small changes

- **WHEN** every change in a batch grades small
- **THEN** the batch review runs inline with no agent dispatch

### Requirement: The review report carries no parallelism plan and no claim quota

A change review report SHALL NOT include an implementation-parallelism section and SHALL NOT require a minimum number of verified claims. It SHALL keep the claim-shape sweep row in its open questions.

#### Scenario: A small change is reviewed

- **WHEN** a review report is printed
- **THEN** it has no implementation-parallelism section
- **AND** its open questions carry the claim-shape sweep row

### Requirement: An invented requirement is an Important finding

A change review SHALL report a requirement that describes no observable behaviour change as an Important finding, with dropping it and setting `skip_specs` as the remedy.

#### Scenario: An invented requirement

- **WHEN** a delta adds a requirement that describes no observable behaviour change
- **THEN** the review reports an Important finding whose remedy is to drop it and set `skip_specs`
