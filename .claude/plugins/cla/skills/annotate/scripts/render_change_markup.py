"""Placing a change's counterparts and claims in the rendered page.

String surgery on the HTML `render_doc.py` produced for each file: finding a
block's end, adding classes and attributes, marking requirement groups,
inlining the counterpart card beneath the block it answers to. Not a command:
import it, or run `render_change.py`.
"""

import html
import itertools
import re
import openspec_change as OC


def esc_attr(s):
    return html.escape(s or "", quote=True)


def add_class(html_str, blk, cls):
    """Add `cls` to the block's opening tag, merging with any class already
    there. Inserting a second `class=` attribute is not a merge — HTML keeps the
    first and silently drops the rest, so a block that already had one would lose
    it. No markdown-rendered block carries one today; `<p class="pt">` in
    plain-text mode does, and that is one caller away."""
    import re
    m = re.search(r'<(\w+)([^>]*)\bdata-blk="%s"' % re.escape(blk), html_str)
    if not m:
        return html_str
    if re.search(r'\bclass="', m.group(2)):
        return (html_str[:m.start(2)]
                + re.sub(r'\bclass="', 'class="%s ' % cls, m.group(2), count=1)
                + html_str[m.end(2):])
    return html_str[:m.end(1)] + ' class="%s"' % cls + html_str[m.end(1):]


def add_attr(html_str, blk, name, value):
    """Set the attribute `name` on the block's opening tag, replacing any value
    it already has there. A second copy of an attribute is not an update — HTML
    keeps the first and drops the rest — which is the trap `add_class` above
    names for `class`."""
    import re
    m = re.search(r'<(\w+)([^>]*)\bdata-blk="%s"([^>]*)>' % re.escape(blk), html_str)
    if not m:
        return html_str
    attr = '%s="%s"' % (name, esc_attr(value))
    tag = m.group(0)
    old = re.search(r'\s%s="[^"]*"' % re.escape(name), tag)
    if old:
        tag = tag[:old.start()] + " " + attr + tag[old.end():]
    else:
        tag = "<%s %s%s" % (m.group(1), attr, tag[1 + len(m.group(1)):])
    return html_str[:m.start()] + tag + html_str[m.end():]


def section_class(html_str, sec_id, cls):
    """Add `cls` to the `<section>` render_doc opened for `sec_id`."""
    import re
    m = re.search(r'<section class="([^"]*)" data-sec-id="%s">' % re.escape(sec_id), html_str)
    if not m:
        return html_str
    return html_str[:m.end(1)] + " " + cls + html_str[m.end(1):]


def _section_of_heading(html_str, blk):
    """The id of the section a heading block opens, or None. render_doc emits
    the `<section>` tag immediately before the heading that starts it."""
    import re
    m = re.search(r'<section class="[^"]*" data-sec-id="([^"]+)"><h\d\b[^>]*\bdata-blk="%s"'
                  % re.escape(blk), html_str)
    return m.group(1) if m else None


def _blocks_in_section(html_str, sec_id):
    """Every block id inside one section, in page order."""
    import re
    m = re.search(r'<section class="[^"]*" data-sec-id="%s">' % re.escape(sec_id), html_str)
    if not m:
        return []
    end = html_str.find("</section>", m.end())
    return re.findall(r'\bdata-blk="([^"]+)"', html_str[m.end():end if end >= 0 else None])


REQ_GROUPS = ("ADDED", "MODIFIED", "REMOVED")


def heading_lookup(ctx, claim):
    """`(block, None)` for a requirement's own `### Requirement:` heading, or
    `(None, why)` when it cannot be placed: `"heading not found"` or
    `"heading not unique"`.

    Matched on the whole text of a block, one match or none. `bind_claims`
    matches on a substring instead, and a substring can land on a paragraph
    that quotes the title; a label there would mark the wrong passage as the
    requirement. The name is normalised as OpenSpec normalises it first, so a
    closing `###` that the rendered heading drops does not stop the match.
    """
    if ctx is None:
        return None, "heading not found"
    name = " ".join(OC.strip_md(OC._norm_name(claim.get("raw") or claim["text"])).split())

    def is_heading(text):
        # The word in any case, as OpenSpec's header pattern accepts it.
        m = re.match(r"(?i)requirement:\s*(.*)$", " ".join(text.split()))
        return bool(m) and m.group(1) == name

    hits = [b for b, t in ctx.blocks.items() if is_heading(t)]
    if len(hits) == 1:
        return hits[0], None
    return None, "heading not found" if not hits else "heading not unique"


