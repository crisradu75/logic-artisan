## ADDED Requirements

### Requirement: Hidden claims are verified

The review SHALL treat a sentence whose truth depends on the code, real data, a cited existing implementation or the deployment as a claim to verify, even when it reads as an explanation, a comparison or a trade-off.

#### Scenario: A comparison to shipped code is checked

- **WHEN** an artifact says its design mirrors an existing implementation
- **THEN** the reviewer reads that implementation and reports where the artifact's claim about it is wrong

### Requirement: A MODIFIED block keeps its live scenarios

The review SHALL run `openspec validate <change> --strict` and SHALL report a MODIFIED block that drops a scenario the live requirement still has as Critical, because archive would delete it.

#### Scenario: A MODIFIED block drops a live scenario

- **WHEN** a change's MODIFIED block omits a scenario the live requirement has
- **THEN** `openspec validate <change> --strict` fails and the review reports it as Critical

### Requirement: The same finding at two severities keeps the higher

Where two reviewers report the same finding at different severities, the review SHALL keep the higher severity.

#### Scenario: Two reviewers disagree on severity

- **WHEN** one reviewer reports a finding as Important and another reports it as Critical
- **THEN** the merged report lists it once, as Critical

## REMOVED Requirements

### Requirement: Grounding contract enumerates the claim shapes that do not look like claims

**Reason**: Four fixed claim-shape procedures cost about 1,900 words per review and no record shows one catching anything.

**Migration**: Replaced by "Hidden claims are verified".

### Requirement: Each claim shape is stated as an executable check

**Reason**: Four fixed claim-shape procedures cost about 1,900 words per review and no record shows one catching anything.

**Migration**: Replaced by "Hidden claims are verified".

### Requirement: The claim-shape enumeration records its reason

**Reason**: Four fixed claim-shape procedures cost about 1,900 words per review and no record shows one catching anything.

**Migration**: Replaced by "Hidden claims are verified".

### Requirement: Producible state is resolved against the data the system will run on

**Reason**: Four fixed claim-shape procedures cost about 1,900 words per review and no record shows one catching anything.

**Migration**: Replaced by "Hidden claims are verified".

### Requirement: A producible-state search that finds nothing resolves negative

**Reason**: Four fixed claim-shape procedures cost about 1,900 words per review and no record shows one catching anything.

**Migration**: Replaced by "Hidden claims are verified".

### Requirement: A named precedent is checked for extra strictness

**Reason**: Four fixed claim-shape procedures cost about 1,900 words per review and no record shows one catching anything.

**Migration**: Replaced by "Hidden claims are verified".

### Requirement: Precedent strictness states its floor and why no other check finds it

**Reason**: Four fixed claim-shape procedures cost about 1,900 words per review and no record shows one catching anything.

**Migration**: Replaced by "Hidden claims are verified".

### Requirement: A guarantee is classified as a code or a deployment property

**Reason**: Four fixed claim-shape procedures cost about 1,900 words per review and no record shows one catching anything.

**Migration**: Replaced by "Hidden claims are verified".

### Requirement: An unclassified guarantee is itself the failure

**Reason**: Four fixed claim-shape procedures cost about 1,900 words per review and no record shows one catching anything.

**Migration**: Replaced by "Hidden claims are verified".

### Requirement: A compensating-coverage claim is read, not accepted

**Reason**: Four fixed claim-shape procedures cost about 1,900 words per review and no record shows one catching anything.

**Migration**: Replaced by "Hidden claims are verified".

### Requirement: An exclusion's reach is enumerated

**Reason**: Four fixed claim-shape procedures cost about 1,900 words per review and no record shows one catching anything.

**Migration**: Replaced by "Hidden claims are verified".

### Requirement: The claim-shape list is open by signature

**Reason**: Four fixed claim-shape procedures cost about 1,900 words per review and no record shows one catching anything.

**Migration**: Replaced by "Hidden claims are verified".

### Requirement: The claim shapes are portable

**Reason**: Four fixed claim-shape procedures cost about 1,900 words per review and no record shows one catching anything.

**Migration**: Replaced by "Hidden claims are verified".

### Requirement: One numbered check reaches the claim shapes and is not delegated

**Reason**: Four fixed claim-shape procedures cost about 1,900 words per review and no record shows one catching anything.

**Migration**: Replaced by "Hidden claims are verified".

### Requirement: Reviewer report severities are reconciled by the evidence behind them

**Reason**: The evidence-based tie-break rested on one case in 18 and contradicted the shipped checklist, which keeps the higher severity.

**Migration**: Replaced by "The same finding at two severities keeps the higher".

### Requirement: The severity rule keys on evidence, with the higher severity as fallback

**Reason**: The evidence-based tie-break rested on one case in 18 and contradicted the shipped checklist, which keeps the higher severity.

