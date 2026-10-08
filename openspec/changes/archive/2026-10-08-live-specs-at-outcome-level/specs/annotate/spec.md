## REMOVED Requirements

### Requirement: A document is shown as its author designed it

**Reason**: Restated at outcome level under a new heading.

**Migration**: See annotate / The document is shown as written and never changed.

### Requirement: The skill adds markup to a copy and changes nothing else

**Reason**: Restated at outcome level under a new heading.

**Migration**: See annotate / The document is shown as written and never changed.

### Requirement: A document already using the skill's attributes is refused

**Reason**: Restated at outcome level under a new heading.

**Migration**: See annotate / A document using the page's own attributes is refused.

### Requirement: Annotatable blocks are chosen by structure, not by a fixed tag list

**Reason**: Describes how the plugin's skills work internally, not an outcome or interface.

**Migration**: None; the rule stays in the skill's own files and tests.

### Requirement: A block's recorded text matches what the browser reports

**Reason**: Restated at outcome level under a new heading.

**Migration**: See annotate / Existing comments are reported when the page is rebuilt.

### Requirement: A block records the source line it came from, in every supported format

**Reason**: Restated at outcome level under a new heading.

**Migration**: See annotate / Comments are saved with their source line.

### Requirement: The annotation interface is isolated from the document's styles and scripts

**Reason**: Restated at outcome level under a new heading.

**Migration**: See annotate / The document is shown as written and never changed.

### Requirement: A change to a rendering path shared by several formats proves the existing format is unchanged

**Reason**: Describes how the plugin's skills work internally, not an outcome or interface.

**Migration**: None; the rule stays in the skill's own files and tests.

## ADDED Requirements

### Requirement: Opening a document for annotation

`/cla:annotate <path or change id>` SHALL open a Markdown, plain-text or HTML document, or every file of an OpenSpec change on one page, in a browser page served only on the local machine, where the reader selects passages and comments on them.

#### Scenario: A Markdown document

- **WHEN** a user runs `/cla:annotate docs/spec.md`
- **THEN** a local page shows the document and lets the reader select a passage and comment on it

#### Scenario: An OpenSpec change

- **WHEN** a user runs `/cla:annotate` with a change id
- **THEN** the change's files open together on one page

### Requirement: The document is shown as written and never changed

Annotating SHALL never change the source document and SHALL show an HTML document with its own styling and layout, adding only the annotation layer, and telling the reader when a document cannot be shown that way.

#### Scenario: The source after annotating

- **WHEN** a reader annotates a document and the page is rebuilt
- **THEN** the source file is byte for byte what it was

#### Scenario: A designed HTML document

- **WHEN** a reader annotates an HTML document with its own styles, including names the annotation layer also uses
- **THEN** it looks as its author designed it, and passages can still be selected and commented on

### Requirement: A document using the page's own attributes is refused

An HTML document that already uses an attribute the annotation page adds SHALL be refused, with the element and attribute named, and no page SHALL be produced for it.

#### Scenario: A clashing attribute

- **WHEN** an HTML document already carries one of the page's own attributes on an element
- **THEN** no page is produced and the reader is told which element and attribute clash

### Requirement: Comments are saved with their source line

Each comment SHALL be saved as it is made to `cla.io/annotations/<document path>.jsonl`, with the selected text, the comment, the source line and, for a change, the file it came from, and that file SHALL only grow, recording edits, retractions and resolutions as new lines.

#### Scenario: Reading a comment back

- **WHEN** a saved comment is read back
- **THEN** its line is the line of the source file holding the passage

#### Scenario: Retracting a comment

- **WHEN** a reader deletes a comment
- **THEN** it leaves the page and the file keeps the original line plus a new line marking it retracted

### Requirement: Existing comments are reported when the page is rebuilt

Rendering a document that already has comments SHALL report how many are open and resolved and name each one whose passage the document no longer contains.

#### Scenario: An edit removes a commented passage

- **WHEN** the document is edited so a commented passage is gone and the page is rebuilt
- **THEN** that comment is reported as no longer found

#### Scenario: An unchanged document

- **WHEN** an unchanged document is rebuilt
- **THEN** no comment is reported as lost
