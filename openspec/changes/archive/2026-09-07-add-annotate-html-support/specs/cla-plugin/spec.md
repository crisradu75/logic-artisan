## ADDED Requirements

### Requirement: A document that carries its own presentation is annotated as presented

A skill that puts a document in front of a reader to be marked up SHALL, where that document carries its own presentation, present it as its author wrote it rather than substituting the skill's own rendering.

The reason is what the reader is being asked to judge. Where a document's layout, typography, tables and figures are part of the artifact under review, a rendering that keeps only the words has discarded half of what was submitted — and it does so silently, because the extracted page is perfectly readable and gives no sign that anything is missing. A skill SHALL NOT present an extraction as the document.

The obligation binds only where the presentation is the document's own. A format with no presentation of its own — plain text, or a markup the skill itself renders — has nothing to preserve, and the skill's rendering IS the presentation there.

**Where the document's presentation cannot be honoured, the skill SHALL say so rather than degrade quietly.** A target the renderer cannot present as authored is reported as such, with the reason, so the reader knows which of the two they are looking at.

#### Scenario: A designed document opens as designed

- **WHEN** the reader annotates a document that carries its own styling and layout
- **THEN** the document is shown with that styling and layout intact
- **AND** the annotation surfaces — the selection affordance, the margin, the drawer — are available over it

#### Scenario: A format with no presentation of its own is unaffected

- **WHEN** the reader annotates a plain-text or Markdown document
- **THEN** the skill's own rendering is used, exactly as before this change

#### Scenario: A presentation that cannot be honoured is reported, not silently degraded

- **WHEN** the renderer cannot present a document as its author wrote it
- **THEN** the reader is told which of the two they are looking at, and why
- **AND** the page does not render as though nothing were wrong

### Requirement: Instrumentation of a reader's document is additive and reversible

Where a skill must add machine-readable structure to a document it did not write — identifiers that bind an annotation to a passage — that instrumentation SHALL be **additive only**: it adds attributes to markup that is already there, plus at most the presentation the annotation layer itself needs in order to be visible, and changes nothing else about the file's bytes.

**What the layer adds for itself SHALL be enumerable, appended rather than interleaved, and self-contained.** Enumerable, so the reversibility check below can subtract it. Appended, so it shifts no position the instrumentation has already recorded for the content above it. Self-contained, because it is the one thing that crosses an isolation boundary the rest of this design exists to maintain — anything it inherits from the other side of that boundary resolves to nothing, and does so silently.

**The reversibility SHALL be verified as a property, not asserted.** Removing everything the instrumentation added — the attributes AND the layer's own appended presentation — SHALL yield the original input byte for byte, and the skill SHALL carry a test that checks exactly that. A transform that rewrites, normalises, reformats or re-serialises the document has changed the artifact under review into a different artifact, and the reader would be annotating the skill's opinion of their document rather than their document.

This is also what makes the presentation obligation above checkable. "The page looks the same" is a judgement; "the bytes outside the injected attributes are identical" is a measurement, and it is the one that catches a renderer quietly normalising an author's markup.

**The document itself is never written to.** The instrumented copy is a separate artifact in working storage; the reversibility property is about that copy's relationship to the source, not a licence to modify the source and undo it.

**Where the document already uses an identifier the instrumentation would add, the renderer SHALL refuse it rather than emit a page.** Additive instrumentation assumes the identifiers it adds are its own. Where they are not, the collision does not announce itself: the markup language's own rule for a repeated identifier decides which value wins, and every later lookup silently resolves to the author's. An annotation then anchors to whatever their value named, and nothing on the page looks wrong. This is the one case where refusing beats rendering, because the defect it prevents is invisible to the reader and they would have no reason to doubt what they were shown.

#### Scenario: The injected attributes strip back to the original

- **WHEN** the instrumented output has its injected attributes removed
- **THEN** the result is byte-identical to the source document

#### Scenario: The source document is unchanged by rendering

- **WHEN** a document is rendered for annotation
- **THEN** the source file's contents are unchanged

#### Scenario: A document already using the instrumentation's own attributes is refused

- **WHEN** the document already carries an attribute the instrumentation would add
- **THEN** the renderer refuses the document and names the offending element
- **AND** it does not emit a page whose annotations would anchor to the author's value

### Requirement: An annotatable block is chosen by structure, not by a fixed tag list

A renderer that divides a document into addressable blocks SHALL choose them by a structural rule, and SHALL NOT rely on a fixed list of the tags that usually hold prose.

The rule SHALL select the **innermost** element that holds text and is not purely inline, so that the selected blocks are disjoint. Disjointness is not cosmetic: the anchor check, the word count and the "which block did this selection start in" lookup all assume a passage belongs to exactly one block, and nested blocks make each of those ambiguous.

**A tag allowlist fails in the direction that is hardest to notice.** Content the author built out of generic containers — a chart row, a stat tile, a figure caption in a wrapper — is not a paragraph and not a list item, so an allowlist silently makes it unannotatable. The reader sees a document where some passages accept a comment and others do not, with no rule they can infer. Measured on the motivating document: a paragraph-and-list-item rule leaves its entire waterfall chart, built from generic containers holding inline spans, outside every block.

