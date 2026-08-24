## ADDED Requirements

### Requirement: A MODIFIED block is compared against the live requirement it replaces

A skill that reviews, archives, or sequences a change SHALL compare each `## MODIFIED Requirements` block's scenario set against the live requirement that block will replace, and SHALL NOT treat the block's internal completeness as evidence of retention.

A modified-requirement block replaces its named requirement wholesale rather than patching it, so a scenario present on the live requirement and absent from the block is deleted at sync or archive with nothing reporting the loss. The block is internally consistent either way: it carries a full requirement text and a list of scenarios in both the retaining and the dropping case, so **the omission is not visible in the delta at all** and any instruction phrased as a property of the delta alone cannot be checked.

**The obligation attaches to the block, not to the workflow that produced it.** It SHALL apply wherever a change carrying such a block is reviewed before implementation, prepared for archive, or sequenced within a batch — a change authored and shipped outside any batch passes through no cross-change sequencing step and would otherwise be compared nowhere.

**The comparison baseline SHALL be the live specification as it stands at the moment of the check**, not as the delta was authored. A correct block goes stale when anything else reaches the live specification first — a sibling in the same batch, a change archived from an earlier batch, a small change landed in between, a hand edit.

**Where a step already locates the live requirement for another purpose, the comparison SHALL be carried by that step** rather than added beside it. A step that confirms a modified block's heading exists in the live specification has already resolved the requirement the comparison needs, and stopping at the heading is what leaves scenario retention unchecked.

This requirement is distinct from validating the live specification set's parse integrity after an edit: that concerns whether the document still parses, whereas this concerns content the delta silently omits, which parses correctly and reads correctly. It is also distinct from an enforcing refusal inside the tool that applies the delta — **nothing in this requirement blocks, edits, or refuses a change.**

#### Scenario: A change outside a batch is still compared

- **WHEN** a change carrying a modified-requirement block is taken to a pull request on its own, passing through no cross-change sequencing step
- **THEN** the comparison runs anyway, at that change's own pre-implementation review and again before its archive
- **AND** a comparison available only to batch-sequenced changes does not satisfy this

#### Scenario: Heading existence is not retention

- **WHEN** a step confirms that a modified block's requirement heading exists verbatim in the live specification
- **THEN** that step also compares the scenario headings under it
- **AND** a confirmed heading with an unexamined scenario set is recorded as unchecked, not as a pass

#### Scenario: A delta that looks complete on its own face

- **WHEN** a modified block carries a full requirement text and a list of scenarios, while the live requirement it replaces carries more scenarios than the block does
- **THEN** the comparison reports the difference
- **AND** an instruction satisfied by reading the delta alone is treated as not covering this

#### Scenario: The baseline is current, not as-authored

- **WHEN** the live requirement changed after the delta was written
- **THEN** the comparison reads the live specification as it stands at the moment of the check
- **AND** comparing against the text the delta was authored against does not satisfy this

#### Scenario: A change with no modified block

- **WHEN** a change's delta contains no modified-requirement block
- **THEN** the check is reported as not applicable, naming what was scanned
- **AND** it is not recorded as a passing comparison

### Requirement: Renames are resolved before a comparison reports a loss

A retention comparison SHALL resolve the delta's requirement-rename mapping before matching a modified block to a live requirement, and SHALL treat every remaining difference as a flag for adjudication rather than as a confirmed loss.

A rename and a deletion are byte-identical to a comparison of headings, and exactly one of them destroys a live normative statement. Ordering is therefore load-bearing: a comparison that resolves renames at any later point reports every renamed requirement as missing from the live specification. This was measured — the one real execution of an unordered comparison flagged two items across two changes and both were benign renames, one of them caused precisely by an unresolved rename mapping.

