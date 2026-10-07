# annotate Specification

## Purpose

How the `annotate` skill shows a reader their own document for marking up: the document is shown as written, the markup the skill adds can be removed exactly, and every annotation points back to a line of the source file.

## Requirements

### Requirement: A document is shown as its author designed it

Where a document carries its own styling and layout, the skill SHALL show it that way rather than in the skill's own rendering, and SHALL NOT present extracted text as the document. A format with no presentation of its own, such as plain text or Markdown, uses the skill's rendering. Where the renderer cannot show a document as designed, the skill SHALL tell the reader so, and why.

#### Scenario: A designed document opens as designed

- **WHEN** the reader annotates a document that carries its own styling and layout
- **THEN** the document is shown with that styling and layout intact
- **AND** the selection, margin and drawer for annotating are available over it

#### Scenario: A format with no presentation of its own is unaffected

- **WHEN** the reader annotates a plain-text or Markdown document
- **THEN** the skill's own rendering is used

#### Scenario: A presentation that cannot be honoured is reported, not silently degraded

- **WHEN** the renderer cannot show a document as its author wrote it
- **THEN** the reader is told which of the two they are looking at, and why
- **AND** the page does not render as though nothing were wrong

### Requirement: The skill adds markup to a copy and changes nothing else

The skill SHALL never write to the source document; it instruments a separate copy. In that copy it SHALL only add attributes to existing elements, plus its own presentation appended after the document's content and depending on nothing outside itself. Removing everything it added SHALL give back the source byte for byte, and a test SHALL check this.

#### Scenario: The injected attributes strip back to the original

- **WHEN** the instrumented output has its added attributes removed
- **THEN** the result is byte-identical to the source document

#### Scenario: The layer's own presentation is appended and strips back

- **WHEN** a document is instrumented for annotation
- **THEN** the presentation the layer adds for itself is appended after every instrumented block and depends on nothing defined outside it
- **AND** removing the attributes and that presentation yields the source document byte for byte

#### Scenario: The source document is unchanged by rendering

- **WHEN** a document is rendered for annotation
- **THEN** the source file's contents are unchanged

### Requirement: A document already using the skill's attributes is refused

Where the document already uses an attribute the skill would add, the renderer SHALL refuse it and name the element, rather than emit a page whose annotations would attach to the author's value.

#### Scenario: A document already using the instrumentation's own attributes is refused

- **WHEN** the document already carries an attribute the skill would add
- **THEN** the renderer refuses the document and names the offending element
- **AND** it emits no page

### Requirement: Annotatable blocks are chosen by structure, not by a fixed tag list

The renderer SHALL choose blocks by a structural rule, not a fixed list of prose tags:

- a block is the innermost element that holds text and is not purely inline, so no block contains another;
- elements with no reader-facing content, such as the document's own styles, scripts and metadata, are never blocks and their text is not counted;
- a subtree that is not prose, such as a vector figure, is one block.

#### Scenario: Content built from generic containers is annotatable

- **WHEN** a document puts content in generic containers rather than prose tags
- **THEN** that content can still be selected and annotated

#### Scenario: Blocks do not nest

- **WHEN** the renderer divides a document into blocks
- **THEN** no block contains another block

#### Scenario: A document's own stylesheet is not offered as a passage

- **WHEN** a document embeds its own styles or scripts
- **THEN** those are not blocks and their text is not counted as document text

#### Scenario: A figure is one block rather than its own labels

- **WHEN** a document contains a vector figure
- **THEN** the whole figure is one block
- **AND** its text labels cannot be annotated separately

### Requirement: A block's recorded text matches what the browser reports

The text the renderer records for a block SHALL be identical to the text the reader's browser reports for that block, and this SHALL be checked directly rather than assumed.

#### Scenario: An anchor survives a rebuild of an unchanged document

- **WHEN** a document is annotated and then re-rendered without being edited
- **THEN** no annotation is reported as having lost its place

### Requirement: A block records the source line it came from, in every supported format

Every block SHALL record the line of the source file its text came from, whatever the document's format.

#### Scenario: An annotation points into the file

- **WHEN** an annotation is read back from the saved annotations
- **THEN** its recorded line is the line of the source document holding the annotated passage

### Requirement: The annotation interface is isolated from the document's styles and scripts

The skill SHALL NOT place its own interface in the same style or script namespace as the document, and SHALL isolate them by structure rather than by naming. The isolation SHALL still let the interface read and select the document's content.

#### Scenario: A document defining the layer's own class names is unaffected

- **WHEN** an annotated document defines style rules for names the skill's interface also uses
- **THEN** the document renders as its author intended
- **AND** the interface renders as the skill intended

#### Scenario: Selection still works across the isolation

- **WHEN** the reader selects a passage inside the isolated document
- **THEN** the annotation is captured against the correct block, with its offset and surrounding text

### Requirement: A change to a rendering path shared by several formats proves the existing format is unchanged

Where a change passes a new shared value (a root element, a handle, a context object) through code an existing format already uses, the change SHALL check, in a test rather than a comment, that the value equals the previous one on the existing path.

#### Scenario: The pre-existing format's behaviour is unchanged

- **WHEN** a document in the format that worked before the change is rendered and annotated
- **THEN** its rendering, its anchors and its saved annotations are unchanged by the change
