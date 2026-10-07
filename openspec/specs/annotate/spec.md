# annotate Specification

## Purpose

How the `annotate` skill presents a reader's own document for marking up: instrumentation that is additive and reversible, how annotatable blocks are chosen and anchored to source lines across formats, and how the annotation layer stays out of the document's namespace. The reasoning and measurements behind each requirement are
in `rationale.md`, under the same heading.

## Requirements

### Requirement: A document that carries its own presentation is annotated as presented

Where a document carries its own presentation, a skill that puts it in front of a reader to be
marked up SHALL present it as its author wrote it, and SHALL NOT present an extraction as the
document. A format with no presentation of its own, such as plain text or a markup the skill
renders, uses the skill's rendering.

#### Scenario: A designed document opens as designed

- **WHEN** the reader annotates a document that carries its own styling and layout
- **THEN** the document is shown with that styling and layout intact
- **AND** the annotation surfaces — the selection affordance, the margin, the drawer — are available over it

#### Scenario: A format with no presentation of its own is unaffected

- **WHEN** the reader annotates a plain-text or Markdown document
- **THEN** the skill's own rendering is used, exactly as before this change

### Requirement: A presentation that cannot be honoured is reported

Where the renderer cannot present a document as authored, the skill SHALL say so, with the reason,
rather than degrade quietly, so the reader knows which of the two they are looking at.

#### Scenario: A presentation that cannot be honoured is reported, not silently degraded

- **WHEN** the renderer cannot present a document as its author wrote it
- **THEN** the reader is told which of the two they are looking at, and why
- **AND** the page does not render as though nothing were wrong

### Requirement: Instrumentation of a reader's document is additive and reversible

Instrumentation of a document a skill did not write (identifiers that bind an annotation to a
passage) SHALL be additive only: attributes on markup already there, plus at most the presentation
the annotation layer needs to be visible, and nothing else about the file's bytes. That presentation
SHALL be enumerable, appended rather than interleaved, and self-contained. Removing everything added SHALL yield the original input byte for byte, and the
skill SHALL carry a test that checks exactly that.

#### Scenario: The injected attributes strip back to the original

- **WHEN** the instrumented output has its injected attributes removed
- **THEN** the result is byte-identical to the source document

### Requirement: The source document is never written to

The instrumented copy SHALL be a separate artifact in working storage. Rendering SHALL NOT write
to the source document, not even to modify it and undo the change.

#### Scenario: The source document is unchanged by rendering

- **WHEN** a document is rendered for annotation
- **THEN** the source file's contents are unchanged

### Requirement: A document already using the instrumentation's identifiers is refused

Where the document already uses an identifier the instrumentation would add, the renderer SHALL
refuse it, naming the offending element, rather than emit a page.

#### Scenario: A document already using the instrumentation's own attributes is refused

- **WHEN** the document already carries an attribute the instrumentation would add
- **THEN** the renderer refuses the document and names the offending element
- **AND** it does not emit a page whose annotations would anchor to the author's value

### Requirement: An annotatable block is chosen by structure, not by a fixed tag list

A renderer that divides a document into addressable blocks SHALL choose them by a structural rule,
and SHALL NOT rely on a fixed list of the tags that usually hold prose.

#### Scenario: Content built from generic containers is annotatable

- **WHEN** a document expresses content in generic containers rather than prose tags
- **THEN** that content is still selectable and can carry an annotation

### Requirement: Annotatable blocks are disjoint

The structural rule SHALL select the innermost element that holds text and is not purely inline,
so that no block contains another.

#### Scenario: Blocks do not nest

- **WHEN** the renderer divides a document into blocks
- **THEN** no block contains another block

### Requirement: Elements with no reader-facing content are not blocks

Elements that carry no reader-facing content, such as the document's own stylesheet, scripts and
metadata, SHALL be excluded from block candidacy and from text accumulation.

#### Scenario: A document's own stylesheet is not offered as a passage

- **WHEN** a document embeds its own styles or scripts
- **THEN** those are not blocks and their text is not counted as document text

### Requirement: A subtree that is not prose is one block

A subtree whose internal structure is not prose, such as a vector figure, SHALL be treated as one
block rather than divided.

#### Scenario: A figure is one block rather than its own labels

- **WHEN** a document contains a vector figure whose internal structure is not prose
- **THEN** the whole figure is a single addressable block
- **AND** its internal text labels are not separately addressable

### Requirement: A block's recorded text is what the reader's browser reports

The text a renderer records for a block SHALL be identical to the text the reader's browser reports
for that same block. The equivalence SHALL be checked directly rather than assumed to follow from
the parsing being correct.

#### Scenario: An anchor survives a rebuild of an unchanged document

- **WHEN** a document is annotated and then re-rendered without being edited
- **THEN** no annotation is reported as having lost its anchor

### Requirement: A block records the source line it came from, in every supported format

Every addressable block SHALL carry the line of the **source file** its text came from, whatever the
document's format.

#### Scenario: An annotation points into the file

- **WHEN** an annotation is read back from the corpus
- **THEN** its recorded line identifies the line of the source document holding the annotated passage

### Requirement: An annotation layer shares no namespace with the document it annotates

A skill that renders its own interface around a document it did not write SHALL NOT place that
interface in the same style or script namespace as the document. Isolation SHALL be structural
rather than a naming convention.

#### Scenario: A document defining the layer's own class names is unaffected

- **WHEN** an annotated document defines style rules for names the annotation layer also uses
- **THEN** the document renders as its author intended
- **AND** the annotation layer renders as the skill intended

### Requirement: The isolation still lets the layer address the document

The isolation SHALL still permit the annotation layer to address the document's content: selection,
block lookup and geometry.

#### Scenario: Selection still works across the isolation

- **WHEN** the reader selects a passage inside the isolated document
- **THEN** the annotation is captured against the correct block, with its offset and surrounding context

### Requirement: A rendering path shared by several formats is proven equivalent on the path that already worked

Where a change threads a new indirection (a root, a handle, a context object) through code an
existing format already depends on, the change SHALL assert, as a check rather than a claim in a
comment, that the indirection resolves to the previous value on the existing path.

#### Scenario: The pre-existing format's behaviour is unchanged

- **WHEN** a document in the format that worked before the change is rendered and annotated
- **THEN** its rendering, its anchors and its corpus are unchanged by the change
