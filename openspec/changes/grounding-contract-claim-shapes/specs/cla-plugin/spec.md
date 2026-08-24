## ADDED Requirements

### Requirement: Grounding contract enumerates the claim shapes that do not look like claims

A cla-plugin review workflow whose grounding contract binds every claim to evidence SHALL additionally
enumerate, beside that rule, the sentence shapes whose truth depends on something outside the artifact
but whose grammar is not assertive. The enumeration SHALL be stated as part of the grounding contract
rather than as further independent numbered checks appended to the workflow's check list.

The reason SHALL be recorded with the enumeration: the failures this addresses are **recognition**
failures, not procedure failures. In each reported instance the reviewer already held the grounding
rule, already held the license to read source, and did not engage either — because the sentence
presented as an explanation, a comparison, a specification of output, or a trade rather than as an
assertion about existing code.

**Four shapes SHALL be named**, each stated as a trigger, a resolution naming what to read and what to
resolve it against, a failure mode, and a severity floor. A shape stated only as an instruction to
confirm that a claim is grounded SHALL NOT satisfy this requirement.

1. **Producible state.** Triggered by an artifact specifying a fixed set of example, demo, fixture, or
   sample states a surface must show. Resolution: name and read the production function or query that
   would produce each state; resolve the predicate gating it against the **real corpus** rather than
   the fixture's; record the producing path with the corpus figure, or an explicit not-producible with
   the line that forbids it. Being unable to name a producing path SHALL resolve as **not producible**
   rather than as unresolved. Severity floor: an unproducible state written as a requirement is
   **Critical**, because such a requirement does not fail loudly — the available resolution under
   implementation pressure is to invent the data.
2. **Precedent strictness.** Triggered by an artifact naming an existing shipped implementation as the
   precedent it mirrors, follows, or is modelled on. Resolution: read the named precedent's actual
   mechanism at its path; for each provision the new requirement imposes, record whether the precedent
   satisfies it, does not satisfy it, or does not have it; for each provision the precedent does not
   satisfy, state what the extra strictness buys and who pays. Severity floor: **Important**, rising
   to **Critical** where the provision blocks implementation. The text SHALL state why no other check
   finds this: every other check asks whether the artifact is strong enough, and this one asks whether
   it is stronger than it needs to be.
3. **Guarantee class.** Triggered by an artifact stating that a mechanism prevents, controls,
   serialises, or makes impossible a hazard. Resolution: classify the guarantee as a **code property**
   — a constraint, a lock, a registration, a type, a test that goes red — or a **deployment property**,
   true only because of how many processes, instances, workers, or regions run today; for a code
   property, quote the enforcing line; for a deployment property, require the artifact to say so and to
   name the trigger condition that changes it. Leaving the guarantee unclassified SHALL itself be the
   failure, because the two read identically in prose and the gap becomes visible only once the
   deployment fact changes, at which point the hazard returns with no code change and nothing red.
   Severity floor: a deployment property with no named trigger is **Important**; a deployment property
   described as a code property is **Critical**, being a false statement about what the code enforces.
4. **Compensating coverage and exclusion reach.** Triggered in two ways. Where a change gives up
   automated coverage for a named alternative, the resolution SHALL be to read the named replacement
   and confirm what kind of assertion it actually runs, then state its strength relative to what was
   given up — the given-up half is visible in the diff and the replacement is a promise, so the promise
   is the half verified. Where an exclusion entry is added to any route-, page-, or file-keyed
   allowlist or denylist, the resolution SHALL be to enumerate the components or modules reachable only
   through the excluded surface and, for each, name where it is otherwise covered or state that it is
   not. Severity floor: **Important** for an unverified compensating claim, **Critical** where the
   replacement is measurably weaker than what it replaced.

**The list SHALL be stated as open, by signature rather than by disclaimer.** The common signature
SHALL be given — a sentence is a claim under this contract when its truth depends on something outside
the artifact even though its grammar is not assertive — together with the grammars that hide one: an
explanation, a comparison to something shipped, a specification of output shape, and a trade. A
sentence matching that signature SHALL be in scope whether or not it appears among the named shapes.

**Exactly one numbered check SHALL be added to the workflow's check list**, pointing at the shape list
rather than restating it, so that the shapes are reached during the workflow's verification sweep and
not only by a reader of the contract section. No existing check SHALL be renumbered or reworded, and
every enumeration of which checks the orchestrator runs SHALL be updated to name the new one.

**That check SHALL be stated as outside the mechanical portion that defaults to a fact-gathering
sub-agent**, and the exclusion SHALL appear in the paragraph where the delegation decision is made, not
only where the check is defined. Each shape returns a judgement — a comparison of two mechanisms, a
classification, an assessment of one test's strength against another's — rather than a pass or fail
row, so a sub-agent returning a pass/fail table cannot carry it.

The shapes SHALL be stated so that no repository-specific mechanism, product name, or infrastructure
identifier from the reporting instances travels into the portable text.