def heading_blk(ctx, claim):
    """The heading block `heading_lookup` finds, or None."""
    return heading_lookup(ctx, claim)[0]


def _unplaced(model, claim, what, why):
    """Record that a requirement's label or diff could not be put on the page,
    so the coverage pane can list it rather than it vanishing."""
    rows = model.setdefault("unplaced", [])
    for row in rows:
        if row["claim"]["id"] == claim["id"]:
            if what not in row["what"]:
                row["what"].append(what)
            return
    rows.append({"claim": claim, "what": [what], "why": why})


def mark_groups(model, bodies, ctxs):
    """Label each requirement heading with its ADDED, MODIFIED or REMOVED group,
    and set a REMOVED requirement's sections apart from the live ones.

    The label is an attribute the stylesheet draws with `::before`, so the
    heading's text — what every annotation offset is counted against — does not
    change. A REMOVED requirement's own section, and each section directly below
    it until the next heading of level 3 or above (its scenarios), are marked
    `req-removed`.
    Its `Reason` and `Migration` blocks are the blocks in those sections whose
    text starts with either word — found within the sections, never by
    searching the page, because changes repeat the same reason word for word.
    A heading that cannot be placed is recorded in `model["unplaced"]`.
    """
    for c in model["claims"]:
        if c["kind"] != "requirement" or c.get("group") not in REQ_GROUPS:
            continue
        ctx, f = ctxs.get(c["file"]), c["file"]
        blk, why = heading_lookup(ctx, c)
        if not blk:
            _unplaced(model, c, "label", why)
            continue
        bodies[f] = add_attr(bodies[f], blk, "data-group", c["group"])
        if c["group"] != "REMOVED":
            continue
        sid = _section_of_heading(bodies[f], blk)
        ids = [s["id"] for s in ctx.sections]
        if sid not in ids:
            continue
        i = ids.index(sid)
        removed = [sid] + [s["id"] for s in
                           itertools.takewhile(lambda s: s["level"] > 3,
                                               ctx.sections[i + 1:])]
        for s in removed:
            bodies[f] = section_class(bodies[f], s, "req-removed")
            for b in _blocks_in_section(bodies[f], s):
                if ctx.blocks.get(b, "").lstrip().startswith(("Reason", "Migration")):
                    bodies[f] = add_class(bodies[f], b, "rm-why")
    return bodies


def _outermost_block(html_str, blk):
    """The match for the outermost element carrying `data-blk` that encloses the
    one named — or the block itself when nothing encloses it."""
    import re
    m = re.search(r"<(\w+)([^>]*\bdata-blk=\"%s\")" % re.escape(blk), html_str)
    if not m:
        return None
    for outer in re.finditer(r"<(\w+)([^>]*\bdata-blk=\"[^\"]+\")", html_str):
        if outer.start() >= m.start():
            break
        if _element_end(html_str, outer) > m.start():
            return outer          # it opens before and closes after: it encloses
    return m


def _element_end(html_str, m):
    """The index just past the closing tag of the element `m` opens."""
    import re
    tag, i, depth = m.group(1), m.end(), 1
    open_re, close_re = re.compile(r"<%s\b" % tag), re.compile(r"</%s>" % tag)
    while depth and i < len(html_str):
        o, c = open_re.search(html_str, i), close_re.search(html_str, i)
        if not c:
            return len(html_str)
        if o and o.start() < c.start():
            depth += 1
            i = o.end()
        else:
            depth -= 1
            i = c.end()
    return i


def after_block(html_str, blk, extra):
    """Insert `extra` immediately after the element carrying data-blk=`blk`, and
    outside every block that encloses it.

    A sibling, never a child: inside a block, `extra`'s words are counted into
    every offset measured against that block, and annotations on it start
    reporting themselves lost against a document nobody touched.

    Closing the inner element is not enough, because blocks NEST. A nested list
    puts `<li data-blk="tasks:b2">` inside `<li data-blk="tasks:b1">`, so landing
    after the inner `</li>` lands inside the outer block — which is the failure
    this docstring already forbade, arriving one level up. Walk out to the
    outermost enclosing block first.
    """
    import re
    m = _outermost_block(html_str, blk)
    if not m:
        return html_str
    tag, i, depth = m.group(1), m.end(), 1
    open_re, close_re = re.compile(r"<%s\b" % tag), re.compile(r"</%s>" % tag)
    while depth and i < len(html_str):
        o, c = open_re.search(html_str, i), close_re.search(html_str, i)
        if not c:
            return html_str
        if o and o.start() < c.start():
            depth += 1
            i = o.end()
        else:
            depth -= 1
            i = c.end()
    return html_str[:i] + extra + html_str[i:]


