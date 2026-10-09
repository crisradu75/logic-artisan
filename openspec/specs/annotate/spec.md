# annotate Specification

## Purpose

What `/cla:annotate` promises a reader: their document shown as written on a local page, comments saved beside the repo with the source line they point at, and the source never changed.

## Requirements

### Requirement: Opening a document for annotation

`/cla:annotate <path or change id>` SHALL open a Markdown, plain-text or HTML document, or every file of an OpenSpec change on one page, in a browser page served only on the local machine, where the reader selects passages and comments on them.

#### Scenario: A Markdown document

- **WHEN** a user runs `/cla:annotate docs/spec.md`
- **THEN** a local page shows the document and lets the reader select a passage and comment on it

#### Scenario: An OpenSpec change

- **WHEN** a user runs `/cla:annotate` with a change id
- **THEN** the change's files open together on one page

#### Scenario: A change opens on its overview

- **WHEN** a change's page opens
- **THEN** it first shows an overview of the change: what it promises, the requirements it adds, modifies or removes, and how many tasks are done

### Requirement: Reviewing a change shows how each requirement changes the current spec

On a change's page, each requirement in its spec changes SHALL say whether it is added, modified or removed, a modified one SHALL show the words it changes in the current spec, a removed one SHALL be set apart from the live ones, and where there is no current text to compare against the page SHALL say so rather than show the requirement as unchanged.

#### Scenario: A modified requirement

- **WHEN** a change modifies a requirement whose current text differs
- **THEN** the words it removes and adds are shown under its heading

#### Scenario: An archived change

- **WHEN** the change has been archived
- **THEN** each modified requirement says there is no current text to compare it with, not that it is unchanged

#### Scenario: A removed requirement

- **WHEN** a change removes a requirement
- **THEN** its heading is labelled removed and its text is set apart from the live requirements, with its reason still readable

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
