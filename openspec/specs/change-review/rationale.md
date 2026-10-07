# change-review — rationale

Why requirements in `spec.md` exist, and the detail they compress. Moved out when the requirements
were compacted (#293), edited only so each section reads on its own. Headings name the requirement
each section explains; a requirement with no section here has no reasoning beyond its own text.

## The claim-shape enumeration records its reason

In each reported instance the reviewer already held the grounding rule, already held the license to
read source, and did not engage either — because the sentence presented as an explanation, a
comparison, a specification of output, or a trade rather than as an assertion about existing code.

## Producible state is resolved against the data the system will run on

The shape as first specified:

> **Producible state.** Triggered by an artifact specifying a fixed set of example, demo, fixture, or
> sample states a surface must show. Resolution: name and read the production function or query that
> would produce each state; resolve the predicate gating it against the **real data the system will run on** rather than
> the fixture's; record the producing path with the corpus figure, or an explicit not-producible with
> the line that forbids it. Having searched and found no producing path SHALL resolve as **not producible**; NOT having searched SHALL resolve as unresolved, and SHALL carry no severity floor. The negative default applies once the reviewer has looked, because an absent producing path is itself the finding — it does not apply to a reviewer who ran out of budget, which the grounding contract already routes to unresolved. Severity floor: an unproducible state written as a requirement is
> **Critical**, because such a requirement does not fail loudly — the available resolution under
> implementation pressure is to invent the data.

## A named precedent is checked for extra strictness

The shape as first specified:

> **Precedent strictness.** Triggered by an artifact naming an existing shipped implementation as the
> precedent it mirrors, follows, or is modelled on. Resolution: read the named precedent's actual
> mechanism at its path; for each provision the new requirement imposes, record whether the precedent
> satisfies it, does not satisfy it, or does not have it; for each provision the precedent does not
> satisfy, state what the extra strictness buys and who pays. Severity floor: **Important**, rising
> to **Critical** where the provision blocks implementation. The text SHALL state why no other check
> finds this: every other check asks whether the artifact is strong enough, and this one asks whether
> it is stronger than it needs to be.

## A guarantee is classified as a code or a deployment property

The shape as first specified:

> **Guarantee class.** Triggered by an artifact stating that a mechanism prevents, controls,
> serialises, or makes impossible a hazard. Resolution: classify the guarantee as a **code property**
> — a constraint, a lock, a registration, a type, a test that goes red — or a **deployment property**,
> true only because of how many processes, instances, workers, or regions run today; for a code
> property, quote the enforcing line; for a deployment property, require the artifact to say so and to
> name the trigger condition that changes it. Leaving the guarantee unclassified SHALL itself be the
> failure, because the two read identically in prose and the gap becomes visible only once the
> deployment fact changes, at which point the hazard returns with no code change and nothing red.
> Severity floor: a deployment property with no named trigger is **Important**; a deployment property
> described as a code property is **Critical**, being a false statement about what the code enforces.

## A compensating-coverage claim is read, not accepted

Shape 4, compensating coverage and exclusion reach, as first specified:

> **Compensating coverage and exclusion reach.** Triggered in two ways. Where a change gives up
> automated coverage for a named alternative, the resolution SHALL be to read the named replacement
> and confirm what kind of assertion it actually runs, then state its strength relative to what was
> given up — the given-up half is visible in the diff and the replacement is a promise, so the promise
> is the half verified. Where an exclusion entry is added to any keyed allowlist or denylist, the resolution SHALL be to enumerate the components or modules reachable only
> through the excluded surface and, for each, name where it is otherwise covered or state that it is
> not. Severity floor: **Important** for an unverified compensating claim, **Critical** where the
> replacement is measurably weaker than what it replaced.

## An exclusion's reach is enumerated

Exclusion reach is the second trigger of shape 4; its original text is quoted under "A
compensating-coverage claim is read, not accepted".

## One numbered check reaches the claim shapes and is not delegated

The check exists so that the shapes are reached during the workflow's verification sweep and not only
by a reader of the contract section. Each shape returns a judgement — a comparison of two mechanisms, a
classification, an assessment of one test's strength against another's — rather than a pass or fail
row, so a sub-agent returning a pass/fail table cannot carry it.

Originally specified as: "No existing check SHALL be renumbered or reworded, and every enumeration of
which checks the orchestrator runs SHALL be updated to name the new one."

## The severity rule keys on evidence, with the higher severity as fallback

Where every dispatched reviewer is licensed to read source, the reviewer's role does not identify who
read the implementation, so a role-keyed rule is not decidable from the reports the orchestrator
holds. The evidence is, and it is present because the grounding contract already requires every
finding to carry its resolving evidence.

Applied unconditionally, the fallback converts every disagreement into an escalation, inflating the
counts that the workflow's own verdict rubric already warns against reading literally.

## The tie-break rule states its evidence without claiming measurement

The rule rests on a single overlapping finding out of eighteen, from one change in one chain in one
consuming repository, and the observed instance was a two-reviewer split under a different workflow
rather than the dispatch this rule governs.

## A MODIFIED block is compared against the live requirement it replaces

A modified-requirement block replaces its named requirement wholesale rather than patching it, so a scenario present on the live requirement and absent from the block is deleted at sync or archive. A current `openspec` refuses that apply, and a repo on an older version gets no such refusal — so the loss is caught late, by a tool the plugin does not own and may not be running, or not at all. The block is internally consistent either way: it carries a full requirement text and a list of scenarios in both the retaining and the dropping case, so **the omission is not visible in the delta at all** and any instruction phrased as a property of the delta alone cannot be checked.

This requirement is distinct from validating the live specification set's parse integrity after an edit: that concerns whether the document still parses, whereas this concerns content the delta silently omits, which parses correctly and reads correctly. It is also distinct from an enforcing refusal inside the tool that applies the delta.

## The comparison attaches to the block, not the workflow

A change authored and shipped outside any batch passes through no cross-change sequencing step and would otherwise be compared nowhere.

## The comparison baseline is the live specification at check time

A correct block goes stale when anything else reaches the live specification first — a sibling in the same batch, a change archived from an earlier batch, a small change landed in between, a hand edit.

## A step that already locates the live requirement carries the comparison

A step that confirms a modified block's heading exists in the live specification has already resolved the requirement the comparison needs, and stopping at the heading is what leaves scenario retention unchecked.

## Renames are resolved before a comparison reports a loss

A rename and a deletion are byte-identical to a comparison of headings, and exactly one of them destroys a live normative statement. Ordering is therefore load-bearing: a comparison that resolves renames at any later point reports every renamed requirement as missing from the live specification. This was measured — the one real execution of an unordered comparison flagged two items across two changes and both were benign renames, one of them caused precisely by an unresolved rename mapping.

A rename mapping names requirements, not scenarios, so a scenario renamed in place — its heading rewritten to widen its scope, its content retained — remains indistinguishable from a deleted scenario and remains flagged. That was the second of the two measured flags. A residual false-positive rate is a property of the delta format, not a defect in the procedure.

## A flag is adjudicated, never acted on alone

An uncited intentional removal is still reported because the verdict is then a claim rather than a reference.

## An unadjudicated flag is treated as dropped

The comparison exists to force an adjudication, and defaulting an unexamined flag to benign returns the situation to the one where the loss is silent.

## A retention report states both directions and its denominator

A missing-only report cannot separate a widening from a truncation. Both present as "one scenario missing", and telling them apart then costs opening both documents — the work the report exists to remove. Stating the live count, the delta count and both differences on one line makes a block that grew and reorganised distinguishable at a glance from one that lost a normative statement.

## A clean comparison still states what it examined

Silence and a clean result are indistinguishable to a reader, and so are a clean result and a step that did not run.

## A failed enumeration is a failed check

A command that errors — run from the wrong directory, against a repository that stores its specifications elsewhere, against a capability whose live file is absent — yields no headings, and reading that as "no differences" converts a check that never ran into a confident pass across every requirement it was meant to cover.