**Migration**: Replaced by "The same finding at two severities keeps the higher".

### Requirement: A severity tie-break is recorded on its finding

**Reason**: The evidence-based tie-break rested on one case in 18 and contradicted the shipped checklist, which keeps the higher severity.

**Migration**: Replaced by "The same finding at two severities keeps the higher".

### Requirement: The tie-break rule states its evidence without claiming measurement

**Reason**: The evidence-based tie-break rested on one case in 18 and contradicted the shipped checklist, which keeps the higher severity.

**Migration**: Replaced by "The same finding at two severities keeps the higher".

### Requirement: A MODIFIED block is compared against the live requirement it replaces

**Reason**: `openspec validate <change> --strict` (verified on 1.14.1) already fails a MODIFIED block that drops a live scenario, after resolving renames, so the hand-run comparison duplicated the tool.

**Migration**: Replaced by "A MODIFIED block keeps its live scenarios". cla-init reports an older OpenSpec.

### Requirement: The comparison attaches to the block, not the workflow

**Reason**: `openspec validate <change> --strict` (verified on 1.14.1) already fails a MODIFIED block that drops a live scenario, after resolving renames, so the hand-run comparison duplicated the tool.

**Migration**: Replaced by "A MODIFIED block keeps its live scenarios". cla-init reports an older OpenSpec.

### Requirement: The comparison baseline is the live specification at check time

**Reason**: `openspec validate <change> --strict` (verified on 1.14.1) already fails a MODIFIED block that drops a live scenario, after resolving renames, so the hand-run comparison duplicated the tool.

**Migration**: Replaced by "A MODIFIED block keeps its live scenarios". cla-init reports an older OpenSpec.

### Requirement: A step that already locates the live requirement carries the comparison

**Reason**: `openspec validate <change> --strict` (verified on 1.14.1) already fails a MODIFIED block that drops a live scenario, after resolving renames, so the hand-run comparison duplicated the tool.

**Migration**: Replaced by "A MODIFIED block keeps its live scenarios". cla-init reports an older OpenSpec.

### Requirement: Renames are resolved before a comparison reports a loss

**Reason**: `openspec validate <change> --strict` (verified on 1.14.1) already fails a MODIFIED block that drops a live scenario, after resolving renames, so the hand-run comparison duplicated the tool.

**Migration**: Replaced by "A MODIFIED block keeps its live scenarios". cla-init reports an older OpenSpec.

### Requirement: A flag is adjudicated, never acted on alone

**Reason**: `openspec validate <change> --strict` (verified on 1.14.1) already fails a MODIFIED block that drops a live scenario, after resolving renames, so the hand-run comparison duplicated the tool.

**Migration**: Replaced by "A MODIFIED block keeps its live scenarios". cla-init reports an older OpenSpec.

### Requirement: An unadjudicated flag is treated as dropped

**Reason**: `openspec validate <change> --strict` (verified on 1.14.1) already fails a MODIFIED block that drops a live scenario, after resolving renames, so the hand-run comparison duplicated the tool.

**Migration**: Replaced by "A MODIFIED block keeps its live scenarios". cla-init reports an older OpenSpec.

### Requirement: A retention report states both directions and its denominator

**Reason**: `openspec validate <change> --strict` (verified on 1.14.1) already fails a MODIFIED block that drops a live scenario, after resolving renames, so the hand-run comparison duplicated the tool.

**Migration**: Replaced by "A MODIFIED block keeps its live scenarios". cla-init reports an older OpenSpec.

### Requirement: A clean comparison still states what it examined

**Reason**: `openspec validate <change> --strict` (verified on 1.14.1) already fails a MODIFIED block that drops a live scenario, after resolving renames, so the hand-run comparison duplicated the tool.

**Migration**: Replaced by "A MODIFIED block keeps its live scenarios". cla-init reports an older OpenSpec.

### Requirement: A failed enumeration is a failed check

**Reason**: `openspec validate <change> --strict` (verified on 1.14.1) already fails a MODIFIED block that drops a live scenario, after resolving renames, so the hand-run comparison duplicated the tool.

**Migration**: Replaced by "A MODIFIED block keeps its live scenarios". cla-init reports an older OpenSpec.

### Requirement: A change multi-spec already reviewed skips the checklist pass

**Reason**: The review.json skip never ran (`git log --all -- '*/review.json'` is empty) and cost about 1,100 words across skills and spec.

**Migration**: spec-to-pr always runs its own Review.

### Requirement: multi-spec records each change's review verdict

**Reason**: The review.json skip never ran (`git log --all -- '*/review.json'` is empty) and cost about 1,100 words across skills and spec.

**Migration**: spec-to-pr always runs its own Review.

