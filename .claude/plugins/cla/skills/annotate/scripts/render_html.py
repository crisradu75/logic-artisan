"""Instrument an author's own HTML document so its passages can be annotated.

The document is NOT rebuilt. This module locates start tags with `html.parser`
and edits the original text at their source offsets, so everything outside the
injected attributes survives byte for byte — the property `strip()` below exists
to prove, and the reason a parse-and-re-serialise implementation was rejected: it
would normalise attribute quoting, drop the author's whitespace, close tags they
left implicit and re-encode entities, turning the artifact under review into a
different artifact while looking fine.

The one exception is the marker stylesheet, appended at the very end. The
annotation markers are painted INTO this document, and the shell's stylesheet
does not cross a frame boundary — without it every highlight and superscript
renders unstyled. `strip()` subtracts it too.
"""

import html as _html
import io
import os
import re
import sys
from html.parser import HTMLParser

# Elements that are purely inline: they never become a block on their own, and a
# block containing only these is still a leaf.
INLINE = frozenset("""
    a abbr b bdi bdo br cite code data del dfn em i img ins kbd mark q rp rt ruby
    s samp small span strong sub sup time u var wbr
""".split())

# One block each, never divided. These hold genuine reader-facing content that a
# reader has a single opinion about: MathML IS the equation, <canvas> fallback
# content between the tags is standard practice, and <object> can embed a whole
# document. Splitting a figure into its own axis labels produces blocks nobody
# has an opinion about.
OPAQUE = frozenset("svg math canvas object".split())

# No block, and no text. Each is verified rather than assumed: <title> is the tab
# label, <noscript> renders only with scripting off (which the annotation layer
# requires anyway), <template> is inert by definition, <iframe> has no text of
# its own, and the rest carry no reader-facing content at all.
EXCLUDED = frozenset("""
    script style head title meta link template noscript base iframe
""".split())

# Void elements never open a scope. HTMLParser reports them through
# handle_starttag with no matching handle_endtag, so a tree builder that pushes
# them corrupts every nesting decision that follows.
VOID = frozenset("""
    area base br col embed hr img input link meta param source track wbr
""".split())

HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")

# The attributes this module adds. Also the collision set: an author already
# using one of these is refused, because a repeated attribute resolves to THEIR
# value and every later lookup silently anchors to whatever it named.
OURS = ("data-blk", "data-line", "data-sec", "data-sec-id")

# A reference is relative when it has no scheme and does not begin with one of
# these. The naive "not absolute" test fires on in-page anchors, mail links and
# inline data, which are universal in designed documents — a check that warns on
# almost every real file is a check nobody reads.
_NOT_RELATIVE = ("#", "//", "data:", "mailto:", "tel:", "javascript:")
_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")

MARK_OPEN = '<style data-cla-marks>'
MARK_CLOSE = '</style>'

# Literal values, never var(): the shell's custom properties are defined on ITS
# :root and do not inherit across a frame boundary, so a var() reference here
# resolves to nothing and fails the same way silently. Selected by
# [data-cla-mark] rather than by class, because an author may plausibly have
# defined .cmt-sup and nobody has defined data-cla-mark. Both themes are carried
# here via prefers-color-scheme, because the shell's :root[data-theme] does not
# cross either — a real limitation: markers follow the system theme while the
# shell follows the reader's toggle, and the two can disagree.
MARKER_CSS = """
[data-cla-mark].cmt-hl{background:#F1DFD4;box-shadow:0 0 0 2px #F1DFD4;
 border-radius:1px;border-bottom:1px solid #9E4718;color:inherit}
[data-cla-mark].cmt-sup{display:inline-flex;align-items:center;
 vertical-align:baseline;margin:0 .12rem 0 .18rem;white-space:nowrap}
[data-cla-mark] .cmt-num,[data-cla-mark] .cmt-x{
 font-family:ui-monospace,Menlo,Consolas,monospace;cursor:pointer;
 border:1px solid #9E4718;background:#F1DFD4;color:#9E4718;
 font-variant-numeric:tabular-nums;line-height:1;padding:0;
 display:inline-flex;align-items:center;justify-content:center;height:1.2rem}
[data-cla-mark] .cmt-num{font-size:.69rem;min-width:1.25rem;border-radius:2px}
[data-cla-mark] .cmt-x{font-size:.8rem;width:0;min-width:0;opacity:0;
 overflow:hidden;border-left:0;border-radius:0 2px 2px 0}
[data-cla-mark]:hover .cmt-x,[data-cla-mark]:focus-within .cmt-x{
 opacity:1;width:1.2rem}
@media (prefers-color-scheme: dark){
 [data-cla-mark].cmt-hl{background:#291A11;box-shadow:0 0 0 2px #291A11;
  border-bottom-color:#E0915E}
 [data-cla-mark] .cmt-num,[data-cla-mark] .cmt-x{
  border-color:#E0915E;background:#291A11;color:#E0915E}
}
"""