#### Scenario: The shapes are named inside the grounding contract

- **WHEN** the review workflow's grounding contract is stated
- **THEN** the four claim shapes are enumerated as part of that contract
- **AND** they are not added as four further independent numbered checks

#### Scenario: Each shape is executable rather than an instruction to verify

- **WHEN** a claim shape is stated
- **THEN** it names its trigger, the resolution steps naming what to read and what to resolve it against, its failure mode, and its severity floor
- **AND** a shape whose text only instructs the reviewer to confirm the claim is grounded is treated as not meeting the requirement

#### Scenario: An unproducible demo state resolves negative rather than unresolved

- **WHEN** a reviewer cannot name the production path that would produce a specified demo state
- **THEN** the state resolves as not producible rather than as unresolved
- **AND** the requirement specifying it is graded Critical

#### Scenario: A guarantee is classified before it is accepted

- **WHEN** an artifact states that a mechanism prevents a hazard
- **THEN** the reviewer classifies the guarantee as a code property or a deployment property
- **AND** a code property is resolved by quoting the enforcing line
- **AND** a deployment property is accepted only where the artifact says so and names the trigger that changes it

#### Scenario: A compensating-coverage claim is read rather than accepted

- **WHEN** a change gives up automated coverage in exchange for a named alternative
- **THEN** the reviewer reads the named replacement and records what kind of assertion it actually runs
- **AND** states the replacement's strength relative to what was given up

#### Scenario: An exclusion's reach is enumerated

- **WHEN** an exclusion entry is added to a route-, page-, or file-keyed allowlist or denylist
- **THEN** the components or modules reachable only through the excluded surface are enumerated
- **AND** each is paired with where it is otherwise covered, or stated to be uncovered

#### Scenario: An unnamed shape matching the signature is in scope

- **WHEN** an artifact carries a sentence whose truth depends on code, corpus, precedent, deployment, or a test file, phrased as an explanation, a comparison, an output specification, or a trade
- **THEN** the contract covers it whether or not it matches one of the named shapes
- **AND** the contract states this as a signature rather than as a closing disclaimer

#### Scenario: The sweep reaches the shapes and is not delegated

- **WHEN** the workflow's verification sweep runs
- **THEN** one numbered check points at the shape list, and every enumeration of the orchestrator's checks names it
- **AND** that check is stated as outside the mechanical portion that defaults to a fact-gathering sub-agent
- **AND** the exclusion appears in the paragraph where the delegation decision is made

### Requirement: Reviewer report severities are reconciled by the evidence behind them

A cla-plugin review workflow that dispatches more than one reviewer and merges their reports SHALL
state how a finding reported by two of them at different severities is graded. Where the reports
disagree, the merged severity SHALL be taken from the report whose evidence for that severity is
**implementation-level** — a source line, a schema, a migration, a query result — over the report
whose evidence is the specification delta or the artifact text alone.

**The rule SHALL key on the evidence attached to the finding, not on which reviewer reported it.**
Where every dispatched reviewer is licensed to read source, the reviewer's role does not identify who
read the implementation, so a role-keyed rule is not decidable from the reports the orchestrator
holds. The evidence is, and it is present because the grounding contract already requires every
finding to carry its resolving evidence.

Where neither report's evidence is implementation-level, or both are, the **higher severity SHALL
stand**. This fallback SHALL NOT be stated as the primary rule: applied unconditionally it converts
every disagreement into an escalation, inflating the counts that the workflow's own verdict rubric
already warns against reading literally.

The tie-break SHALL be recorded on the finding it resolved, so that a reader can see one occurred, and
SHALL NOT add a line to the report, which is budgeted at one line per finding.

**The rule's evidence SHALL be stated with it and SHALL NOT be presented as measured.** It rests on a
single overlapping finding out of eighteen, from one change in one chain in one consuming repository,
and the observed instance was a two-reviewer split under a different workflow rather than the dispatch
this rule governs. The text SHALL state that low overlap is the reviewer split working as intended and
that the rule is therefore expected to fire rarely.

#### Scenario: Two reports grade one finding differently

- **WHEN** two dispatched reviewers report the same finding at different severities
- **THEN** the merged severity is taken from the report whose evidence is implementation-level
- **AND** the report whose evidence is the specification delta or artifact text alone does not set the severity

#### Scenario: Neither report's evidence discriminates

- **WHEN** neither report's evidence for the severity is implementation-level, or both are
- **THEN** the higher severity stands
- **AND** this is stated as the fallback rather than as the rule

#### Scenario: The tie-break is visible without costing a report line

- **WHEN** a severity tie-break is applied
- **THEN** it is recorded on the finding it resolved
- **AND** no additional line is added to the report

#### Scenario: The rule carries its own evidence honestly

- **WHEN** the tie-break rule is stated
- **THEN** it names its single supporting instance and the total it came from
- **AND** it states that the instance came from a different dispatch shape
- **AND** it is not described as measured