**Rename resolution SHALL NOT be claimed to eliminate false positives.** A rename mapping names requirements, not scenarios, so a scenario renamed in place — its heading rewritten to widen its scope, its content retained — remains indistinguishable from a deleted scenario and remains flagged. That was the second of the two measured flags. A residual false-positive rate is a property of the delta format, not a defect in the procedure.

**Because a flag can be a rename, nothing SHALL refuse, halt, or auto-correct on a flag alone.** Each flagged scenario SHALL be adjudicated to exactly one of: renamed, intentionally removed, or dropped. Only *dropped* is a finding. An intentional removal SHALL cite the change's own artifacts; asserted without a citation it carries a lower severity than a drop but is still reported, because the verdict is then a claim rather than a reference.

**An unadjudicated flag SHALL be treated as dropped, not as waived.** The comparison exists to force an adjudication, and defaulting an unexamined flag to benign returns the situation to the one where the loss is silent.

#### Scenario: A requirement renamed by the same delta

- **WHEN** a modified block names a requirement that does not appear in the live specification, because the same delta's rename section renames it
- **THEN** the rename is resolved first and the block is matched to the live requirement under its old name
- **AND** the requirement is not reported as absent

#### Scenario: A scenario renamed in place is still flagged

- **WHEN** a live scenario's heading was rewritten in the delta to widen its scope, with its behaviour retained
- **THEN** it is flagged as missing and adjudicated as renamed
- **AND** the procedure does not claim to have distinguished it mechanically

#### Scenario: A flag does not block the change

- **WHEN** a comparison flags one or more scenarios
- **THEN** the change is not refused, halted, or edited by the comparison itself
- **AND** the flag is carried to whoever adjudicates it

#### Scenario: An unadjudicated flag is a finding

- **WHEN** a flagged scenario reaches the end of the step with no verdict recorded
- **THEN** it is treated as dropped and reported at the severity a dropped scenario carries
- **AND** it is not recorded as resolved because nothing contradicted it

### Requirement: A retention report states both directions and its denominator

A retention comparison SHALL report added scenario counts alongside missing ones, for every compared requirement, including one where nothing is missing.

A missing-only report cannot separate a widening from a truncation. Both present as "one scenario missing", and telling them apart then costs opening both documents — the work the report exists to remove. Stating the live count, the delta count and both differences on one line makes a block that grew and reorganised distinguishable at a glance from one that lost a normative statement.

**A comparison that found nothing SHALL still report what it examined.** Silence and a clean result are indistinguishable to a reader, and so are a clean result and a step that did not run. The report SHALL name how many modified requirements were compared, across how many capabilities, how many were flagged, and how many flags were adjudicated to each verdict.

**A failed enumeration SHALL be reported as a failed check, not as an empty result.** A command that errors — run from the wrong directory, against a repository that stores its specifications elsewhere, against a capability whose live file is absent — yields no headings, and reading that as "no differences" converts a check that never ran into a confident pass across every requirement it was meant to cover.

#### Scenario: A widening is distinguishable from a truncation

- **WHEN** a modified block carries more scenarios than the live requirement, while one live scenario heading is absent from it
- **THEN** the report states the live count, the delta count, the added count and the missing count together
- **AND** a reader distinguishes the widening from a truncation without opening either document

#### Scenario: A clean requirement is reported, not omitted

- **WHEN** a compared requirement's scenario sets match exactly
- **THEN** the report states its counts with both differences at zero
- **AND** omitting it is not treated as reporting it

#### Scenario: The run states its denominator

- **WHEN** a step finishes comparing a change's modified blocks
- **THEN** it reports how many requirements were compared across how many capabilities, how many were flagged, and how each flag was adjudicated
- **AND** a bare statement that nothing was found does not satisfy this

#### Scenario: An enumeration that errored is not zero differences

- **WHEN** a command enumerating headings from either document exits non-zero
- **THEN** the check is reported as failed for that requirement
- **AND** the absent headings are not read as an empty set, and no requirement covered by that command is reported as clean