class Refused(Exception):
    """The document cannot be instrumented without silently corrupting it."""


def use_utf8_stdout():
    """Diagnostics print block text, and on Windows `sys.stdout` is the locale
    codepage — printing a document containing `−` or `ț` raises UnicodeEncodeError
    and takes the run down. POSIX is fine throughout, which is what makes this
    dangerous in a repo with no CI."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


class Node(object):
    __slots__ = ("tag", "line", "kids", "parent", "attrs", "tag_end")

    def __init__(self, tag, line, parent, attrs=(), tag_end=None):
        self.tag = tag
        self.line = line
        self.parent = parent
        self.attrs = dict(attrs)
        # Absolute source offset of the '>' closing this element's start tag.
        # The splice happens here, which is why nothing else in the file moves.
        self.tag_end = tag_end
        self.kids = []          # mixed: Node objects and str (text nodes)


class _Tree(HTMLParser):
    def __init__(self, src):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.src = src
        # Line starts, so (lineno, col) from getpos() becomes an absolute offset.
        self._line_start = [0]
        for i, ch in enumerate(src):
            if ch == "\n":
                self._line_start.append(i + 1)
        self.root = Node("#root", 0, None)
        self.cur = self.root
        self.text_collisions = []

    def _offset(self):
        line, col = self.getpos()
        return self._line_start[line - 1] + col

    def _open(self, tag, attrs):
        raw = self.get_starttag_text() or ""
        start = self._offset()
        n = Node(tag, self.getpos()[0], self.cur, attrs,
                 tag_end=start + len(raw) - 1)
        self.cur.kids.append(n)
        return n

    def handle_starttag(self, tag, attrs):
        n = self._open(tag, attrs)
        if tag not in VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self._open(tag, attrs)

    def handle_endtag(self, tag):
        # Walk up to the nearest matching open element. A stray close tag that
        # matches nothing is ignored rather than unwinding the whole tree, which
        # is what a browser does with the same input.
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        if self.cur.tag in ("style", "script"):
            for token in OURS:
                if token in data:
                    self.text_collisions.append((self.cur.tag, token))
        self.cur.kids.append(data)


def _elements(node):
    return [k for k in node.kids if isinstance(k, Node)]


def has_text(node):
    """Whether this subtree holds any non-whitespace text, ignoring the parts
    that carry no reader-facing content."""
    for k in node.kids:
        if isinstance(k, Node):
            if k.tag not in EXCLUDED and has_text(k):
                return True
        elif k.strip():
            return True
    return False


def text_of(node):
    """The subtree's text as the browser's `textContent` would report it.

    Raw character data in document order, entities already expanded by the
    parser, excluded subtrees contributing nothing, whitespace preserved
    verbatim. The page compares a selection against this exact string, so a
    normalisation here would report annotations lost against a document that
    never changed.
    """
    out = []
    for k in node.kids:
        if isinstance(k, Node):
            if k.tag not in EXCLUDED:
                out.append(text_of(k))
        else:
            out.append(k)
    return "".join(out)


def find_blocks(node, out):
    """Collect blocks in document order. Returns whether this subtree contains
    one.

    A block is the innermost element that holds text and has no descendant that
    is itself a block. The return value propagates "my subtree contains a block",
    NOT "I am a block" — returning the latter tells the parent nothing was found
    beneath it, so the parent re-qualifies and every ancestor becomes a block
    too. Blocks must be disjoint: the anchor check, the word count and the
    "which block did this selection start in" lookup all assume a passage
    belongs to exactly one.
    """
    if node.tag in EXCLUDED:
        return False
    if node.tag in OPAQUE:
        if has_text(node):
            out.append(node)
            return True
        return False
    found = False
    for k in _elements(node):
        if find_blocks(k, out):
            found = True
    if found:
        return True
    if node.tag not in INLINE and node.parent is not None and has_text(node):
        out.append(node)
        return True
    return False


def relative_refs(node, found=None):
    """Every relative `src`/`href` in the document, as (tag, attribute, value).

    A relative reference will not resolve once the document is served from the
    page directory, so the page renders with its assets missing. It warns rather
    than refusing: a missing image is visible to the reader, so a warning is
    enough for them to judge it.
    """
    found = [] if found is None else found
    for k in _elements(node):
        for attr in ("src", "href"):
            val = k.attrs.get(attr)
            if not val:
                continue
            v = val.strip()
            if not v or v.startswith(_NOT_RELATIVE) or _SCHEME.match(v):
                continue
            found.append((k.tag, attr, v))
        relative_refs(k, found)
    return found


def attribute_collisions(node, found=None):
    """Elements already carrying an attribute this module would add."""
    found = [] if found is None else found
    for k in _elements(node):
        for token in OURS:
            if token in k.attrs:
                found.append((k.tag, token, k.line))
        attribute_collisions(k, found)
    return found


class Ctx(object):
    """The running state of one render, shaped so `render_doc.check_anchors`
    accepts it: that function reads `ctx.blocks` and nothing else."""

    def __init__(self):
        self.blocks = {}
        self.sections = []
        self.title = ""
        self._slugs = {}

    def unique_slug(self, title):
        base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "section"
        seen = self._slugs.get(base, 0)
        self._slugs[base] = seen + 1
        return base if not seen else "%s-%d" % (base, seen + 1)


def instrument(src):
    """-> (instrumented html, Ctx, warnings). Raises Refused on a collision.

    Everything outside the injected attributes and the appended stylesheet is
    unchanged, which `strip()` checks.
    """
    tree = _Tree(src)
    tree.feed(src)
    tree.close()

    clashes = attribute_collisions(tree.root)
    if clashes:
        tag, token, line = clashes[0]
        raise Refused(
            "the document already uses %s (on <%s> at line %d); instrumenting it "
            "would leave every annotation in that element anchored to the "
            "author's value, invisibly" % (token, tag, line))

    warnings = []
    for tag, token in tree.text_collisions:
        warnings.append(
            "<%s> mentions %s; the author's rules or queries may reach the "
            "annotation markers" % (tag, token))
    rel = relative_refs(tree.root)
    if rel:
        shown = ", ".join("%s=%s" % (a, v) for _, a, v in rel[:5])
        warnings.append(
            "not self-contained: %d relative reference(s) will not resolve "
            "(%s%s)" % (len(rel), shown, ", ..." if len(rel) > 5 else ""))

    blocks = []
    find_blocks(tree.root, blocks)

    ctx = Ctx()
    section_title, section_id = "", ""
    edits = []
    for i, node in enumerate(blocks, start=1):
        text = text_of(node)
        blk = "b%d" % i
        ctx.blocks[blk] = text
        if node.tag in HEADINGS:
            title = " ".join(text.split())
            section_id = "s%d" % (len(ctx.sections) + 1)
            section_title = title
            ctx.sections.append({
                "id": section_id, "level": int(node.tag[1]), "title": title,
                "slug": ctx.unique_slug(title), "line": node.line,
                "words": 0, "titled": bool(title),
            })
            if not ctx.title:
                ctx.title = title
        if ctx.sections:
            ctx.sections[-1]["words"] += len(text.split())
        edits.append((node.tag_end, ' data-blk="%s" data-line="%d" data-sec="%s"'
                                    ' data-sec-id="%s"'
                      % (blk, node.line,
                         _html.escape(section_title, quote=True),
                         section_id)))

    # Applied last-first so an earlier offset is never shifted by a later edit.
    out = src
    for offset, text in sorted(edits, reverse=True):
        out = out[:offset] + text + out[offset:]

    # Appended at the very END so it shifts no data-line already recorded.
    out = out + "\n" + MARK_OPEN + MARKER_CSS + MARK_CLOSE + "\n"
    return out, ctx, warnings


_ATTR_RE = re.compile(
    r' data-blk="b\d+" data-line="\d+" data-sec="[^"]*" data-sec-id="[^"]*"')


def strip(instrumented):
    """Remove everything `instrument()` added. The result must equal the input
    it was built from, byte for byte — that equality is the whole argument that
    the artifact under review is still the artifact under review."""
    tail = "\n" + MARK_OPEN + MARKER_CSS + MARK_CLOSE + "\n"
    if instrumented.endswith(tail):
        instrumented = instrumented[:-len(tail)]
    return _ATTR_RE.sub("", instrumented)


def read(path):
    """Encoding is not optional. Python's default is the locale codepage, so on
    Windows a UTF-8 document decodes as cp1252 and every non-ASCII character
    arrives mangled — silently, while POSIX is fine throughout."""
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def main(argv=None):
    import argparse
    use_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("document", help="the .html or .htm file to instrument")
    ap.add_argument("--out", help="where to write the instrumented copy")
    a = ap.parse_args(argv)

    if not os.path.isfile(a.document):
        print("no such document: %s" % a.document)
        return 1
    try:
        src = read(a.document)
    except UnicodeDecodeError as e:
        print("%s is not valid UTF-8 (%s at byte %d)" % (a.document, e.reason, e.start))
        return 1
    try:
        out, ctx, warnings = instrument(src)
    except Refused as e:
        print("REFUSED: %s" % e)
        return 1

    words = sum(len(t.split()) for t in ctx.blocks.values())
    print("instrumented  %d blocks, %s words, %d section(s)"
          % (len(ctx.blocks), format(words, ",d"), len(ctx.sections)))
    for w in warnings:
        print("warning       %s" % w)
    if strip(out) != src:
        # The property this module exists to hold. Reported rather than assumed,
        # because a renderer that quietly normalised the author's markup would
        # look exactly like one that did not.
        print("ERROR         the instrumented copy does not strip back to the source")
        return 1
    if a.out:
        with io.open(a.out, "w", encoding="utf-8", newline="") as fh:
            fh.write(out)
        print("wrote         %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
