## ADDED Requirements

### Requirement: An author checks its change's size before reporting it done

During `/cla:multi-spec`, each change's author SHALL check the change against the whole-change budget and the word limits that `rules.proposal` and `rules.design` in the repo's `openspec/config.yaml` state, counting proposal.md without its `## Open questions` and `## Risks noted` sections, and SHALL cut what is over, never an open question, before it reports the change done.

#### Scenario: A proposal over its word limit

- **WHEN** an author's proposal counts 520 words outside its `## Open questions` and `## Risks noted` sections, and `rules.proposal` says about 400
- **THEN** the author cuts the proposal until `wc -w` outside those two sections gives 400 or fewer, before it reports the change done

#### Scenario: One word over

- **WHEN** a proposal counts 401 words outside those two sections and `rules.proposal` says about 400
- **THEN** the author treats it as over and cuts it, because any count above the config's figure is over

#### Scenario: An open question is not cut to fit

- **WHEN** a proposal fits its limit only if one of its open questions is cut
- **THEN** the question stays, and the report names the overrun

### Requirement: An overrun that could not be cut is reported and the batch goes on

An author SHALL name in its report whatever overrun it could not cut, and `/cla:multi-spec` SHALL carry that into the batch report and pull request and go on to the next change.

#### Scenario: Protected requirements over the budget

- **WHEN** a change's requirements that guard a protected area alone exceed the requirement budget
- **THEN** every one of them stays, the report and the pull request name the overrun, and the next change is authored

#### Scenario: A budget that could not be checked

- **WHEN** the budget checker cannot run on the change
- **THEN** the report says the budget was not checked, and never that the change fits