def inside_block(html_str, blk, extra):
    """Insert `extra` just inside the end of the block — for the gutter, which is
    positioned against it and is declared in render_doc.INJECTED_CLASSES."""
    import re
    m = re.search(r"<(\w+)([^>]*\bdata-blk=\"%s\")" % re.escape(blk), html_str)
    if not m:
        return html_str
    tag, i, depth = m.group(1), m.end(), 1
    open_re, close_re = re.compile(r"<%s\b" % tag), re.compile(r"</%s>" % tag)
    while depth and i < len(html_str):
        o, c = open_re.search(html_str, i), close_re.search(html_str, i)
        if not c:
            return html_str
        if o and o.start() < c.start():
            depth += 1
            i = o.end()
        else:
            depth -= 1
            i = c.start() if depth == 0 else c.end()
    return html_str[:i] + extra + html_str[i:]


def bind_claims(model, ctxs):
    """Give every claim the block it was rendered into, or None.

    Bound by text, one match or none — the rule the anchor layer keeps. A claim
    that cannot be placed keeps its row in the coverage tab and loses only its
    link; it is never bound to a guess, because a link that scrolls somewhere
    arbitrary is worse than no link.
    """
    for c in model["claims"]:
        ctx = ctxs.get(c["file"])
        c["blk"] = None
        if not ctx:
            continue
        needle = c["text"][:70]
        if not needle:
            continue
        hits = [b for b, t in ctx.blocks.items() if needle in t]
        # One match or none. Two blocks holding the same text is exactly the case
        # where a guess sends the reader to the wrong passage while showing them
        # text that looks right.
        c["blk"] = hits[0] if len(hits) == 1 else None


def counterparts(model, bodies, ctxs, labels):
    """Hang a gutter mark and an inlined counterpart off every linked block."""
    by_id = {c["id"]: c for c in model["claims"]}
    per_claim = {}
    for l in model["links"]:
        for a, b in ((l["src"], l["dst"]), (l["dst"], l["src"])):
            per_claim.setdefault(a, []).append((by_id.get(b), l))

    for cid, partners in per_claim.items():
        c = by_id.get(cid)
        if not c or not c.get("blk"):
            continue
        marks, cards = "", ""
        # Strongest first: a citation, then a path, then an identifier, then
        # shared wording — so the best evidence is the one read first.
        order = {k: i for i, k in enumerate(OC.LINK_KINDS)}
        seen = set()
        # No .get default: a kind nobody ranked is a bug, and sorting it
        # quietly last is how it stays one.
        for other, link in sorted(partners, key=lambda p: order[p[1]["kind"]]):
            if not other or not other.get("blk") or other["id"] in seen:
                continue
            seen.add(other["id"])
            weak = link["kind"] == "wording"
            label = "%s · %s %s" % (labels.get(other["file"], other["file"]),
                                    other["kind"], other["num"])
            excerpt = html.escape(other["text"][:400], quote=False)
            marks += ('<b class="%s" data-label="%s" data-excerpt="%s" data-go-blk="%s">%s</b>'
                      % ("weak" if weak else "", esc_attr(label), esc_attr(excerpt),
                         esc_attr(other["blk"]), esc_attr(other["file"][0])))
            cards += ('<span class="cf%s"><span class="cf-h">%s '
                      '<span class="cf-why">%s %s</span>'
                      '<span class="cf-go" data-go-blk="%s">open in tab →</span>'
                      '</span><span class="cf-x" role="button" tabindex="0" '
                      'aria-expanded="false">%s</span></span>'
                      % (" weak" if weak else "", esc_attr(label),
                         link["kind"], esc_attr(link["why"][:60]),
                         esc_attr(other["blk"]), excerpt))
        if not marks:
            continue
        f = c["file"]
        bodies[f] = add_class(bodies[f], c["blk"], "linked")
        bodies[f] = inside_block(bodies[f], c["blk"], '<span class="gut">%s</span>' % marks)
        bodies[f] = after_block(bodies[f], c["blk"], cards)
    return bodies
