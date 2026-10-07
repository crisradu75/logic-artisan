# change-review Specification

## Purpose

How a change is reviewed before implementation: which claims get verified, how findings are graded and merged, and the findings an oversized or unproven artifact earns.

## Requirements

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

### Requirement: multi-spec's batch review is size-gated per change

multi-spec's batch review SHALL apply the checklist's size gate to each change, and SHALL dispatch the three review agents only when at least one change in the batch is large.

#### Scenario: A batch of small changes

- **WHEN** every change in a batch grades small
- **THEN** the batch review runs inline with no agent dispatch

### Requirement: The review report carries no parallelism plan and no claim quota

A change review report SHALL NOT include an implementation-parallelism section and SHALL NOT require a minimum number of verified claims.

#### Scenario: A small change is reviewed

- **WHEN** a review report is printed
- **THEN** it has no implementation-parallelism section
- **AND** it does not pad its verified claims to reach a count

### Requirement: An invented requirement is an Important finding

A change review SHALL report a requirement that describes no observable behaviour change as an Important finding, with dropping it and setting `skip_specs` as the remedy.

#### Scenario: An invented requirement

- **WHEN** a delta adds a requirement that describes no observable behaviour change
- **THEN** the review reports an Important finding whose remedy is to drop it and set `skip_specs`

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
