# annotate — rationale

Why each requirement in `spec.md` exists. The spec states the behaviour; this file keeps the
evidence and reasoning behind it, moved out when the requirements were compacted (#293) and edited
only so each section reads on its own. Headings name the requirement each section explains.

## A document that carries its own presentation is annotated as presented

The reason is what the reader is being asked to judge. Where a document's layout, typography, tables and figures are part of the artifact under review, a rendering that keeps only the words has discarded half of what was submitted — and it does so silently, because the extracted page is perfectly readable and gives no sign that anything is missing.

The obligation binds only where the presentation is the document's own. A format with no presentation of its own — plain text, or a markup the skill itself renders — has nothing to preserve, and the skill's rendering IS the presentation there.

## Instrumentation of a reader's document is additive and reversible

A transform that rewrites, normalises, reformats or re-serialises the document has changed the artifact under review into a different artifact, and the reader would be annotating the skill's opinion of their document rather than their document.

The byte-for-byte property is also what makes the presentation obligation checkable. "The page looks the same" is a judgement; "the bytes outside the injected attributes are identical" is a measurement, and it is the one that catches a renderer quietly normalising an author's markup.

## The annotation layer's own presentation is enumerable, appended, and self-contained

Enumerable, so the reversibility check can subtract it. Appended, so it shifts no position the instrumentation has already recorded for the content above it. Self-contained, because it is the one thing that crosses the isolation boundary between the layer and the document (see "An annotation layer shares no namespace with the document it annotates") — anything it inherits from the other side of that boundary resolves to nothing, and does so silently.

## A document already using the instrumentation's identifiers is refused

Additive instrumentation assumes the identifiers it adds are its own. Where they are not, the collision does not announce itself: the markup language's own rule for a repeated identifier decides which value wins, and every later lookup silently resolves to the author's. An annotation then anchors to whatever their value named, and nothing on the page looks wrong. This is the one case where refusing beats rendering, because the defect it prevents is invisible to the reader and they would have no reason to doubt what they were shown.

## An annotatable block is chosen by structure, not by a fixed tag list

**A tag allowlist fails in the direction that is hardest to notice.** Content the author built out of generic containers — a chart row, a stat tile, a figure caption in a wrapper — is not a paragraph and not a list item, so an allowlist silently makes it unannotatable. The reader sees a document where some passages accept a comment and others do not, with no rule they can infer. Measured on the motivating document: a paragraph-and-list-item rule leaves its entire waterfall chart, built from generic containers holding inline spans, outside every block.

## Annotatable blocks are disjoint

Disjointness is not cosmetic: the anchor check, the word count and the "which block did this selection start in" lookup all assume a passage belongs to exactly one block, and nested blocks make each of those ambiguous.

## Elements with no reader-facing content are not blocks

A document's own stylesheet, scripts, and document metadata are not passages, and a structural rule that does not exclude them will offer the reader the document's CSS as something to comment on.

## A subtree that is not prose is one block

A vector figure is a single thing a reader has a single opinion about; splitting it into its own text labels produces blocks that are individually meaningless.

## A block's recorded text is what the reader's browser reports

Both halves of the anchoring machinery depend on this and neither can detect its failure. The page captures a selection as an offset into the block's text; the renderer's later anchor check looks for the recorded passage in the block's text. When the two disagree about whitespace, about entity expansion, or about which nested content counts, the check reports an annotation lost against a document that has not changed — and a lost anchor is defined as evidence the document moved, so the report is not merely wrong, it is wrong in a way that is believed.

## A block records the source line it came from, in every supported format

The recorded line is not for navigation on the page — the page can already scroll to the block it painted. It is for the session that reads the annotations back afterwards and has to make an edit, and an edit lands in the file. A format whose renderer records a position in the rendered page instead has recorded the one address that cannot be edited.

## An annotation layer shares no namespace with the document it annotates

The collision is not hypothetical and is not avoidable by choosing better names. A skill's interface needs a page container, a top bar, and a light/dark switch; so does any competently designed document, and both reach for the same short names for them. Measured on the motivating document, three of the skill's own names collide: the reading-grid class, the top-bar class, and the root theme attribute the skill's own toggle writes. Every one of those is the obvious name for what it does, on both sides.

**The consequence of a collision is silent and asymmetric.** Neither party errors. The document renders with the skill's spacing, or the skill's controls render with the document's, and the reader is looking at a hybrid neither author produced — while reviewing the design is part of what they were asked to do.

Prefixing the skill's own names removes today's three collisions and leaves the next document's collisions to be discovered by the reader.

## The isolation still lets the layer address the document

An isolation that also cuts off selection, block lookup and geometry has replaced a styling problem with a functional one.

## A rendering path shared by several formats is proven equivalent on the path that already worked

This is the whole safety argument for touching working code, and it is the kind of claim that reads as obviously true and is cheap to get wrong. A refactor of this shape has one failure mode: the new path works, the old path is subtly rerouted, and the existing tests still pass because they were written against behaviour the indirection preserves in the common case and not in the one that matters.