**A subtree whose internal structure is not prose SHALL be treated as one block rather than divided.** A vector figure is a single thing a reader has a single opinion about; splitting it into its own text labels produces blocks that are individually meaningless.

**Elements that carry no reader-facing content SHALL be excluded from block candidacy and from text accumulation** — a document's own stylesheet, scripts, and document metadata are not passages, and a structural rule that does not exclude them will offer the reader the document's CSS as something to comment on.

#### Scenario: Content built from generic containers is annotatable

- **WHEN** a document expresses content in generic containers rather than prose tags
- **THEN** that content is still selectable and can carry an annotation

#### Scenario: Blocks do not nest

- **WHEN** the renderer divides a document into blocks
- **THEN** no block contains another block

#### Scenario: A document's own stylesheet is not offered as a passage

- **WHEN** a document embeds its own styles or scripts
- **THEN** those are not blocks and their text is not counted as document text

#### Scenario: A figure is one block rather than its own labels

- **WHEN** a document contains a vector figure whose internal structure is not prose
- **THEN** the whole figure is a single addressable block
- **AND** its internal text labels are not separately addressable

### Requirement: A block's recorded text is what the reader's browser reports

The text a renderer records for a block SHALL be identical to the text the reader's browser reports for that same block.

Both halves of the anchoring machinery depend on this and neither can detect its failure. The page captures a selection as an offset into the block's text; the renderer's later anchor check looks for the recorded passage in the block's text. When the two disagree about whitespace, about entity expansion, or about which nested content counts, the check reports an annotation lost against a document that has not changed — and a lost anchor is defined as evidence the document moved, so the report is not merely wrong, it is wrong in a way that is believed.

The equivalence SHALL be checked directly rather than assumed to follow from the parsing being correct.

#### Scenario: An anchor survives a rebuild of an unchanged document

- **WHEN** a document is annotated and then re-rendered without being edited
- **THEN** no annotation is reported as having lost its anchor

### Requirement: A block records the source line it came from, in every supported format

Every addressable block SHALL carry the line of the **source file** its text came from, whatever the document's format.

The recorded line is not for navigation on the page — the page can already scroll to the block it painted. It is for the session that reads the annotations back afterwards and has to make an edit, and an edit lands in the file. A format whose renderer records a position in the rendered page instead has recorded the one address that cannot be edited.

#### Scenario: An annotation points into the file

- **WHEN** an annotation is read back from the corpus
- **THEN** its recorded line identifies the line of the source document holding the annotated passage

### Requirement: An annotation layer shares no namespace with the document it annotates

A skill that renders its own interface around a document it did not write SHALL NOT place that interface in the same style or script namespace as the document.

The collision is not hypothetical and is not avoidable by choosing better names. A skill's interface needs a page container, a top bar, and a light/dark switch; so does any competently designed document, and both reach for the same short names for them. Measured on the motivating document, three of the skill's own names collide: the reading-grid class, the top-bar class, and the root theme attribute the skill's own toggle writes. Every one of those is the obvious name for what it does, on both sides.

**The consequence of a collision is silent and asymmetric.** Neither party errors. The document renders with the skill's spacing, or the skill's controls render with the document's, and the reader is looking at a hybrid neither author produced — while reviewing the design is part of what they were asked to do.

Isolation SHALL be structural rather than a naming convention. Prefixing the skill's own names removes today's three collisions and leaves the next document's collisions to be discovered by the reader.

**The isolation SHALL still permit the layer to address the document's content.** An isolation that also cuts off selection, block lookup and geometry has replaced a styling problem with a functional one; the mechanism chosen must keep the layer able to read the document it is annotating.

#### Scenario: A document defining the layer's own class names is unaffected

- **WHEN** an annotated document defines style rules for names the annotation layer also uses
- **THEN** the document renders as its author intended
- **AND** the annotation layer renders as the skill intended

#### Scenario: Selection still works across the isolation

- **WHEN** the reader selects a passage inside the isolated document
- **THEN** the annotation is captured against the correct block, with its offset and surrounding context

### Requirement: A rendering path shared by several formats is proven equivalent on the path that already worked

Where a change threads a new indirection through code that an existing format already depends on — a root, a handle, a context object that resolves to what was previously implicit — the change SHALL assert that the indirection resolves to the previous value on the existing path, as a check rather than as a claim in a comment.

This is the whole safety argument for touching working code, and it is the kind of claim that reads as obviously true and is cheap to get wrong. A refactor of this shape has one failure mode: the new path works, the old path is subtly rerouted, and the existing tests still pass because they were written against behaviour the indirection preserves in the common case and not in the one that matters.

#### Scenario: The pre-existing format's behaviour is unchanged

- **WHEN** a document in the format that worked before the change is rendered and annotated
- **THEN** its rendering, its anchors and its corpus are unchanged by the change
