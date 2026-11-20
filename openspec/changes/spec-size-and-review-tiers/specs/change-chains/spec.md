## ADDED Requirements

### Requirement: An author checks its change's size before reporting it done

During `/cla:multi-spec`, each change's author SHALL check the change against the whole-change budget and the word limits that `rules.proposal` and `rules.design` in the repo's `openspec/config.yaml` state, and SHALL cut what is over before it reports the change done.

#### Scenario: A proposal over its word limit

- **WHEN** an author's proposal counts 520 words outside its `## Open questions` and `## Risks noted` sections, and `rules.proposal` says about 400
- **THEN** the author cuts the proposal to 400 words or fewer, counted the same way, before it reports the change done

#### Scenario: Open questions are not cut to fit

- **WHEN** a proposal is over 400 words only because of its `## Open questions` and `## Risks noted` sections
- **THEN** nothing is cut, and every open question reaches the owner

### Requirement: What still does not fit is reported and the batch goes on

An author SHALL NOT cut a requirement that guards a protected area to meet the budget, SHALL name in its report whatever is still over, and `/cla:multi-spec` SHALL carry that into the batch report and pull request and go on to the next change.

#### Scenario: Protected requirements over the budget

- **WHEN** a change's requirements that guard a protected area alone exceed the requirement budget
- **THEN** every one of them stays, the report and the pull request name the overrun, and the next change is authored

#### Scenario: A budget that could not be checked

- **WHEN** the budget checker cannot run on the change
- **THEN** the report says the budget was not checked, and never that the change fits
