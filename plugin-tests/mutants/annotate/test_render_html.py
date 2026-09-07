"""Mutants for the HTML instrumenter: the block rule, the two refusals, the
predicate, and the splice.

What is mutated is what the change TOUCHED rather than only what it targeted.
The block rule's *disqualification condition* gets three mutants of its own,
because that is the line the design got wrong twice — once in the phrasing
("no non-inline descendant", which kills the waterfall) and once in the
recursion (returning "I am a block" instead of "my subtree holds one", which
made 348 of 349 blocks nest).

    python3 plugin-tests/mutate.py plugin-tests/mutants/annotate/test_render_html.py
"""
from pathlib import Path

DEV = Path(__file__).resolve().parents[2]                 # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
DOC = PLUGIN / "skills" / "annotate" / "scripts" / "render_html.py"
TESTS = [DEV / "tests" / "skills" / "annotate" / "test_render_html.py"]

MUTANTS = [
    # ---- the block rule's disqualification condition ----
    ("the recursion reports 'I am a block' rather than 'my subtree holds one', "
     "so every ancestor re-qualifies and the blocks nest",
     DOC,
     "        return True\n    if node.tag not in INLINE and node.parent is not None and has_text(node):",
     "        return False\n    if node.tag not in INLINE and node.parent is not None and has_text(node):",
     TESTS),

    ("candidacy stops requiring text, so an empty layout div becomes a block "
     "and the row that contains it is disqualified",
     DOC,
     "    if node.tag not in INLINE and node.parent is not None and has_text(node):",
     "    if node.tag not in INLINE and node.parent is not None:",
     TESTS),

    ("an inline element can become a block, so a <span> inside a row splits it",
     DOC,
     "    if node.tag not in INLINE and node.parent is not None and has_text(node):",
     "    if node.parent is not None and has_text(node):",
     TESTS),

    # ---- opaque vs excluded ----
    ("an opaque subtree is descended into, so a figure becomes its own labels",
     DOC,
     "    if node.tag in OPAQUE:\n        if has_text(node):\n            out.append(node)\n            return True\n        return False",
     "    if node.tag in OPAQUE:\n        return False",
     TESTS),

    ("math/canvas/object go back to being excluded outright, losing content "
     "that is itself what the reader is judging",
     DOC,
     'OPAQUE = frozenset("svg math canvas object".split())',
     'OPAQUE = frozenset("svg".split())',
     TESTS),

    ("the excluded set is matched by prefix, so <header> is swallowed by the "
     "`head` entry and the masthead disappears",
     DOC,
     "    if node.tag in EXCLUDED:\n        return False",
     "    if any(node.tag.startswith(x) for x in EXCLUDED):\n        return False",
     TESTS),

    ("a document's own stylesheet becomes the largest block on the page",
     DOC,
     'script style head title meta link template noscript base iframe',
     'head title meta link template noscript base iframe',
     TESTS),

    # ---- void elements ----
    ("a void element opens a scope, so everything after a <br> nests inside it",
     DOC,
     "        if tag not in VOID:\n            self.cur = n",
     "        self.cur = n",
     TESTS),

    # ---- block text vs the browser's textContent ----
    ("block text is whitespace-normalised, so a selection the page captures "
     "verbatim no longer matches and reports itself lost",
     DOC,
     '    return "".join(out)',
     '    return " ".join("".join(out).split())',
     TESTS),

    ("an excluded subtree contributes its text to the enclosing block",
     DOC,
     "            if k.tag not in EXCLUDED:\n                out.append(text_of(k))",
     "            out.append(text_of(k))",
     TESTS),

    # ---- the refusals ----
    ("an author's own data-blk is overwritten instead of refused, so every "
     "annotation in that element anchors to their value",
     DOC,
     "    if clashes:",
     "    if False:",
     TESTS),

    ("only data-blk is treated as a collision, so data-line and data-sec "
     "collide silently",
     DOC,
     'OURS = ("data-blk", "data-line", "data-sec", "data-sec-id")',
     'OURS = ("data-blk",)',
     TESTS),

    # ---- the relative-asset predicate ----
    ("the predicate loses its exemptions, so an in-page anchor, a mail link "
     "and inline data all report the document as not self-contained",
     DOC,
     '_NOT_RELATIVE = ("#", "//", "data:", "mailto:", "tel:", "javascript:")',
     '_NOT_RELATIVE = ()',
     TESTS),

    ("a scheme no longer counts as absolute, so every https:// reference "
     "reports as relative",
     DOC,
     "            if v.startswith(_NOT_RELATIVE) or _SCHEME.match(v):",
     "            if v.startswith(_NOT_RELATIVE):",
     TESTS),

    # ---- the splice and the reversibility property ----
    ("edits are applied first-to-last, so every splice after the first lands "
     "at an offset the previous one already shifted",
     DOC,
     "    for offset, text in sorted(edits, reverse=True):",
     "    for offset, text in sorted(edits):",
     TESTS),

    ("the marker stylesheet is prepended rather than appended, shifting every "
     "data-line the instrumentation just recorded",
     DOC,
     '    out = out + "\\n" + MARK_OPEN + MARKER_CSS + MARK_CLOSE + "\\n"',
     '    out = MARK_OPEN + MARKER_CSS + MARK_CLOSE + "\\n" + out',
     TESTS),

    ("strip() stops removing the stylesheet, so the round-trip property is "
     "asserted against a document that still carries it",
     DOC,
     "    if instrumented.endswith(tail):\n        instrumented = instrumented[:-len(tail)]",
     "    pass",
     TESTS),

    ("the marker stylesheet goes back to var() references, which resolve to "
     "nothing across a frame boundary and paint the markers invisible",
     DOC,
     "[data-cla-mark].cmt-hl{background:#F1DFD4;",
     "[data-cla-mark].cmt-hl{background:var(--mark-wash);",
     TESTS),

    # ---- sections ----
    ("a heading no longer opens a section, so the rail has nothing to show",
     DOC,
     "        if node.tag in HEADINGS:",
     "        if False:",
     TESTS),

    # ---- PR review round 1 ----

    ("the collision scan stops recursing, so a data-blk nested inside a "
     "<section> is never seen and the document instruments with wrong anchors",
     DOC,
     "                found.append((k.tag, token, k.line))\n        attribute_collisions(k, found)",
     "                found.append((k.tag, token, k.line))",
     TESTS),

    ("the relative-asset scan stops recursing, so an <img> inside a <figure> "
     "never reports the document as not self-contained",
     DOC,
     "            found.append((k.tag, attr, v))\n        relative_refs(k, found)",
     "            found.append((k.tag, attr, v))",
     TESTS),

    ("bare text sitting beside a block goes back to being dropped silently",
     DOC,
     "            elif k.strip() and stranded is not None:",
     "            elif False:",
     TESTS),

    ("an inline element beside a block is no longer promoted, so a callout "
     "label becomes unannotatable with nothing reporting it",
     DOC,
     "                elif k.tag not in EXCLUDED and has_text(k):",
     "                elif False:",
     TESTS),

    ("an EXCLUDED element beside a block is promoted, so a stylesheet becomes "
     "an annotatable passage",
     DOC,
     "                elif k.tag not in EXCLUDED and has_text(k):",
     "                elif has_text(k):",
     TESTS),

    ("an empty inline beside a block is promoted, so a layout span becomes a "
     "block with no text in it",
     DOC,
     "                elif k.tag not in EXCLUDED and has_text(k):",
     "                elif k.tag not in EXCLUDED:",
     TESTS),

    ("promoted inlines are emitted after their siblings instead of in document "
     "order, so the block numbering stops following reading order",
     DOC,
     "        for k in node.kids:\n            if isinstance(k, Node):\n                got = sub.get(id(k))\n                if got:\n                    out.extend(got)",
     "        for k in node.kids:\n            if isinstance(k, Node):\n                got = sub.get(id(k))\n                if got:\n                    out[:0] = got",
     TESTS),

    ("a document with nothing annotatable reports success",
     DOC,
     "    if not blocks:",
     "    if False:",
     TESTS),

    ("the reversibility property goes back to being the CLI's problem, so a "
     "library caller gets no guarantee at all",
     DOC,
     "    if strip(out) != src:\n        raise Refused(",
     "    if False:\n        raise Refused(",
     TESTS),

    ("an unclosed <p> nests instead of closing, so the outer paragraph's own "
     "text belongs to no block",
     DOC,
     "    def handle_starttag(self, tag, attrs):\n        self._implicit_close(tag)",
     "    def handle_starttag(self, tag, attrs):",
     TESTS),

    ("implicit closing unwinds past elements that cannot be implicitly closed, "
     "so a <p> inside a <div> inside a <p> closes the outer paragraph",
     DOC,
     "        while n is not self.root and n.tag in closes:",
     "        while n is not self.root and n.tag not in EXCLUDED:",
     TESTS),

    ("a block-level element stops closing an open paragraph",
     DOC,
     "        if tag in CLOSES_P:\n            closes = closes | {\"p\"}",
     "        if False:\n            closes = closes | {\"p\"}",
     TESTS),

    ("an empty src goes back to being indistinguishable from no src",
     DOC,
     '                if attr == "src":\n                    found.append((k.tag, attr, ""))',
     "                pass",
     TESTS),

    ("the text-collision scan only looks at <style>, so the same token in a "
     "<script> goes unreported",
     DOC,
     '        if self.cur.tag in ("style", "script"):',
     '        if self.cur.tag in ("style",):',
     TESTS),
]
