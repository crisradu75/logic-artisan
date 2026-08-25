#!/usr/bin/env python3
"""Render a Markdown or plain-text document as an annotatable reading page.

Stdlib only, and it runs on Windows and POSIX alike.

    python3 <plugin>/skills/annotate/scripts/render_doc.py docs/spec.md
    python3 <plugin>/skills/annotate/scripts/render_doc.py notes.txt --out page.html

The page goes to a temp directory, never into the repo. It is a working view of
a document rather than something the repo keeps, and writing it into the tree
would mean every consuming repo needs a `.gitignore` entry the install has no
business adding.

Serve the result with `annotate_server.py`, which collects annotations against
it. The corpus's shape lives in [annotations_store.py](annotations_store.py) and
is read there, never restated.

**Every block the reader can select carries `data-blk` and `data-line`.**
`data-blk` is an ordinal, so it moves when the document is edited above it and
the page relocates an annotation by its text and context when it does.
`data-line` is the source line the block came from — it does not move for the
right reason either, but it is what turns "this passage" into a place in the
*source*, which is where an edit actually has to land. The rendered text drops
inline markers (`**bold**` reads as `bold`), so an annotation's `text` is what
was on screen; `line` is how you find it in the file.

Markdown support is a working subset, not a spec implementation: front matter,
ATX headings, paragraphs, nested ordered and unordered lists, fenced code,
blockquotes, pipe tables, thematic breaks, links, images, and inline bold,
italic, strikethrough and code. **Anything unrecognised is passed through as
escaped text rather than guessed at** — a wrong guess renders confidently and
silently, and the reader annotates a passage the document does not contain.
"""
import argparse
import base64
import hashlib
import html
import json
import mimetypes
import os
import re
import sys
import tempfile

import annotations_store as store

# What the page injects into the prose that the document does not contain: the
# annotation marker, and the change page's link gutter. This
# constant is the Python half of the page's own NON_SOURCE, and the two must
# agree — an annotation records the document's characters, so anything the
# renderer added has to come out on both sides, or the browser and this script
# disagree about what a block says. One constant per side, never a list per use
# site: three hand-maintained copies is how a class gets missed.
INJECTED_CLASSES = ("cmt-sup", "gut")

MAX_INLINE_IMAGE_BYTES = 2 * 1024 * 1024

FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*([^`]*)$")
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
HR_RE = re.compile(r"^ {0,3}([-*_])[ \t]*(?:\1[ \t]*){2,}$")
QUOTE_RE = re.compile(r"^ {0,3}>")
LIST_RE = re.compile(r"^(\s*)([-*+]|\d{1,9}[.)])[ \t]+(.*)$")
TABLE_SEP_RE = re.compile(r"^ {0,3}\|?[ \t]*:?-{1,}:?[ \t]*(\|[ \t]*:?-{1,}:?[ \t]*)*\|?[ \t]*$")

# Private-use sentinels (U+E000, U+E001). A code span is lifted out before
# escaping and put back after, so nothing inside it is read as emphasis or a
# link. These two characters are ones a document does not contain; a printable
# marker is not, and a document that happened to contain it would have its own
# text substituted with someone else's code.
CODE_OPEN, CODE_CLOSE = "", ""


def esc(s):
    return html.escape(s or "", quote=False)


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "section"


# ---------------------------------------------------------------- inline


def _data_uri(path):
    """A local image small enough to carry, as a data URI — or None.

    The page is served out of a temp directory, so a relative `src` from the
    document resolves against the wrong root and a `file://` subresource is
    blocked from an `http://` page outright. Both fail *silently*, as a broken
    image icon. Carrying the bytes is the only form that actually renders, and
    anything too big, remote, or unreadable becomes a link, which at least says
    what it is.
    """
    try:
        if os.path.getsize(path) > MAX_INLINE_IMAGE_BYTES:
            return None
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    if not mime.startswith("image/"):
        return None
    return "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode("ascii"))


def _safe_href(url):
    """`javascript:` and `data:` hrefs never reach the page. The document is
    usually trusted, but "usually" is not a property a renderer can rely on, and
    a page that executes what it is reading is a different kind of tool."""
    u = (url or "").strip()
    if re.match(r"^\s*(javascript|vbscript|data)\s*:", u, re.I):
        return "#"
    return u


def inline(text, doc_dir):
    """Inline Markdown to HTML. Escaping happens first and once; every producer
    below emits its own tags into already-escaped text, so nothing the document
    contains can close a tag this function opened."""
    codes = []

    def stash(m):
        codes.append(m.group(2))
        return CODE_OPEN + str(len(codes) - 1) + CODE_CLOSE

    text = re.sub(r"(`+)(.+?)\1", stash, text, flags=re.S)
    text = esc(text)

    # These run over text `esc()` has ALREADY escaped, so an href or an alt is
    # only quote-guarded here, never escaped again: `html.escape` on an escaped
    # string turns `&amp;` into `&amp;amp;`, and a URL with a query string
    # arrives on the page visibly wrong.
    def attr(s):
        return s.replace('"', "&quot;")

    def image(m):
        alt, src = m.group(1), _safe_href(m.group(2))
        if not re.match(r"^[a-z]+:", src, re.I):
            local = html.unescape(src).replace("/", os.sep)
            uri = _data_uri(os.path.join(doc_dir, local))
            if uri:
                return '<img alt="%s" src="%s">' % (attr(alt), uri)
        return '<a class="imglink" href="%s" target="_blank" rel="noopener">%s</a>' % (
            attr(src), alt or src)

    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", image, text)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)",
        lambda m: '<a href="%s" target="_blank" rel="noopener">%s</a>'
                  % (attr(_safe_href(m.group(2))), m.group(1)),
        text)
    text = re.sub(r"&lt;(https?://[^&\s]+)&gt;",
                  lambda m: '<a href="%s" target="_blank" rel="noopener">%s</a>'
                            % (attr(m.group(1)), m.group(1)), text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text, flags=re.S)
    text = re.sub(r"(?<![\w\\])__(.+?)__(?!\w)", r"<strong>\1</strong>", text, flags=re.S)
    text = re.sub(r"~~(.+?)~~", r"<del>\1</del>", text, flags=re.S)
    text = re.sub(r"(?<!\*)\*([^*\n][^*]*?)\*(?!\*)", r"<em>\1</em>", text, flags=re.S)
    text = re.sub(r"(?<![\w`])_([^_\n]+?)_(?![\w`])", r"<em>\1</em>", text)
    return re.sub(CODE_OPEN + r"(\d+)" + CODE_CLOSE,
                  lambda m: "<code>%s</code>" % esc(codes[int(m.group(1))]), text)


def plain(fragment):
    """The text of a rendered fragment, as the browser's `textContent` would
    give it. The page reads a block's characters this way and so must this
    script, or the two disagree about what an annotation anchored to."""
    fragment = re.sub(r"<[^>]+>", "", fragment)
    return html.unescape(fragment)


# ---------------------------------------------------------------- blocks


class Ctx:
    """The running state of one render: block ordinals, the current heading, the
    plain text of every addressable block (kept for the anchor check), and the
    section list the navigation rail is built from."""

    def __init__(self, doc_dir, prefix=""):
        # `prefix` namespaces block ids per file. Rendering several files into
        # one page without it restarts every file at b1, and an annotation on
        # one document then repaints onto another — found in the mock, where
        # four files produced 251 blocks and colliding ids.
        self.doc_dir = doc_dir
        self.prefix = prefix
        self.n = 0
        self.section = ""
        self.blocks = {}
        self.title = ""
        self.sections = []
        self.open_section = False
        self._slugs = {}

    def take(self, text):
        self.n += 1
        blk = "%sb%d" % (self.prefix, self.n)
        self.blocks[blk] = text
        if self.sections:
            # Words are attributed to the section open when the block was
            # emitted, which is why this counts here rather than over the
            # finished HTML: by then a block's section is only recoverable by
            # re-parsing, and a heading inside a blockquote reads like a section
            # boundary that never existed.
            self.sections[-1]["words"] += len(text.split())
        return blk

    def attrs(self, text, line):
        return ' data-blk="%s" data-line="%d" data-sec="%s"' % (
            self.take(text), line, html.escape(self.section, quote=True))

    def unique_slug(self, title):
        """A heading's anchor, deduplicated. Two sections called "Notes" would
        otherwise share one `id`, and a document's own `[link](#notes)` would
        land on whichever the browser found first."""
        base = (self.prefix.replace(":", "-") + slugify(title)) if self.prefix else slugify(title)
        seen = self._slugs.get(base, 0)
        self._slugs[base] = seen + 1
        return base if not seen else "%s-%d" % (base, seen + 1)

    def new_section(self, level, title, line, slug):
        """Open a section. `id` is an ordinal and is what the rail and the
        scroll-spy key on; `slug` is the heading's own anchor and is what the
        document's internal links point at. They are separate because only one
        of them can be allowed to change when a heading is retitled."""
        sid = "%ss%d" % (self.prefix, len(self.sections) + 1)
        self.sections.append({"id": sid, "level": level, "title": title,
                              "slug": slug, "line": line, "words": 0,
                              "titled": bool(title)})
        return sid


def _starts_block(line, nxt):
    s = line.rstrip()
    if not s.strip():
        return True
    return bool(FENCE_RE.match(s) or HEADING_RE.match(s) or HR_RE.match(s)
                or QUOTE_RE.match(s) or LIST_RE.match(line)
                or ("|" in s and nxt is not None and TABLE_SEP_RE.match(nxt)))


def render_blocks(lines, ctx, top=False):
    """`lines` is a list of (source line number, text). Returns HTML.

    `top` marks the outermost call, and only there does a heading start a new
    `<section>`. That distinction is the whole point: a `#` inside a fenced code
    block or a blockquote is content, not structure, and splitting the document
    on raw heading-shaped lines would put a section boundary inside a shell
    script. Recursing decides it instead — by the time this sees a heading at
    `top`, the fence and the quote have already consumed their own lines.
    """
    out, i, n = [], 0, len(lines)
    while i < n:
        lno, raw = lines[i]
        s = raw.rstrip()
        if not s.strip():
            i += 1
            continue

        m = FENCE_RE.match(s)
        if m:
            fence, lang = m.group(1), m.group(2).strip().split()[0] if m.group(2).strip() else ""
            close = re.compile(r"^ {0,3}%s{%d,}\s*$" % (re.escape(fence[0]), len(fence)))
            body, i = [], i + 1
            while i < n and not close.match(lines[i][1]):
                body.append(lines[i][1])
                i += 1
            i += 1                              # the closing fence, if there was one
            code = "\n".join(body)
            # quote=True, and not `esc()`. `esc()` is quote=False — right for
            # text nodes, wrong here, because this is the one place a document's
            # own characters reach an ATTRIBUTE. A fence opened
            # ```js"onmouseover="alert(1) closed the class attribute and left a
            # live handler on a page that is same-origin with the endpoint
            # appending to a committed, never-rewritten corpus.
            cls = ' class="language-%s"' % html.escape(lang, quote=True) if lang else ""
            out.append("<pre%s><code%s>%s</code></pre>"
                       % (ctx.attrs(code, lno), cls, esc(code)))
            continue

        m = HEADING_RE.match(s)
        if m:
            level, txt = len(m.group(1)), m.group(2)
            body = inline(txt, ctx.doc_dir)
            ctx.section = plain(body)
            if level == 1 and not ctx.title:
                ctx.title = ctx.section
            slug = ctx.unique_slug(ctx.section)
            if top:
                if ctx.open_section:
                    out.append("</section>")
                sid = ctx.new_section(level, ctx.section, lno, slug)
                out.append('<section class="sec" data-sec-id="%s">' % sid)
                ctx.open_section = True
            out.append("<h%d%s id=\"%s\">%s</h%d>"
                       % (level, ctx.attrs(plain(body), lno), slug, body, level))
            i += 1
            continue

        if HR_RE.match(s):
            out.append("<hr>")
            i += 1
            continue

        if QUOTE_RE.match(s):
            grp = []
            while i < n and (QUOTE_RE.match(lines[i][1]) or (grp and lines[i][1].strip())):
                grp.append((lines[i][0], re.sub(r"^ {0,3}> ?", "", lines[i][1])))
                i += 1
            out.append("<blockquote>%s</blockquote>" % render_blocks(grp, ctx))
            continue

        nxt = lines[i + 1][1] if i + 1 < n else None
        if "|" in s and nxt is not None and TABLE_SEP_RE.match(nxt):
            html_tbl, i = render_table(lines, i, ctx)
            out.append(html_tbl)
            continue

        if LIST_RE.match(raw):
            html_list, i = render_list(lines, i, ctx)
            out.append(html_list)
            continue

        para, first = [], lno
        while i < n and lines[i][1].strip():
            if para and _starts_block(lines[i][1], lines[i + 1][1] if i + 1 < n else None):
                break
            para.append(lines[i][1].strip())
            i += 1
        body = inline(" ".join(para), ctx.doc_dir)
        out.append("<p%s>%s</p>" % (ctx.attrs(plain(body), first), body))
    return "".join(out)


def render_list(lines, i, ctx):
    """One list and everything nested inside it. Returns (html, next index).

    An item's continuation is decided by indentation against the item's own
    content column, and the content is then rendered recursively — which is what
    makes a paragraph, a nested list or a fenced block inside a bullet work
    without a second code path for each.
    """
    n = len(lines)
    base = LIST_RE.match(lines[i][1])
    indent = len(base.group(1))
    ordered = base.group(2)[0].isdigit()
    items, cur, cur_line, content_col = [], None, None, 0
    while i < n:
        raw = lines[i][1]
        m = LIST_RE.match(raw)
        if m and len(m.group(1)) <= indent + 1:
            if len(m.group(1)) < indent:
                break
            # A bullet where an ordered item was, at the same level, is a new
            # list rather than a sibling — running them together renumbers one
            # into the other's sequence.
            if m.group(2)[0].isdigit() != ordered:
                break
            if cur is not None:
                items.append((cur_line, cur))
            content_col = len(m.group(1)) + len(m.group(2)) + 1
            cur, cur_line = [(lines[i][0], m.group(3))], lines[i][0]
            i += 1
            continue
        if cur is None:
            break
        if not raw.strip():
            # A blank line ends the list only when what follows belongs to
            # neither the current item nor the list. Ending it unconditionally
            # split every list holding a paragraph inside a bullet in two; ending
            # it whenever the next line was not indented into the item did the
            # same to every list with a blank line between its bullets, which is
            # the ordinary way a loose list is written.
            j = i + 1
            while j < n and not lines[j][1].strip():
                j += 1
            if j >= n:
                break
            lead_j = len(lines[j][1]) - len(lines[j][1].lstrip())
            sibling = LIST_RE.match(lines[j][1]) and indent <= lead_j <= indent + 1
            if lead_j < content_col and not sibling:
                break
            cur.append((lines[i][0], ""))
            i += 1
            continue
        lead = len(raw) - len(raw.lstrip())
        if lead < content_col and not LIST_RE.match(raw):
            if _starts_block(raw, lines[i + 1][1] if i + 1 < n else None):
                break
            cur.append((lines[i][0], raw.strip()))          # lazy continuation
            i += 1
            continue
        cur.append((lines[i][0], raw[min(lead, content_col):]))
        i += 1
    if cur is not None:
        items.append((cur_line, cur))

    parts = []
    for _lno, body in items:
        inner = render_blocks(body, ctx)
        # A one-paragraph item reads as a bullet, not as a paragraph inside a
        # bullet: the paragraph's attributes move onto the <li> so the item is
        # itself the addressable block. Anything richer keeps its own blocks.
        m = re.match(r"^<p([^>]*)>(.*?)</p>(.*)$", inner, re.S)
        if m and "<p" not in m.group(3):
            parts.append("<li%s>%s%s</li>" % (m.group(1), m.group(2), m.group(3)))
        else:
            parts.append("<li>%s</li>" % inner)
    tag = "ol" if ordered else "ul"
    return "<%s>%s</%s>" % (tag, "".join(parts), tag), i


def _cells(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", s)]


def render_table(lines, i, ctx):
    head = _cells(lines[i][1])
    aligns = []
    for spec in _cells(lines[i + 1][1]):
        left, right = spec.startswith(":"), spec.endswith(":")
        aligns.append("center" if left and right else "right" if right else
                      "left" if left else "")
    rows, j = [], i + 2
    while j < len(lines) and "|" in lines[j][1] and lines[j][1].strip():
        rows.append((lines[j][0], _cells(lines[j][1])))
        j += 1

    def cell(tag, text, line, idx):
        body = inline(text, ctx.doc_dir)
        al = aligns[idx] if idx < len(aligns) else ""
        style = ' style="text-align:%s"' % al if al else ""
        return "<%s%s%s>%s</%s>" % (tag, ctx.attrs(plain(body), line), style, body, tag)

    out = ["<div class=\"tw\"><table><thead><tr>"]
    out += [cell("th", c, lines[i][0], k) for k, c in enumerate(head)]
    out.append("</tr></thead><tbody>")
    for line, cs in rows:
        out.append("<tr>")
        out += [cell("td", c, line, k) for k, c in enumerate(cs)]
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out), j


def strip_html_comments(text):
    """HTML comments are not content and must not be annotatable — but they must
    not shift the line numbers either, since `data-line` is the whole point of
    recording one. Each comment is replaced by as many newlines as it spanned."""
    return re.sub(r"<!--.*?-->",
                  lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)


def render_document(text, doc_dir, plain_text=False, prefix=""):
    """-> (body html, Ctx). `plain_text` renders with no markup interpretation.

    `prefix` namespaces this file's block ids, for a page holding several files.
    """
    ctx = Ctx(doc_dir, prefix)
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    lines = text.split("\n")

    # Everything before the first heading still needs a section to live in, or a
    # document that opens with prose has blocks outside every observed region and
    # the rail lights nothing until the reader scrolls past the first heading. It
    # gets no rail entry: it has no title to show. Opened before the front matter
    # is rendered, so that block's words are attributed like any other.
    sid = ctx.new_section(0, "", 1, "")
    ctx.open_section = True
    head = '<section class="sec" data-sec-id="%s">' % sid

    front = ""
    start = 0
    if lines and lines[0].strip() == "---" and not plain_text:
        for k in range(1, len(lines)):
            if lines[k].strip() in ("---", "..."):
                block = "\n".join(lines[1:k])
                front = ('<div class="fm"><span class="fm-t">front matter</span>'
                         '<pre%s><code>%s</code></pre></div>'
                         % (ctx.attrs(block, 2), esc(block)))
                start = k + 1
                break

    body_lines = list(enumerate(lines[start:], start=start + 1))
    if plain_text:
        parts, buf, first = [], [], None
        for lno, ln in body_lines + [(0, "")]:
            if ln.strip():
                buf.append(ln)
                first = first or lno
            elif buf:
                block = "\n".join(buf)
                parts.append('<p class="pt"%s>%s</p>' % (ctx.attrs(block, first), esc(block)))
                buf, first = [], None
        body = "".join(parts)
    else:
        body = strip_html_comments("\n".join(l for _, l in body_lines))
        body = render_blocks(list(zip([l for l, _ in body_lines], body.split("\n"))),
                             ctx, top=True)
    return head + front + body + "</section>", ctx


# ---------------------------------------------------------------- the page


def rail(sections):
    """The navigation pane: one entry per titled section, indented by depth.

    Depth is measured against the shallowest heading present, not against `h1`.
    A document whose top level is `##` — every SKILL.md reference, most notes —
    would otherwise render its entire rail indented one step, with the left
    column reserved for a level nothing in the file uses.

    The bar is the section's length against the longest section, which is what
    makes the rail answer "where is the weight of this document" and not only
    "what is it called".
    """
    titled = [s for s in sections if s["titled"]]
    if not titled:
        return ""
    base = min(s["level"] for s in titled)
    longest = max((s["words"] for s in titled), default=0)
    out = []
    for s in titled:
        depth = min(s["level"] - base, 4)
        pct = (100.0 * s["words"] / longest) if longest else 0
        out.append(
            '<a class="rail-item" href="#%s" data-go-sec="%s" data-depth="%d">'
            '<span class="rail-main"><span class="rail-title">%s</span>'
            '<span class="rail-bar"><i style="width:%.1f%%"></i></span></span>'
            '<span class="rail-meta"><span class="rail-n">%s</span>'
            '<span class="rail-c" data-count="%s" hidden></span></span></a>'
            % (s["slug"], s["id"], depth, esc(s["title"]), pct,
               format(s["words"], ",d"), s["id"]))
    return "".join(out)


FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
    # The two accents, spelled out rather than read from the stylesheet: this
    # SVG is base64'd into a data URI and never sees a CSS variable. `.b` is
    # --mark and moves with it — it was left at the old #C8622F when --mark was
    # darkened for contrast, which put a differently-coloured bar on the tab.
    '<style>.a{fill:#2F5C57}.b{fill:#9E4718}'
    '@media (prefers-color-scheme:dark){.a{fill:#84B8B0}.b{fill:#E0915E}}</style>'
    '<path class="a" d="M3.4 1h5.3l3.9 3.9V15H3.4z"/>'
    '<path class="a" opacity=".55" d="M8.7 1l3.9 3.9H8.7z"/>'
    '<path class="b" d="M1.5 8.7h11v3h-11z"/></svg>'
)

CSS = """
:root{
 --paper:#F2F2EE;--ground:#E5E6E1;--sunk:#DCDDD7;
 --ink:#1A1D1F;--ink-2:#3E4447;--muted:#585E62;--rule:#C9CBC5;--hair:#DBDCD6;
 --accent:#2F5C57;--accent-2:#4C837C;--accent-wash:#DCE7E3;
 --mark:#9E4718;--mark-wash:#F1DFD4;
}
/* --muted carries nearly every label on this page and --mark carries the whole
   annotation layer, so both are read as text and both answer to WCAG AA (4.5:1)
   on all three light surfaces, not just on --paper. They did not: --muted was
   4.22 / 3.78 / 3.47 and --mark 3.57 / 3.19 / 2.93. They now measure 5.86 /
   5.24 / 4.81 and 5.55 / 4.97 / 4.56, so the worst pair on the page is 4.56 —
   --mark on --sunk, which is the drawer's own ground and the pair nobody looks
   at. Changing either value re-derives every one of those six numbers, and the
   command that produces them is the test:

     python3 -m pytest plugin-tests/tests/skills/annotate/test_render_doc.py -k wcag

   It reads the palette out of the rendered page and fails below 4.5:1, so it
   goes red on a value this comment has not been updated for. The old hex codes
   are deliberately not repeated here: dead colours in prose are a grep magnet
   that nothing fails on. */
/* Light is the default outright, and there is deliberately no
   `prefers-color-scheme` rule: this page is a reading surface for a working
   document, and it opens the same way on every machine rather than tracking a
   system setting the reader did not choose for it. The emitted HTML carries
   data-theme="light" on the root, so dark applies only once the toggle has
   asked for it — which also means no flash of the other palette on load. */
:root[data-theme="dark"]{
 --paper:#16191B;--ground:#101314;--sunk:#1C2022;
 --ink:#DCDEDA;--ink-2:#B0B5B3;--muted:#8E9491;--rule:#2B3033;--hair:#23282A;
 --accent:#84B8B0;--accent-2:#5E938C;--accent-wash:#172523;
 --mark:#E0915E;--mark-wash:#291A11;
}
*{box-sizing:border-box}
/* No declaration on this page goes below .69rem. `rem` resolves against the
   ROOT, which is 16px — `body{font-size:17px}` below does not move it — so
   .69rem is 11.04px and anything under it was 9–10px type carrying locators,
   counts and failure states. 21 declarations were below that floor. */
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--ground);color:var(--ink);font-size:17px;line-height:1.65;
 font-family:ui-serif,Charter,"Iowan Old Style",Georgia,Cambria,"Times New Roman",serif}
.mono,code,pre,kbd{font-family:ui-monospace,SFMono-Regular,"Cascadia Mono","Segoe UI Mono",
 Menlo,Consolas,"Liberation Mono",monospace}
:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:2px}

.bar{position:sticky;top:0;z-index:60;background:var(--paper);border-bottom:1px solid var(--rule);
 display:flex;align-items:center;gap:.85rem;padding:.55rem 1.1rem;
 font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.72rem}
.bar-doc{color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:46vw}
.bar-stat{color:var(--muted);letter-spacing:.06em;text-transform:uppercase;
 font-variant-numeric:tabular-nums;white-space:nowrap}
.bar-sp{flex:1}
.bar-tools{display:flex;align-items:center;gap:.15rem;flex:none}
.bar-ico{width:1.7rem;height:1.7rem;flex:none;display:inline-flex;align-items:center;
 justify-content:center;border:0;border-radius:3px;background:none;cursor:pointer;
 color:var(--muted);font-size:.95rem;line-height:1;padding:0}
.bar-ico:hover{color:var(--ink);background:var(--sunk)}
.bar-ico[disabled]{cursor:progress;color:var(--ink);animation:spin .9s linear infinite}
.bar-ico.failed{color:var(--mark)}
@keyframes spin{from{transform:rotate(0)}to{transform:rotate(360deg)}}
.ico-svg{width:.95rem;height:.95rem;display:block;flex:none}
.opener{font:inherit;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
 font-size:.72rem;cursor:pointer;display:flex;align-items:center;gap:.5rem;background:transparent;
 border:1px solid var(--mark);border-radius:3px;padding:.36rem .55rem .36rem .7rem;color:var(--mark);
 letter-spacing:.07em;text-transform:uppercase;box-shadow:inset 3px 0 0 var(--mark)}
.opener:hover{background:var(--mark-wash)}
.opener[aria-expanded="true"]{background:var(--mark);border-color:var(--mark);color:var(--paper);
 box-shadow:inset 3px 0 0 var(--paper)}
/* The one always-visible surface, so it carries any state the drawer would
   otherwise hold off-screen — an unreadable corpus, a dead server, an unsaved
   note. Not a colour alone: the dot is what survives a reader who cannot tell
   these two oranges apart. */
.opener.failing{border-color:var(--mark);background:var(--mark);color:var(--paper);
 box-shadow:inset 3px 0 0 var(--paper)}
.opener.failing::after{content:"!";font-weight:700;margin-left:.15rem}
.opener.failing .cmt-n{background:var(--paper);color:var(--mark)}
.cmt-n{font-variant-numeric:tabular-nums;background:var(--mark-wash);color:var(--mark);
 border-radius:999px;padding:.05rem .42rem;font-size:0.69rem;min-width:1.35rem;text-align:center}
.opener[aria-expanded="true"] .cmt-n{background:var(--paper);color:var(--mark)}

.shell{display:grid;grid-template-columns:clamp(13rem,18vw,17rem) minmax(0,1fr);
 align-items:start}
.rail{position:sticky;top:2.9rem;height:calc(100vh - 2.9rem);overflow-y:auto;
 padding:1.3rem .8rem 3rem 1.1rem;border-right:1px solid var(--rule);background:var(--paper)}
.rail-h{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;letter-spacing:.16em;
 text-transform:uppercase;color:var(--muted);margin:0 0 .8rem .1rem}
.rail-item{display:grid;grid-template-columns:1fr auto;gap:.5rem;align-items:center;
 text-decoration:none;color:var(--ink-2);padding:.42rem .45rem;border-radius:2px;
 border-left:2px solid transparent}
.rail-item:hover{background:var(--sunk);color:var(--ink)}
.rail-item.on{border-left-color:var(--accent);background:var(--accent-wash);color:var(--ink)}
.rail-item[data-depth="1"]{padding-left:1.2rem}
.rail-item[data-depth="2"]{padding-left:2rem}
.rail-item[data-depth="3"]{padding-left:2.8rem}
.rail-item[data-depth="4"]{padding-left:3.6rem}
.rail-main{display:flex;flex-direction:column;gap:.3rem;min-width:0}
.rail-title{font-size:.9rem;line-height:1.25}
.rail-item[data-depth="0"] .rail-title{font-weight:600}
.rail-item[data-depth="2"] .rail-title,.rail-item[data-depth="3"] .rail-title,
.rail-item[data-depth="4"] .rail-title{font-size:.8rem}
.rail-bar{display:block;height:3px;background:var(--hair);border-radius:2px;overflow:hidden}
.rail-bar i{display:block;height:100%;background:var(--accent-2);opacity:.5}
.rail-item.on .rail-bar i{opacity:1}
.rail-meta{display:flex;align-items:center;gap:.3rem;flex:none}
.rail-n{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;
 font-variant-numeric:tabular-nums;color:var(--muted);text-align:right}
.rail-item.on .rail-n{color:var(--accent)}
/* The annotation count is the reason to look at the rail once a pass is under
   way: it says which sections were argued with, which is not the same question
   as which are long. */
.rail-c{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;
 font-variant-numeric:tabular-nums;background:var(--mark);color:var(--paper);
 border-radius:999px;padding:.02rem .34rem;min-width:1.1rem;text-align:center}
.rail-c[hidden]{display:none}
.rail-foot{margin-top:1.1rem;padding-top:.9rem;border-top:1px solid var(--hair);
 font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;line-height:1.7;
 color:var(--muted)}
.sec{scroll-margin-top:4rem}

.page{background:var(--paper);min-height:100vh;padding:0 1.5rem 10rem}
.col{max-width:44rem;margin:0 auto;padding-top:2.4rem}
h1,h2,h3,h4,h5,h6{font-weight:600;line-height:1.25;text-wrap:balance;scroll-margin-top:4rem}
h1{font-size:2rem;margin:0 0 1.4rem;letter-spacing:-.012em}
h2{font-size:1.4rem;margin:2.6rem 0 .9rem;padding-bottom:.35rem;border-bottom:1px solid var(--hair)}
h3{font-size:1.13rem;margin:2rem 0 .7rem}
h4,h5,h6{font-size:1rem;margin:1.6rem 0 .6rem;color:var(--ink-2)}
p{margin:0 0 1.1rem}
a{color:var(--accent);text-underline-offset:2px}
strong{font-weight:650}
del{color:var(--muted)}
hr{border:0;border-top:1px solid var(--rule);margin:2.4rem 0}
ul,ol{margin:0 0 1.1rem;padding-left:1.5rem}
li{margin:.3rem 0}
li>ul,li>ol{margin:.3rem 0}
blockquote{margin:1.4rem 0;padding:.1rem 0 .1rem 1.1rem;border-left:2px solid var(--accent-2);
 color:var(--ink-2)}
blockquote p:last-child{margin-bottom:0}
code{font-size:.86em;background:var(--sunk);border-radius:2px;padding:.1em .32em}
pre{background:var(--sunk);border:1px solid var(--hair);border-radius:3px;
 padding:.75rem .9rem;overflow-x:auto;margin:0 0 1.2rem;font-size:.82rem;line-height:1.6}
pre code{background:none;padding:0;font-size:inherit}
img{max-width:100%;height:auto;border-radius:2px}
.imglink{font-style:italic}
.fm{margin:0 0 2rem;border:1px dashed var(--rule);border-radius:3px;padding:.5rem .7rem;
 background:var(--ground)}
.fm-t{display:block;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;
 letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin-bottom:.4rem}
.fm pre{margin:0;background:none;border:0;padding:0}
.pt{white-space:pre-wrap}
.tw{overflow-x:auto;margin:0 0 1.2rem}
table{border-collapse:collapse;font-size:.88rem;min-width:100%}
th,td{border:1px solid var(--hair);padding:.4rem .6rem;text-align:left;vertical-align:top}
th{background:var(--sunk);font-weight:600}

.sel-btn{position:absolute;z-index:90;cursor:pointer;background:var(--mark);color:var(--paper);
 font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;letter-spacing:.1em;
 text-transform:uppercase;border-radius:3px;padding:.34rem .6rem;
 box-shadow:0 2px 10px rgba(0,0,0,.22);user-select:none}
.sel-btn span{margin-right:.25rem}
.cmt-pop{position:absolute;z-index:95;width:min(25rem,90vw);background:var(--paper);
 border:1px solid var(--mark);border-radius:3px;box-shadow:0 8px 30px rgba(0,0,0,.24);padding:.75rem}
.cmt-anchor{margin:0 0 .5rem;font-size:.84rem;line-height:1.45;color:var(--ink-2);
 border-left:2px solid var(--mark);padding-left:.6rem;max-height:5.2rem;overflow:auto}
.cmt-pop textarea,.cmt-ta{width:100%;font:inherit;font-size:.9rem;line-height:1.5;padding:.5rem;
 background:var(--sunk);color:var(--ink);border:1px solid var(--rule);border-radius:2px;
 resize:vertical}
.cmt-actions,.cmt-erow{display:flex;align-items:center;gap:.35rem;margin-top:.5rem}
.cmt-where{flex:1;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;
 color:var(--muted);letter-spacing:.06em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cmt-hint{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;color:var(--muted)}
.cmt-ico{width:1.5rem;height:1.5rem;display:inline-flex;align-items:center;justify-content:center;
 border:1px solid var(--rule);border-radius:2px;background:transparent;color:var(--ink-2);
 cursor:pointer;font-size:.82rem;line-height:1;padding:0}
.cmt-ico:hover{border-color:var(--mark);color:var(--mark);background:var(--mark-wash)}
.cmt-ico.is-on{border-color:var(--mark);color:var(--paper);background:var(--mark)}
.cmt-ok{border-color:var(--mark);color:var(--paper);background:var(--mark)}
.cmt-ok:hover{filter:brightness(1.08);color:var(--paper)}

.cmt-hl{background:var(--mark-wash);box-shadow:0 0 0 2px var(--mark-wash);border-radius:1px;
 border-bottom:1px solid var(--mark);color:inherit}
.cmt-sup{display:inline-flex;align-items:center;gap:0;vertical-align:baseline;
 margin:0 .12rem 0 .18rem;white-space:nowrap}
.cmt-num,.cmt-x{font-family:ui-monospace,Menlo,Consolas,monospace;cursor:pointer;
 border:1px solid var(--mark);background:var(--mark-wash);color:var(--mark);
 font-variant-numeric:tabular-nums;line-height:1;padding:0;display:inline-flex;
 align-items:center;justify-content:center;height:1.2rem}
.cmt-num{font-size:0.69rem;min-width:1.25rem;border-radius:2px}
.cmt-x{font-size:.8rem;width:0;min-width:0;opacity:0;overflow:hidden;border-left:0;
 border-radius:0 2px 2px 0;transition:opacity .12s ease,width .12s ease}
.cmt-sup:hover .cmt-num,.cmt-sup:focus-within .cmt-num{border-radius:2px 0 0 2px}
.cmt-sup:hover .cmt-x,.cmt-sup:focus-within .cmt-x{opacity:1;width:1.2rem}
.cmt-num:hover,.cmt-num:focus-visible,.cmt-x:hover,.cmt-x:focus-visible{
 background:var(--mark);color:var(--paper)}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
@media (hover:none){.cmt-x{opacity:1;width:1.2rem}}

.scrim{position:fixed;inset:0;background:rgba(0,0,0,.32);opacity:0;pointer-events:none;
 transition:opacity .2s ease;z-index:80}
.drawer{position:fixed;top:0;right:0;height:100vh;width:min(27rem,92vw);z-index:85;
 background:var(--paper);border-left:2px solid var(--mark);transform:translateX(101%);
 transition:transform .22s ease;display:flex;flex-direction:column}
body.cmt .drawer{transform:none}
body.cmt .scrim{opacity:1;pointer-events:auto}
.dr-top{display:flex;align-items:baseline;gap:.6rem;padding:.8rem 1rem;
 border-bottom:1px solid var(--mark);flex:none}
.dr-title{font-weight:600}
.dr-sub{flex:1;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;
 letter-spacing:.07em;text-transform:uppercase;color:var(--muted);overflow:hidden;
 text-overflow:ellipsis;white-space:nowrap}
.dr-x{display:inline-flex;align-items:center;justify-content:center;width:1.6rem;height:1.6rem;
 padding:0;border:0;background:none;color:var(--muted);cursor:pointer}
.dr-x:hover{color:var(--ink)}
.dr-body{overflow-y:auto;padding:0 1rem 3rem}
.cmt-card{padding:.9rem 0;border-bottom:1px solid var(--hair)}
.cmt-head{display:flex;gap:.55rem;align-items:baseline;margin-bottom:.35rem}
.cmt-idx{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;color:var(--mark);flex:none}
.cmt-loc{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;color:var(--muted);
 letter-spacing:.04em;cursor:pointer;background:none;border:0;padding:0;text-align:left}
.cmt-loc:hover{color:var(--mark);text-decoration:underline}
.cmt-acts{margin-left:auto;display:flex;gap:.15rem;flex:none;align-items:center}
/* A destructive action says what it does and is big enough to mean it. This was
   a 24px unlabelled ✕ beside an identical ✎, which is two glyphs and one
   irreversible outcome. Same control as the margin's, same words. */
.cmt-act{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;letter-spacing:.08em;
 text-transform:uppercase;color:var(--muted);background:none;border:0;cursor:pointer;
 padding:.28rem .4rem;border-radius:2px;min-height:26px}
.cmt-act:hover{color:var(--mark);background:var(--mark-wash)}
.cmt-quote{margin:0 0 .4rem;font-size:.84rem;line-height:1.45;color:var(--ink-2);
 border-left:2px solid var(--mark);padding-left:.6rem}
.cmt-note{margin:0;font-size:.9rem;line-height:1.5;cursor:text;white-space:pre-wrap}
.cmt-empty{color:var(--muted);font-size:.86rem;line-height:1.6;padding:1.4rem 0}
.cmt-fatal{color:var(--mark)}
.cmt-sep{margin:1.1rem 0 .5rem;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;
 letter-spacing:.12em;text-transform:uppercase;color:var(--muted);border-top:1px solid var(--rule);
 padding-top:.6rem}

/* ---------- the comment margin ---------- */
/* The reading column sat centred with ~214px of dead paper either side at
   1440px, and the drawer — the one surface that describes the prose — was laid
   ON TOP of it. An annotation and the sentence it names could not be read at
   once, which is the whole reason this page exists. The right-hand dead paper is
   the margin now, and the column moves off centre to pay for it: 40rem here
   against the 44rem it had, so the measure is 64px narrower when the margin is
   up. Below 1000px the margin folds away and the inline markers carry every
   annotation, so nothing is ever unreachable. */
.wrap{display:grid;grid-template-columns:minmax(0,40rem) minmax(11rem,19rem);
 gap:clamp(1rem,2.5vw,3rem);justify-content:center;align-items:start;padding-top:2.4rem}
.wrap>.col{max-width:none;min-width:0;margin:0;padding-top:0}
.gutter{position:relative}
@media (max-width:999px){
 .wrap{display:block;max-width:44rem;margin:0 auto}
 .gutter{display:none}
}
/* The drawer is a fixed overlay 27rem wide, so on anything narrower than the
   rail plus the column plus the margin plus the drawer, an open drawer lands ON
   the margin — notes rendered, hoverable, and covered. The margin folds away
   instead while the drawer is open. Nothing is lost by that: the two surfaces
   hold the same records, and the drawer is the one the reader just opened.
   Above 1600px they fit side by side, and there the drawer stops being modal —
   the scrim would sit over the margin and swallow every click on it. */
@media (max-width:1599px){
 body.cmt .wrap{display:block;max-width:44rem;margin:0 auto}
 body.cmt .gutter{display:none}
}
@media (min-width:1600px){
 body.cmt .page{padding-right:27rem}
 body.cmt .scrim{opacity:0;pointer-events:none}
}
/* A note stands beside the block it names. Two notes on one block stack: the
   second is pushed below the first and switches to a dashed rule, so a displaced
   note never pretends to be level with its own line. */
.mnote{position:absolute;left:0;width:100%;cursor:pointer;
 padding:.5rem .6rem .55rem .7rem;border-left:2px solid var(--mark);
 background:transparent;border-radius:0 2px 2px 0;
 transition:background .15s ease,top .18s cubic-bezier(.4,0,.2,1)}
.mnote:hover,.mnote.lit{background:var(--mark-wash)}
.mnote.stacked{border-left-style:dashed}
/* Not anchored to a block, so it does not pretend to be: no tie, no number, and
   it sits under the last note rather than beside anything. */
.mnote.mn-lost{border-left-style:dotted;cursor:default}
.mnote.mn-lost:hover{background:transparent}
/* A button centres its own text, and this one wraps to two lines — so the
   sentence sat centred while every other note in the margin is ragged-right. */
.mn-lost .mn-act{padding-left:0;text-transform:none;letter-spacing:.02em;
 font-size:.78rem;color:var(--mark);text-align:left;line-height:1.45}
.mn-lost .mn-act:hover{background:transparent;text-decoration:underline}
.mn-head{display:flex;align-items:baseline;gap:.45rem;margin-bottom:.2rem}
.mn-i{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;
 color:var(--mark);flex:none;font-variant-numeric:tabular-nums}
.mn-note{margin:0;font-size:.88rem;line-height:1.5;color:var(--ink-2);white-space:pre-wrap}
.mnote.lit .mn-note{color:var(--ink)}
.mn-acts{margin-left:auto;display:flex;gap:.1rem;opacity:0;transition:opacity .12s ease}
.mnote:hover .mn-acts,.mnote:focus-within .mn-acts{opacity:1}
@media (hover:none){.mn-acts{opacity:1}}
/* A destructive action says what it does and is big enough to mean it. The
   drawer's delete is a 24px unlabelled glyph beside an identical edit glyph. */
.mn-act{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;letter-spacing:.08em;
 text-transform:uppercase;color:var(--muted);background:none;border:0;cursor:pointer;
 padding:.28rem .4rem;border-radius:2px;min-height:26px}
.mn-act:hover{color:var(--mark);background:var(--paper)}
.mn-tie{position:absolute;left:-2.5rem;top:.85rem;width:2.5rem;height:1px;background:var(--hair)}
.mnote.lit .mn-tie{background:var(--mark)}
.mn-ta{width:100%;font:inherit;font-size:.88rem;line-height:1.5;padding:.4rem .45rem;
 border:1px solid var(--mark);border-radius:3px;background:var(--sunk);color:var(--ink);
 resize:vertical}
.mn-erow{display:flex;gap:.15rem;margin-top:.35rem;align-items:center}
/* Hovering either end lights both. */
.cmt-hl.lit{background:var(--mark);color:var(--paper);box-shadow:0 0 0 2px var(--mark)}
.cmt-card.lit{background:var(--mark-wash)}

/* ---------- state, as a badge rather than a caption ---------- */
/* `unsaved`, `DELETE FAILED` and `EDIT NOT SAVED` were appended to the locator
   line in 10px --muted — the same size and weight as the routine locator they
   were bolted onto, for four states of which three mean the reader's work did
   not reach the file. */
.badge{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;letter-spacing:.09em;
 text-transform:uppercase;padding:.1rem .35rem;border-radius:2px;flex:none;white-space:nowrap}
.b-fail{background:var(--mark);color:var(--paper);font-weight:600}
.b-warn{border:1px solid var(--mark);color:var(--mark);font-weight:600}
.b-info{border:1px solid var(--rule);color:var(--muted)}

/* ---------- undo ---------- */
/* The corpus is append-only, so a deleted record is still on disk. That makes an
   undo cheap, and a delete with no way back inexcusable. */
.undo{position:fixed;left:50%;bottom:1.4rem;transform:translateX(-50%) translateY(1.5rem);
 z-index:120;display:flex;align-items:center;gap:.9rem;opacity:0;pointer-events:none;
 background:var(--ink);color:var(--paper);border-radius:4px;padding:.55rem .75rem .55rem 1rem;
 box-shadow:0 6px 26px rgba(0,0,0,.3);font-family:ui-monospace,Menlo,Consolas,monospace;
 font-size:.75rem;line-height:1.5;max-width:min(34rem,92vw);
 transition:opacity .16s ease,transform .16s ease}
.undo.on{opacity:1;pointer-events:auto;transform:translateX(-50%) translateY(0)}
.undo-b{font:inherit;background:none;border:1px solid var(--paper);border-radius:3px;
 color:var(--paper);cursor:pointer;padding:.2rem .6rem;letter-spacing:.08em;
 text-transform:uppercase;flex:none;min-height:26px}
.undo-b:hover{background:var(--paper);color:var(--ink)}
@media (max-width:900px){
 .col{max-width:none}
 .shell{grid-template-columns:1fr}
 /* The rail stops being a sticky column and becomes a band across the top: a
    13rem column on a narrow screen leaves the document too little to read in,
    which is the one thing this page exists for. */
 .rail{position:static;height:auto;max-height:40vh;border-right:0;
  border-bottom:1px solid var(--rule);display:grid;
  grid-template-columns:repeat(auto-fill,minmax(11rem,1fr));gap:.15rem;padding:.9rem}
 .rail-h,.rail-foot{grid-column:1/-1}
 .rail-item[data-depth]{padding-left:.45rem}
 .bar{flex-wrap:wrap;gap:.5rem}
 .bar-stat{order:9}
}
"""

JS = r"""
const DOC = __DOC__;
const CMT = {list:[], problems:[], err:null, fatal:null, readonly:false, pending:null, el:{
  btn:  document.getElementById('sel-btn'),
  pop:  document.getElementById('cmt-pop'),
  anch: document.getElementById('cmt-anchor'),
  where:document.getElementById('cmt-where'),
  text: document.getElementById('cmt-text'),
  list: document.getElementById('cmt-list'),
  st:   document.getElementById('cmt-status'),
  n:    document.getElementById('cmt-count'),
  open: document.getElementById('cmt-open'),
}};

/* ---- theme ----
   Light is the default, and the system preference is deliberately not consulted:
   the page opens the same way on every machine. Dark is a choice the reader
   makes here, and it is remembered. The root already carries data-theme="light"
   from the renderer, so nothing flashes while this runs. */
(function () {
  const btn = document.getElementById('t-theme');
  let choice = null;
  try { choice = localStorage.getItem('cla-annotate-theme'); } catch (e) {}
  const apply = () => {
    const dark = choice === 'dark';
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
    btn.title = dark ? 'Light theme' : 'Dark theme';
  };
  btn.onclick = () => {
    choice = choice === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem('cla-annotate-theme', choice); } catch (e) {}
    apply();
  };
  apply();
})();

/* ---- the navigation rail ----
   Which entry is lit is decided by an observer over the sections rather than by
   scroll arithmetic, so it stays right when the page reflows — which it does on
   every repaint, because painting an annotation inserts a marker into the prose. */
const RAIL = new Map(
  [...document.querySelectorAll('.rail-item')].map(a => [a.dataset.goSec, a]));

(function () {
  if (!RAIL.size) return;
  const io = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      const a = RAIL.get(e.target.dataset.secId);
      if (!a) return;
      RAIL.forEach(x => x.classList.remove('on'));
      a.classList.add('on');
    });
  }, {rootMargin: '-12% 0px -70% 0px'});
  document.querySelectorAll('.sec').forEach(s => io.observe(s));
  RAIL.forEach(a => a.addEventListener('click', () => {
    RAIL.forEach(x => x.classList.remove('on'));
    a.classList.add('on');
  }));
})();

/* How many open annotations sit in each section. Derived from where the markers
   actually landed rather than from the stored section name: a heading that has
   been retitled since would otherwise leave its annotations uncounted, and the
   rail would say a section was never argued with. */
function paintRailCounts() {
  if (!RAIL.size) return;
  const tally = new Map();
  openOnes().forEach(c => {
    if (!c.blk || c.lost) return;
    const el = document.querySelector('[data-blk="' + CSS.escape(c.blk) + '"]');
    const sec = el && el.closest('.sec');
    if (!sec) return;
    const id = sec.dataset.secId;
    tally.set(id, (tally.get(id) || 0) + 1);
  });
  RAIL.forEach((a, id) => {
    const badge = a.querySelector('.rail-c');
    if (!badge) return;
    const n = tally.get(id) || 0;
    badge.textContent = n;
    badge.hidden = !n;
    badge.title = n === 1 ? '1 annotation' : n + ' annotations';
  });
}

/* ---- the drawer ---- */
/* A closed drawer is translated off-screen, which removes it from view and from
   nothing else: every button inside it stayed in the tab order, so tabbing
   across the page walked an invisible list of edit and delete controls. `inert`
   is what actually takes it out — and it is set here rather than in the CSS
   because it also has to be true before the first click, which the initial call
   below provides. */
function setCmt(on) {
  document.body.classList.toggle('cmt', on);
  CMT.el.open.setAttribute('aria-expanded', String(on));
  const dr = document.getElementById('cdrawer');
  if (dr) { dr.toggleAttribute('inert', !on); dr.setAttribute('aria-hidden', String(!on)); }
  /* Above the wide breakpoint the margin stays up while the drawer is open, so
     both surfaces would render an editor for the same record; below it the
     margin folds away entirely. Either way the answer to "is there a margin"
     changes with the drawer, so opening or closing one is a geometry event.
     Called unguarded: syncMargin is a function declaration and is hoisted, and
     every caller of setCmt runs after load. A `typeof` guard here bought
     nothing and made the call impossible to distinguish, in a test, from a call
     that can never fire. */
  syncMargin();
}
CMT.el.open.onclick = () => setCmt(!document.body.classList.contains('cmt'));
document.getElementById('cd-x').onclick = () => setCmt(false);
document.getElementById('scrim').onclick = () => setCmt(false);
function openList(id) {
  setCmt(true);
  const el = document.getElementById('card-' + id);   // not `card` — that is the renderer
  if (el) el.scrollIntoView({block:'center', behavior:'smooth'});
}

/* Bring a block into view. On a single-document page that is a scroll; on a page
   of several files the tab has to change first, so a multi-file page replaces
   this one function rather than carrying its own copy of the anchor layer. */
window.focusBlock = function (blk) {
  const h = blk ? document.querySelector('[data-blk="' + CSS.escape(blk) + '"]') : null;
  if (!h) return false;
  setCmt(false);
  h.scrollIntoView({block: 'center', behavior: 'smooth'});
  return true;
};

/* Everything the renderer injects that the document does not contain. An
   annotation records the document's characters, so every one of these must come
   out before text is read or offsets are counted — in all three places, from
   this one constant. */
const NON_SOURCE = '__NON_SOURCE__';

function blockText(el) {
  const c = el.cloneNode(true);
  c.querySelectorAll(NON_SOURCE).forEach(s => s.remove());
  return c.textContent;
}

/* Text nodes of a block, with the markers left out. blockText(), the offset
   captured on selection and the offset replayed on paint must all agree about
   what counts as text, or a second annotation in an already-marked block lands
   one character out and reports itself lost. */
function textNodes(host) {
  const w = document.createTreeWalker(host, NodeFilter.SHOW_TEXT, {
    acceptNode: n => n.parentElement && n.parentElement.closest(NON_SOURCE)
      ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT
  });
  const out = []; let n;
  while ((n = w.nextNode())) out.push(n);
  return out;
}

/* Locate a painted selection in the source text of its block. What the browser
   hands back is what is on screen, and that is not always what the block says —
   CSS can transform it and layout can insert breaks the source does not have.
   Four passes, narrowest first — exact, case-folded, whitespace-normalised,
   whitespace-stripped — each returning the SOURCE spelling
   rather than the painted one. One match or none at every pass: guessing files
   an annotation against the wrong sentence while showing text that looks right. */
function findLoose(full, text) {
  const only = (hay, needle) => {
    const a = hay.indexOf(needle);
    return (a < 0 || hay.indexOf(needle, a + 1) >= 0) ? -1 : a;
  };
  let i = only(full, text);
  if (i >= 0) return [i, text];
  i = only(full.toLowerCase(), text.toLowerCase());
  if (i >= 0) return [i, full.substr(i, text.length)];
  const map = []; let norm = '';
  for (let k = 0; k < full.length; k++) {
    const ws = /\s/.test(full[k]);
    if (ws && norm.endsWith(' ')) continue;
    norm += ws ? ' ' : full[k];
    map.push(k);
  }
  const nt = text.replace(/\s+/g, ' ').trim().toLowerCase();
  if (!nt) return null;
  let j = only(norm.toLowerCase(), nt);
  if (j >= 0) {
    const start = map[j];
    const end = map[Math.min(j + nt.length - 1, map.length - 1)];
    return [start, full.slice(start, end + 1)];
  }
  const tmap = []; let tight = '';
  for (let k = 0; k < full.length; k++) {
    if (/\s/.test(full[k])) continue;
    tight += full[k]; tmap.push(k);
  }
  const tt = text.replace(/\s+/g, '').toLowerCase();
  if (!tt) return null;
  j = only(tight.toLowerCase(), tt);
  if (j < 0) return null;
  const ts = tmap[j];
  const te = tmap[Math.min(j + tt.length - 1, tmap.length - 1)];
  return [ts, full.slice(ts, te + 1)];
}

function captureSelection() {
  const sel = window.getSelection();
  if (!sel || sel.isCollapsed) return null;
  if (sel.toString().trim().length < 2) return null;
  const rng = sel.getRangeAt(0);
  const el = n => n && (n.nodeType === 1 ? n : n.parentElement);
  /* Anchor to the block the selection starts in, or the nearest one enclosing
     it, and keep only the part of the selection inside that block. A selection
     running across a paragraph break ends in the next one, and requiring both
     ends in the same block returned nothing at all. */
  let host = el(rng.startContainer).closest('[data-blk]')
          || el(rng.commonAncestorContainer).closest('[data-blk]');
  if (!host) return null;

  /* The text is taken from the range's own contents, clipped to the block and
     with the markers stripped — never from sel.toString(). A block that already
     carries an annotation has a marker inside it, and the selection swallows the
     marker's digits, so the captured string is not a substring of the block and
     no amount of matching will find it. */
  const clip = rng.cloneRange();
  if (!host.contains(rng.startContainer)) clip.setStart(host, 0);
  if (!host.contains(rng.endContainer)) clip.setEnd(host, host.childNodes.length);
  const box = document.createElement('div');
  box.appendChild(clip.cloneContents());
  box.querySelectorAll(NON_SOURCE).forEach(x => x.remove());
  let text = box.textContent.trim();
  if (text.length < 2) return null;
  const full = blockText(host);
  let off = -1, seen = 0;
  for (const n of textNodes(host)) {
    if (n === rng.startContainer) { off = seen + rng.startOffset; break; }
    seen += n.nodeValue.length;
  }
  if (off < 0 || full.substr(off, text.length) !== text) {
    const hit = findLoose(full, text);
    if (!hit) return null;
    off = hit[0]; text = hit[1];
  }
  return {
    blk: host.dataset.blk,
    line: Number(host.dataset.line) || 0,
    sec: host.dataset.sec || '',
    /* Which file the passage came from, read off the enclosing pane. Empty on a
       single-document page, which has no panes — the field costs nothing there
       and is the whole address on a page holding a change's four files. */
    file: (host.closest('[data-pane]') || {dataset: {}}).dataset.pane || '',
    off, text,
    /* Sixty characters is the authoritative figure and it is set here. The
       replay uses the inner 24 to bracket the passage; the far context usually
       survives an edit and what is immediately around the selection usually
       does not. Anything quoting "sixty" elsewhere is quoting this. */
    before: full.slice(Math.max(0, off - 60), off),
    after:  full.slice(off + text.length, off + text.length + 60),
  };
}

document.addEventListener('mouseup', e => {
  if (e.target.closest('#cmt-pop') || e.target.closest('#sel-btn')
      || e.target.closest('.drawer')) return;
  /* While the popup is open it is QUOTING the pending passage. Letting a new
     selection replace `pending` underneath it filed the note against a passage
     the reader was not looking at — and the stored record is self-consistent, so
     nothing downstream could ever notice. */
  if (!CMT.el.pop.hidden) return;
  const cap = captureSelection();
  const b = CMT.el.btn;
  if (!cap) { b.hidden = true; return; }
  const r = window.getSelection().getRangeAt(0).getBoundingClientRect();
  b.style.left = (window.scrollX + r.left) + 'px';
  b.style.top  = (window.scrollY + r.bottom + 8) + 'px';
  b.hidden = false;
  CMT.pending = cap;
});

CMT.el.btn.addEventListener('mousedown', e => {
  e.preventDefault();
  const cap = CMT.pending; if (!cap) return;
  const b = CMT.el.btn, p = CMT.el.pop;
  b.hidden = true;
  p.style.left = Math.min(parseFloat(b.style.left), window.scrollX + innerWidth - 420) + 'px';
  p.style.top  = b.style.top;
  p.hidden = false;
  CMT.el.anch.textContent = '"' + cap.text + '"';
  CMT.el.where.textContent = (cap.sec || DOC) + ' · line ' + cap.line;
  CMT.el.text.value = '';
  CMT.el.text.focus();
});

function closePop() { CMT.el.pop.hidden = true; CMT.el.btn.hidden = true; CMT.pending = null; }
document.getElementById('cmt-cancel').onclick = closePop;
/* One Escape handler, and the innermost thing wins. Editing is checked first and
   from the LIST rather than from the focused element: the note being edited is
   the most recent thing opened, and cancelling it must work whether focus is
   still in the textarea or the reader has clicked away — otherwise Escape
   closes the whole drawer over an open edit, which loses the same keystrokes it
   was pressed to discard.

   Cancelling changes nothing. The textarea is re-rendered from `c.note` on every
   render and `c.note` is only ever written by editNote(), so dropping out of edit
   mode restores the stored wording by construction rather than by an undo. */
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  const editing = CMT.list.find(c => c.editing);
  if (editing) { editing.editing = false; render(); return; }
  if (!CMT.el.pop.hidden) return closePop();
  if (document.body.classList.contains('cmt')) setCmt(false);
});

async function submit() {
  const cap = CMT.pending, note = CMT.el.text.value.trim();
  if (!cap || !note) return closePop();
  if (CMT.readonly) {
    /* Refusing the write is right; discarding what was typed is not. The note
       goes into the list as unsaved, which the card and the counter already
       know how to show. */
    closePop();
    CMT.list.push(Object.assign({note, doc: DOC, unsaved: true,
                                 id: localId()}, cap));
    return render();
  }
  closePop();
  await postAnnotation(Object.assign({note, doc: DOC}, cap));
}
document.getElementById('cmt-save').onclick = () => submit();
CMT.el.text.addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') submit();
});

/* Never `CMT.list.length`: it is reused after a delete, and two records sharing
   an id means find() returns the first while filter() removes both. */
let LOCAL_N = 0;
function localId() { return 'local-' + (++LOCAL_N) + '-' + Date.now(); }

async function postAnnotation(rec) {
  try {
    const r = await fetch('/api/annotations', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(rec)
    });
    if (!r.ok) {
      /* A refused write is not an absent server, and saying so is the only
         message that tells the reader what to fix. */
      let msg = 'HTTP ' + r.status;
      try { msg = (await r.json()).error || msg; } catch (e) {}
      throw new Error(msg);
    }
    const j = await r.json();
    if (j.record) Object.assign(rec, j.record);   // adopt what was actually stored
    rec.id = j.id || rec.id;
    rec.unsaved = false;
    CMT.err = null;
  } catch (err) {
    rec.id = rec.id || localId();
    rec.unsaved = true;
    CMT.err = String(err.message || err);
  }
  CMT.list.push(rec);
  render();
}

/* Nothing leaves the list until the tombstone lands. Removing the card first and
   swallowing the error means watching an annotation vanish while it stays live
   in the corpus. */
async function del(id) {
  const rec = CMT.list.find(c => c.id === id); if (!rec) return;
  if (rec.unsaved && String(rec.id).startsWith('local-')) {
    /* A local- id means postComment's catch fired, which happens for a lost
       response as well as a failed write — so this record MAY be on the file
       under a server id. Dropping it from the page is still right, because the
       page has no id the server would accept; the strip says what is actually
       known rather than claiming a clean removal. */
    CMT.list = CMT.list.filter(c => c.id !== id);
    undoBar(true, 'Removed from this page. It was never confirmed saved, so it'
                + ' may still be in the annotations file.', null);
    clearTimeout(undoT);
    undoT = setTimeout(hideUndo, 9000);
    return render();
  }
  rec.deleting = true;
  /* A retry must not look identical to the failure it is retrying: stateBadge
     tests delFailed first, so leaving it set shows "delete failed" over an
     in-flight second attempt. */
  rec.delFailed = false;
  render();
  rec.wasAt = CMT.list.indexOf(rec);          // so undo can put it back in place
  try {
    const r = await fetch('/api/annotations', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id, deleted: true})});
    if (!r.ok) {
      /* The server distinguishes an unreadable corpus from a failed write from a
         refused amendment, and says which in the body. Throwing the status alone
         drops the one sentence naming what to fix. */
      let msg = 'HTTP ' + r.status;
      try { msg = (await r.json()).error || msg; } catch (e) {}
      throw new Error(msg);
    }
    CMT.list = CMT.list.filter(c => c.id !== id);
    CMT.err = null;
    /* The corpus is append-only, so the record is still on disk and the undo is
       one POST. A delete with no way back, from an unlabelled 24px glyph, is
       not a thing this page should offer. */
    offerUndo(rec);
  } catch (e) {
    rec.deleting = false;
    rec.delFailed = String(e.message || e);
    CMT.err = 'delete failed: ' + rec.delFailed;
  }
  render();
}

/* Editing a note is an amendment, not a new annotation: the same id with a new
   `note`, appended. The store merges later lines onto earlier ones and never
   overwrites `at`, so the record keeps when the objection was made and the file
   keeps every wording the note has had. Nothing is rewritten in place. */
async function editNote(id, note) {
  const rec = CMT.list.find(c => c.id === id); if (!rec) return;
  note = (note || '').trim();
  /* An emptied note is not a no-op the reader meant, and discarding it in
     silence is indistinguishable from a save. The store has no way to record
     "no note" — that is what deleting is for — so it is refused out loud.

     The refusal rides on the RECORD, not on CMT.err, and the editor stays open.
     CMT.err renders only into #cmt-status, which lives inside the drawer, and
     the whole point of the margin is that the reader now works with the drawer
     closed — so a message sent there is a message nobody reads. And an editor
     that closes on a refusal looks exactly like an editor that saved. */
  if (!note) {
    rec.editFailed = 'an annotation cannot have an empty note — delete it instead';
    return render();
  }
  rec.editing = false;
  /* `!rec.editFailed` is what makes a retry possible at all. `rec.note` is set
     optimistically below, so after a failed POST the record already holds the
     text the reader typed — reopening the editor prefills it, and Save then hit
     `note === rec.note` and returned with no POST, no message and the badge
     unchanged. The reader was retrying a failed save and the page did nothing,
     forever, unless they thought to alter a character. del() was given exactly
     this fix and editNote was not. */
  if (note === rec.note && !rec.editFailed) return render();   // nothing to record
  rec.note = note;
  /* Cleared at the START of the attempt, so an in-flight retry does not wear the
     badge of the failure it is retrying. Same rule as del()'s delFailed. */
  rec.editFailed = false;                    // before the POST, not after it
  if (rec.unsaved && String(rec.id).startsWith('local-')) return render();
  render();
  try {
    const r = await fetch('/api/annotations', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id, note, edited: true})});
    if (!r.ok) {
      let msg = 'HTTP ' + r.status;
      try { msg = (await r.json()).error || msg; } catch (e) {}
      throw new Error(msg);
    }
    rec.editFailed = false;
    CMT.err = null;
  } catch (e) {
    /* The new wording stays on screen rather than being rolled back — throwing
       away what was just typed is a worse failure than an unsaved one, and the
       badge says which it is. The MESSAGE is carried on the record, not only in
       CMT.err: CMT.err renders inside the drawer, and with the margin up the
       drawer is closed. */
    rec.editFailed = String(e.message || e);
    CMT.err = 'edit failed: ' + rec.editFailed;
  }
  render();
}

/* ---- paint anchors back into the prose ---- */
/* extractContents splits an inline element when a range ends inside one, and
   unwrapping the highlight does not put the halves back together. Covers every
   inline the renderer emits — em, strong, code, del and a — and compares href so
   that two different links are never welded into one. */
function mergeSplitInline(root) {
  root.querySelectorAll('em, strong, code, del, a').forEach(el => {
    let next = el.nextSibling;
    while (next && next.nodeType === 1 && next.tagName === el.tagName
           && next.className === el.className
           && next.getAttribute('href') === el.getAttribute('href')) {
      while (next.firstChild) el.appendChild(next.firstChild);
      const dead = next;
      next = next.nextSibling;
      dead.remove();
    }
    el.normalize();
  });
}

function clearMarks() {
  document.querySelectorAll('.cmt-sup').forEach(s => s.remove());
  document.querySelectorAll('mark.cmt-hl').forEach(m => {
    const p = m.parentNode; while (m.firstChild) p.insertBefore(m.firstChild, m);
    p.removeChild(m); p.normalize();
  });
  mergeSplitInline(document.getElementById('doc'));
}

/* A resolved annotation is deliberately not painted: its text has gone from the
   document *because* something replaced it, so chasing its anchor would report
   ANCHOR LOST on every one already dealt with. */
function openOnes() { return CMT.list.filter(c => !c.resolved); }
function doneOnes() { return CMT.list.filter(c => c.resolved); }

/* The inner 24 characters either side. */
function needleOf(c) {
  return {lead: (c.before || '').slice(-24), tail: (c.after || '').slice(0, 24)};
}

/* Block ids are ordinals, so inserting one paragraph renumbers every block after
   it and every open annotation below the insertion stops finding its own block.
   The stored id is tried first; when it is gone — or now holds something else —
   the annotation is relocated by its text and the context either side, and only
   when exactly one block matches. An ambiguous match is left lost, which is the
   honest answer. */
function hostFor(c) {
  const byId = c.blk ? document.querySelector('[data-blk="' + CSS.escape(c.blk) + '"]') : null;
  if (byId && blockText(byId).indexOf(c.text) >= 0) return byId;
  const n = needleOf(c), full = n.lead + c.text + n.tail;
  const hits = [...document.querySelectorAll('[data-blk]')]
    .filter(el => blockText(el).indexOf(full) >= 0);
  if (hits.length === 1) { c.blk = hits[0].dataset.blk; c.line = Number(hits[0].dataset.line) || c.line; return hits[0]; }
  if (hits.length > 1) return null;
  return byId || null;
}

/* Where the anchor sits inside the block it was found in. The stored offset was
   counted against an older render, so it is trusted only when the text is
   actually there; otherwise the context brackets it, and a passage appearing
   twice in one block is left to the stored offset rather than guessed at. */
function offsetOf(c, host) {
  const t = blockText(host), n = needleOf(c);
  if (t.substr(c.off, c.text.length) === c.text) return c.off;
  const withCtx = t.indexOf(n.lead + c.text + n.tail);
  if (withCtx >= 0) return withCtx + n.lead.length;
  const bare = t.indexOf(c.text);
  return bare >= 0 && t.indexOf(c.text, bare + 1) < 0 ? bare : c.off;
}

/* Where the anchor starts and ends, as a range that may cross text nodes: an
   anchor spanning <em>, <code> or a link lives in two nodes or more, and
   requiring one node reported ANCHOR LOST for text sitting untouched. */
function rangeFor(host, off, text) {
  const nodes = textNodes(host);
  const total = nodes.reduce((n, x) => n + x.nodeValue.length, 0);
  /* A stored offset comes out of a committed, hand-editable file. A negative one
     throws IndexSizeError out of setStart, out of paint and out of render,
     leaving the drawer empty over a fully loaded corpus. */
  if (!(off >= 0) || off + text.length > total) return null;
  let seen = 0, start = null, end = null, got = '';
  for (const n of nodes) {
    const len = n.nodeValue.length;
    if (start === null && seen + len > off) start = [n, off - seen];
    if (start !== null) {
      const a = (n === start[0]) ? start[1] : 0;
      const b = Math.min(len, off + text.length - seen);
      if (b > a) got += n.nodeValue.slice(a, b);
      if (seen + len >= off + text.length) { end = [n, off + text.length - seen]; break; }
    }
    seen += len;
  }
  if (!start || !end) return null;
  /* Compared against what textNodes actually walked, never against
     range.toString(): toString concatenates every text node between the
     boundaries, including the markers textNodes filtered out. */
  if (got !== text) return null;
  const r = document.createRange();
  r.setStart(start[0], start[1]);
  r.setEnd(end[0], end[1]);
  return r;
}

/* Whether the last paint() ran with a margin or without one. paint() chooses
   between a margin note and an inline marker, so when that answer changes the
   page has to be REPAINTED, not merely re-laid-out. Null until the first paint,
   so the first sync after load always repaints. */
let paintedMarginOff = null;

function paint() {
  clearMarks();
  paintedMarginOff = marginOff();
  openOnes().forEach((c, i) => {
    c.idx = i + 1;
    c.mark = null;
    c.paintFailed = false;
    const host = hostFor(c);
    if (!host) { c.lost = true; return; }
    c.off = offsetOf(c, host);
    const r = rangeFor(host, c.off, c.text);
    if (!r) { c.lost = true; return; }
    const m = document.createElement('mark');
    m.className = 'cmt-hl';
    try {
      /* extract-and-insert rather than surroundContents, which throws the moment
         a range partially selects an element. The fragment is held so a failed
         insert can put the prose back: extractContents has already removed it
         from the document by then. */
      m.appendChild(r.extractContents());
      r.insertNode(m);
    } catch (e) {
      /* Put ALL of it back, not just the first node: a fragment spanning <em> or
         <code> has several children, and restoring one silently drops the rest —
         the block's text then differs from the document, and its neighbours
         start reporting themselves lost against a file nobody touched. And say
         so rather than swallowing: an empty catch here loses a clause of the
         prose the reader is annotating. */
      if (!m.parentNode) {
        try { while (m.firstChild) r.insertNode(m.lastChild); }
        catch (e2) {
          CMT.err = 'a passage could not be repainted — press Rebuild;'
                  + ' the corpus is untouched';
        }
      }
      /* Distinct from `lost`, and both are set. Reporting only ANCHOR LOST told
         the reader their document had moved — for an annotation whose text is
         exactly where it was. This one is a fault in the page, not in the
         corpus, and it is the only state here the reader can do nothing about
         except rebuild. */
      c.paintFailed = true;
      c.lost = true;
      return;
    }
    c.lost = false;
    c.mark = m;
    m.dataset.cmt = c.id;
    m.onmouseenter = () => lite(c.id, true);
    m.onmouseleave = () => lite(c.id, false);
    /* The inline marker is what the margin replaces. It stays for the widths
       where there is no margin — a phone, a narrow window — so no annotation is
       ever unreachable. syncMargin() is what keeps that true across a resize. */
    if (paintedMarginOff) {
      const sup = document.createElement('sup');
      sup.className = 'cmt-sup';
      const num = document.createElement('button');
      num.className = 'cmt-num'; num.textContent = String(i + 1);
      num.title = c.note; num.setAttribute('aria-label', 'annotation ' + (i + 1));
      num.onclick = e => { e.stopPropagation(); openList(c.id); };
      const x = document.createElement('button');
      x.className = 'cmt-x'; x.textContent = '×';
      x.title = 'delete this annotation';
      x.setAttribute('aria-label', 'delete annotation ' + (i + 1));
      x.onclick = e => { e.stopPropagation(); del(c.id); };
      sup.append(num, x);
      m.after(sup);
    }
  });
  layoutMargin();
}

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

/* ---- the annotation margin ---- */
const GUTTER = document.getElementById('gutter');
function marginOff() {
  return !GUTTER || getComputedStyle(GUTTER).display === 'none';
}

/* The drawer being open decides which surface owns editing. */
function drawerOpen() { return document.body.classList.contains('cmt'); }

/* The ONE entry point for "the geometry moved". Every reading control that
   changes the FLOW has to come through here — not just a resize. On the change
   page, switching tabs and hiding the counterparts both move every block by
   hundreds of pixels, and margin tops are absolute pixels computed once. Nothing
   re-laid them out, so a toggle left every note beside a different sentence with
   its tie still drawn SOLID, which is this page's promise that the note is level
   with its own line. Repaint when the margin has appeared or disappeared;
   otherwise just move the notes. */
function syncMargin() {
  if (marginOff() !== paintedMarginOff) render();
  else layoutMargin();
}

/* Light the note and its anchor together, from whichever end was touched. */
function lite(id, on) {
  document.querySelectorAll('[data-cmt="' + CSS.escape(id) + '"]')
    .forEach(el => el.classList.toggle('lit', on));
  const card = document.getElementById('card-' + id);
  if (card) card.classList.toggle('lit', on);
}

function layoutMargin() {
  if (!GUTTER) return;
  GUTTER.textContent = '';
  GUTTER.style.height = '';
  if (marginOff()) return;
  const top0 = GUTTER.getBoundingClientRect().top + window.scrollY;
  let floor = -Infinity;
  /* `isConnected` is not the test. On a change page every file is in the
     document at once and only the showing tab is displayed, so a mark in a
     hidden pane is connected, has a zero-sized rect, and produced a note pinned
     at the top of the margin beside nothing — measured at top:-135.78px while
     the tasks tab was showing and the note belonged to the proposal.
     getClientRects() is empty for a `display:none` subtree, which is the
     question actually being asked: is this mark on screen. */
  openOnes().filter(c => !c.lost && c.mark && c.mark.getClientRects().length).forEach(c => {
    const el = document.createElement('div');
    el.className = 'mnote';
    el.tabIndex = 0;
    el.dataset.cmt = c.id;
    el.innerHTML =
      '<span class="mn-tie"></span>'
      + '<div class="mn-head"><span class="mn-i">' + c.idx + '</span>' + stateBadge(c)
      + '<span class="mn-acts">'
      + '<button class="mn-act" data-medit="' + esc(c.id) + '">Edit</button>'
      + '<button class="mn-act" data-mdel="' + esc(c.id) + '">Delete</button>'
      + '</span></div>'
      /* ONE editor at a time. Above the wide breakpoint the margin is not hidden
         while the drawer is open, so both surfaces would render a textarea for
         the same c.editing, each prefilled from c.note — and saving from the
         drawer would read ITS stale textarea, match `note === rec.note`, and
         repaint the old wording with no message. The drawer owns editing
         whenever it is open. */
      + (c.editing && !drawerOpen()
          ? '<textarea class="mn-ta" rows="3" data-med="' + esc(c.id) + '">' + esc(c.note) + '</textarea>'
            + '<div class="mn-erow"><button class="mn-act" data-mesave="' + esc(c.id) + '">Save</button>'
            + '<button class="mn-act" data-mecancel="' + esc(c.id) + '">Cancel</button></div>'
          : '<p class="mn-note">' + esc(c.note) + '</p>');
    GUTTER.appendChild(el);
    /* Anchored to the marked block, then pushed clear of the note above it. A
       pushed note switches to a dashed rule: it is no longer level with its own
       line and should not say that it is. */
    let top = c.mark.getBoundingClientRect().top + window.scrollY - top0 - 6;
    if (top < floor + 8) { top = floor + 8; el.classList.add('stacked'); }
    el.style.top = top + 'px';
    floor = top + el.offsetHeight;
    el.onmouseenter = () => lite(c.id, true);
    el.onmouseleave = () => lite(c.id, false);
    el.addEventListener('focus', () => lite(c.id, true));
    el.addEventListener('blur', () => lite(c.id, false));
  });
  /* An annotation whose passage the document no longer has cannot stand beside a
     block, and paint() gives it no inline marker either — so with the drawer
     closed it was on NO surface the reader had open. The margin says how many
     and opens the drawer. */
  const lostN = openOnes().filter(c => c.lost).length;
  if (lostN) {
    const note = document.createElement('div');
    note.className = 'mnote mn-lost';
    note.style.top = (floor > -Infinity ? floor + 24 : 0) + 'px';
    note.innerHTML =
      '<p class="mn-note"><button class="mn-act" id="mn-lost-b">'
      + (lostN === 1
          ? '1 annotation has lost its place in the document'
          : lostN + ' annotations have lost their place in the document')
      + ' →</button></p>';
    GUTTER.appendChild(note);
    note.querySelector('#mn-lost-b').onclick = () => setCmt(true);
    floor = (floor > -Infinity ? floor + 24 : 0) + note.offsetHeight;
  }
  GUTTER.style.height = (floor > -Infinity ? floor + 40 : 0) + 'px';

  GUTTER.querySelectorAll('[data-mdel]').forEach(bn =>
    bn.onclick = e => { e.stopPropagation(); del(bn.dataset.mdel); });
  GUTTER.querySelectorAll('[data-medit]').forEach(bn =>
    bn.onclick = e => {
      e.stopPropagation();
      const c = CMT.list.find(x => x.id === bn.dataset.medit); if (!c) return;
      CMT.list.forEach(x => { x.editing = (x === c); });
      render();
      /* With the drawer open the margin renders no textarea, so focus has to
         follow the editor to the surface that actually has it — otherwise Edit
         looks like it did nothing. */
      const t = GUTTER.querySelector('[data-med]')
             || CMT.el.list.querySelector('[data-ed="' + CSS.escape(c.id) + '"]');
      if (t) { t.focus(); t.setSelectionRange(t.value.length, t.value.length); }
    });
  GUTTER.querySelectorAll('[data-mecancel]').forEach(bn =>
    bn.onclick = e => {
      e.stopPropagation();
      const c = CMT.list.find(x => x.id === bn.dataset.mecancel);
      if (c) { c.editing = false; render(); }
    });
  GUTTER.querySelectorAll('[data-mesave]').forEach(bn =>
    bn.onclick = e => {
      e.stopPropagation();
      const t = GUTTER.querySelector('[data-med="' + CSS.escape(bn.dataset.mesave) + '"]');
      /* A missing textarea is a DOM fault, not an empty note. Feeding '' to
         editNote makes the two indistinguishable and throws away what the reader
         typed. */
      if (!t) { CMT.err = 'the editor went missing; nothing was saved'; return render(); }
      editNote(bn.dataset.mesave, t.value);
    });
  GUTTER.querySelectorAll('[data-med]').forEach(t => t.onkeydown = e => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); editNote(t.dataset.med, t.value); }
    if (e.key === 'Escape') {
      const c = CMT.list.find(x => x.id === t.dataset.med);
      if (c) { c.editing = false; render(); }
    }
  });
}

/* State as a badge. More than one can be true at once — a failed undo and then a
   failed edit — so the worst is shown and the rest are counted rather than
   dropped. `lost` is deliberately absent: the drawer card marks it and the
   margin's foot counts it, because it is information, not a failure. */
/* Each entry is [class, label, detail]. The label is what the badge prints and
   stays short enough to sit in a margin note's head; the detail is the server's
   own sentence naming what to fix, and it goes in the title alongside every
   other state that is true at once. Three of the flags carry a message string
   rather than `true`, because with the margin up the drawer is closed and
   CMT.err — which is where those sentences used to go — is inside it. */
function stateBadge(c) {
  const all = [];
  const detail = v => (typeof v === 'string' && v) ? v : '';
  if (c.paintFailed) all.push(['b-fail', 'could not be marked', '']);
  if (c.undoFailed)  all.push(['b-fail', 'undo not confirmed', detail(c.undoFailed)]);
  if (c.delFailed)   all.push(['b-fail', 'delete failed', detail(c.delFailed)]);
  if (c.editFailed)  all.push(['b-fail', 'edit not saved', detail(c.editFailed)]);
  if (c.unsaved)     all.push(['b-warn', 'not saved', '']);
  if (c.deleting)    all.push(['b-info', 'deleting…', '']);
  if (!all.length) return '';
  const more = all.length > 1 ? ' +' + (all.length - 1) : '';
  const title = all.map(x => x[2] ? x[1] + ' — ' + x[2] : x[1]).join(', ');
  return '<span class="badge ' + all[0][0] + '" title="' + esc(title) + '">'
       + all[0][1] + more + '</span>';
}

let marginT;
addEventListener('resize', () => { clearTimeout(marginT); marginT = setTimeout(syncMargin, 120); });

/* ---- undo ---- */
const UNDO = {
  bar:  document.getElementById('undo'),
  text: document.getElementById('undo-t'),
  btn:  document.getElementById('undo-b'),
};

/* opacity:0 does not remove a button from the tab order, and a handler holding
   its closure over the deleted record would let a keyboard user fire an
   un-delete long after the window closed. */
function undoBar(on, msg, onClick, label) {
  UNDO.text.textContent = msg || '';
  UNDO.btn.textContent = label || 'Undo';
  UNDO.btn.onclick = onClick || null;
  /* An informational strip has no action, and two call sites pass none: the
     local- delete, and the in-flight "Restoring…" state. The button used to
     render anyway — visible, focusable, labelled "Undo", and doing nothing, for
     the full nine seconds. A dead control is worse than an absent one, because
     it advertises a recovery that does not exist, and it advertised it hardest
     to the reader who had just destroyed the only copy of their own words.
     `hidden`, not opacity, for the same reason the bar itself is `inert`. */
  UNDO.btn.hidden = !onClick;
  UNDO.bar.classList.toggle('on', !!on);
  UNDO.bar.toggleAttribute('inert', !on);
  UNDO.bar.setAttribute('aria-hidden', String(!on));
}
let undoT;
function hideUndo() { clearTimeout(undoT); undoBar(false); }

/* A record's own name, for a strip read in a hurry. `idx` is assigned in paint()
   and a lost-anchor annotation still gets one, but a record deleted before the
   first paint has none. */
function nameOf(rec) {
  if (rec.idx) return 'Annotation ' + rec.idx;
  return rec.line ? ('The annotation on line ' + rec.line) : 'That annotation';
}

function offerUndo(rec) {
  undoBar(true, nameOf(rec) + ' deleted.', () => undoDelete(rec));
  clearTimeout(undoT);
  undoT = setTimeout(hideUndo, 7000);
}

async function undoDelete(rec) {
  clearTimeout(undoT);
  /* The strip stays up THROUGH the POST, saying what it is doing. Dismissing it
     first is what sends the failure to a panel nobody has open. */
  undoBar(true, 'Restoring ' + nameOf(rec).toLowerCase() + '…', null);
  delete rec.deleted; delete rec.deleting; delete rec.delFailed;
  delete rec.undoFailed;
  /* Back where it was, not re-sorted: sorting would renumber the whole list and
     put it out of step with the file's own order.

     Guarded, because the catch below leaves `rec` IN the list and re-arms the
     strip with this same function and this same object. A retry after a failed
     undo therefore ran this line a second time and spliced one record in twice:
     two margin notes, the second marked `.stacked` as though it were a separate
     annotation on the same block, two drawer cards sharing one DOM id, and a
     header count one too high — with no error anywhere. The page invented an
     annotation. Every further retry added another. */
  if (CMT.list.indexOf(rec) < 0) {
    const at = typeof rec.wasAt === 'number' ? rec.wasAt : CMT.list.length;
    CMT.list.splice(Math.min(at, CMT.list.length), 0, rec);
  }
  render();
  try {
    const r = await fetch('/api/annotations', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: rec.id, deleted: false})});
    if (!r.ok) {
      let msg = 'HTTP ' + r.status;
      try { msg = (await r.json()).error || msg; } catch (e2) {}
      throw new Error(msg);
    }
    CMT.err = null;
    hideUndo();
  } catch (e) {
    /* NOT "still deleted". This catch fires for a refused write AND for a lost
       response — a killed server, a slept laptop, a reset socket — and in the
       second case the tombstone may well have been lifted. Asserting the file's
       state is something the client cannot do from here, and `del()`'s local-
       branch already reasons this way about the same ambiguity. What is true in
       both cases is that the undo was not confirmed. */
    rec.undoFailed = String(e.message || e);
    CMT.err = 'undo not confirmed: ' + rec.undoFailed;
    undoBar(true, 'Undo could not be confirmed — reload to see the file. '
                + rec.undoFailed, () => undoDelete(rec), 'Retry');
  }
  render();
}

/* Hoisted out of render(): the fatal branch renders unsaved cards too, and it
   runs before render()'s own declarations. A function declaration hoists; a
   const does not, and referencing it early is a ReferenceError. */
const card = (c, i) => '<div class="cmt-card" id="card-' + c.id + '" data-id="' + c.id + '">'
    + '<div class="cmt-head">'
    + '<span class="cmt-idx">' + (i + 1) + '</span>'
    + '<button class="cmt-loc" data-go="' + c.id + '">'
    /* On a change, which FILE an annotation is on outranks which section: the
       reader is deciding whether to switch tabs. */
    + esc(c.file ? c.file + (c.sec ? ' · ' + c.sec : '') : (c.sec || DOC))
    + ' · line ' + (c.line || '?')
    /* ANCHOR LOST stays on the locator: it describes WHERE the annotation is,
       which is the locator's job, and it is information rather than a failure.
       The three states that mean the reader's work did not reach the file are
       badges — they were 10px --muted suffixes on this same line, the same size
       and weight as the routine locator they were bolted onto. */
    + (c.lost ? ' · ANCHOR LOST' : '')
    + '</button>'
    + stateBadge(c)
    + '<span class="cmt-acts">'
    + '<button class="cmt-ico' + (c.editing ? ' is-on' : '') + '" data-edit="' + c.id + '"'
    + ' title="edit this note" aria-label="edit annotation ' + (i + 1) + '">✎</button>'
    + (c.editing ? '' : '<button class="cmt-act" data-del="' + c.id + '"'
        + ' title="delete this annotation" aria-label="delete annotation ' + (i + 1)
        + '">Delete</button>')
    + '</span></div>'
    + '<p class="cmt-quote">' + esc(c.text) + '</p>'
    + (c.editing
        ? '<textarea class="cmt-ta" rows="4" data-ed="' + c.id + '">' + esc(c.note) + '</textarea>'
          + '<div class="cmt-erow">'
          + '<button class="cmt-ico cmt-ok" data-esave="' + c.id + '" title="save this note">✓</button>'
          + '<button class="cmt-ico" data-ecancel="' + c.id + '" title="discard the change">✕</button>'
          + '<span class="cmt-hint">⌘/ctrl+enter</span></div>'
        : '<p class="cmt-note" title="click to edit">' + esc(c.note) + '</p>')
    + '</div>';

function wireCards() {
  CMT.el.list.querySelectorAll('[data-del]').forEach(b => b.onclick = () => del(b.dataset.del));
  CMT.el.list.querySelectorAll('[data-edit]').forEach(b => b.onclick = () => {
    const c = CMT.list.find(x => x.id === b.dataset.edit); if (!c) return;
    CMT.list.forEach(x => { if (x !== c) x.editing = false; });
    c.editing = !c.editing;
    render();
    const t = CMT.el.list.querySelector('[data-ed]');
    if (t) { t.focus(); t.setSelectionRange(t.value.length, t.value.length); }
  });
  CMT.el.list.querySelectorAll('[data-ecancel]').forEach(b => b.onclick = () => {
    const c = CMT.list.find(x => x.id === b.dataset.ecancel);
    if (c) { c.editing = false; render(); }
  });
  CMT.el.list.querySelectorAll('[data-esave]').forEach(b => b.onclick = () => {
    const t = CMT.el.list.querySelector('[data-ed="' + CSS.escape(b.dataset.esave) + '"]');
    editNote(b.dataset.esave, t ? t.value : '');
  });
  // Escape is deliberately NOT handled here — it bubbles to the one handler
  // above, so cancelling behaves the same whether focus is in this textarea or
  // anywhere else on the page.
  CMT.el.list.querySelectorAll('[data-ed]').forEach(t => t.onkeydown = e => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); editNote(t.dataset.ed, t.value); }
  });
  // Clicking the card opens the note for editing. Buttons keep their own jobs
  // (delete, and the location line that scrolls to the passage), and a click
  // inside the open textarea must not toggle the edit it is part of.
  CMT.el.list.querySelectorAll('.cmt-card').forEach(el => el.onclick = e => {
    if (e.target.closest('button, textarea, a')) return;
    const c = CMT.list.find(x => x.id === el.dataset.id);
    if (!c || c.editing) return;
    CMT.list.forEach(x => { x.editing = (x === c); });
    render();
    const t = CMT.el.list.querySelector('[data-ed]');
    if (t) { t.focus(); t.setSelectionRange(t.value.length, t.value.length); }
  });
  CMT.el.list.querySelectorAll('[data-go]').forEach(b => b.onclick = () => {
    const c = CMT.list.find(x => x.id === b.dataset.go);
    if (c) window.focusBlock(c.blk);
  });
}

function render() {
  paint();
  paintRailCounts();          // after paint(), which is what decides `lost`
  const live = openOnes(), done = doneOnes();
  CMT.el.n.textContent = live.length;
  /* Derived from the records, never from a last-write-wins flag: one failed save
     followed by one successful save used to read 'saved' over an annotation that
     existed only in this tab. */
  const unsaved = CMT.list.filter(c => c.unsaved).length;
  const damaged = (CMT.problems || []).length;
  const bits = [];
  if (damaged) bits.push(damaged + ' LINE(S) UNREADABLE');
  if (unsaved) bits.push(unsaved + ' NOT SAVED');
  if (CMT.err) bits.push(CMT.err);
  /* Joined, not ranked. A damaged corpus and unsaved work are independent facts
     and the second one is the reader's own words; precedence hid it behind the
     first. */
  CMT.el.st.textContent =
    CMT.fatal ? CMT.fatal
    : bits.length ? bits.join(' · ')
    : !CMT.list.length ? 'none yet'
    : (done.length ? 'saved · ' + done.length + ' resolved' : 'saved');

  /* #cmt-status lives INSIDE the drawer, which is translateX(101%) when closed —
     and this page's whole premise is that the reader now works with the drawer
     closed, beside the margin. Every sentence above was therefore written to a
     surface nobody has open, including "no server" and "CORPUS UNREADABLE": a
     dead server rendered as an empty margin and an opener reading 0, which is
     pixel-identical to a document nobody has annotated yet.
     The opener is always visible, so it carries the alarm. */
  const alarm = CMT.fatal || bits.length ? (CMT.fatal || bits.join(' · ')) : '';
  CMT.el.open.classList.toggle('failing', !!alarm);
  CMT.el.open.title = alarm || 'Open the annotations';

  if (CMT.fatal) {
    /* Unsaved cards render ABOVE the banner rather than instead of it. Returning
       here dropped them entirely — and `readonly` is only ever set alongside
       `fatal`, so this was the one state in which a note written after the
       failure could be seen, and it could not be. The comment on submit()'s
       read-only branch claimed the card list already knew how to show these; it
       did not. */
    const held = CMT.list.filter(c => c.unsaved);
    CMT.el.list.innerHTML =
      '<p class="cmt-empty cmt-fatal">' + esc(CMT.fatal) + '</p>'
      + (held.length
          ? '<p class="cmt-sep">' + held.length + ' annotation(s) written since the'
            + ' failure are held in this tab only, and are lost if it closes</p>'
            + held.map(card).join('')
          : '');
    wireCards();
    return;
  }
  if (!CMT.list.length && damaged) {
    /* Not "none yet". The file exists and every line of it failed to parse,
       which must never read like a corpus nobody has started. */
    CMT.el.list.innerHTML = '<p class="cmt-empty cmt-fatal">' + damaged
      + ' line(s) of the annotations file could not be read, and no record'
      + ' survived.<br><br>The file is on disk and is not empty. Resolve it by'
      + ' hand — keeping every side, because every line is evidence.</p>';
    return;
  }
  if (!CMT.list.length) {
    CMT.el.list.innerHTML = '<p class="cmt-empty">No annotations yet.<br><br>'
      + 'Select any text and an <strong>annotate</strong> button appears.'
      + ' Cmd/Ctrl+Enter saves.<br><br>'
      + 'Each one records the section, the source line, the selected words and'
      + ' the text either side of them, so it can be found again after the'
      + ' document moves underneath it.</p>';
    return;
  }



  /* A resolved annotation leaves the page. It has been answered, and leaving it
     in view means reading the same objection twice — once as work to do and once
     as work already done. It is not deleted: the corpus keeps every one, and the
     count stays, so a page showing none is never mistaken for a corpus holding
     none. */
  CMT.el.list.innerHTML = live.map(card).join('')
    + (done.length ? '<p class="cmt-sep">' + done.length
        + ' resolved · kept in the annotations file, off the page</p>' : '');

  wireCards();
}

/* Rebuild, not reload. The page is a view of the document, so reloading a stale
   file shows prose the document no longer contains. The server runs the renderer
   on its own document and the page then reloads — which keeps this window, where
   a restart of the server would close it. */
(function () {
  const rb = document.getElementById('t-reload');
  const REST = 'Rebuild this page from the document';
  const fail = msg => {
    rb.classList.add('failed'); rb.title = msg;
    CMT.err = msg; render();
    setTimeout(() => { rb.classList.remove('failed'); rb.title = REST; }, 3000);
  };
  rb.onclick = async () => {
    if (CMT.list.some(c => c.editing)) return fail('finish the open edit before rebuilding');
    const pending = CMT.list.filter(c => c.unsaved).length;
    if (pending) return fail(pending + ' annotation(s) are not saved — rebuilding reloads'
                             + ' the page and they exist nowhere else');
    rb.disabled = true; rb.classList.remove('failed'); rb.title = 'rebuilding…';
    try {
      const r = await fetch('/api/render', {method: 'POST'});
      if (!r.ok) {
        let m = 'HTTP ' + r.status;
        try { m = (await r.json()).error || m; } catch (e) {}
        throw new Error(m);
      }
      location.reload();
    } catch (e) {
      rb.disabled = false;
      fail('rebuild failed: ' + String(e.message || e));
    }
  };
})();

/* The corpus is the only copy of a saved note, and this tab is the only copy of
   an unsaved one. */
addEventListener('beforeunload', e => {
  if (CMT.list.some(c => c.unsaved || c.editing)) { e.preventDefault(); e.returnValue = ''; }
});

/* Three states, and they must never print the same thing: reachable and empty,
   unreachable, and unreadable. A bare catch here would paint "No annotations
   yet." over a corpus that exists and cannot be parsed. */
(async function load() {
  try {
    const r = await fetch('/api/annotations');
    let j = null;
    try { j = await r.json(); } catch (e) { j = null; }
    if (r.ok && (!j || !Array.isArray(j.annotations))) {
      CMT.fatal = 'the server answered, but not with an annotation list — nothing is'
                + ' shown, and nothing should be written, until this is understood';
      CMT.readonly = true;
      return render();
    }
    if (!r.ok) {
      j = j || {};
      CMT.fatal = j.unreadable
        ? 'CORPUS UNREADABLE — ' + (j.error || 'HTTP ' + r.status)
          + '. Nothing is shown, and nothing should be written, until this is'
          + ' resolved by hand.'
        : 'could not load annotations: ' + (j.error || 'HTTP ' + r.status);
      CMT.readonly = true;
    } else {
      CMT.list = j.annotations || [];
      CMT.problems = j.problems || [];
    }
  } catch (e) {
    CMT.fatal = 'no server — annotations cannot be loaded or saved ('
              + (e.message || e) + ')';
    CMT.readonly = true;
  }
  render();
})();
"""

ICON_REBUILD = ('<svg class="ico-svg" viewBox="0 0 16 16" aria-hidden="true"><path '
                'd="M13.4 8a5.4 5.4 0 1 1-1.6-3.8M13.4 2v3.1h-3.1" fill="none" '
                'stroke="currentColor" stroke-width="1.4" stroke-linecap="round" '
                'stroke-linejoin="round"/></svg>')
ICON_THEME = ('<svg class="ico-svg" viewBox="0 0 16 16" aria-hidden="true"><path '
              'd="M13.2 9.6A5.6 5.6 0 0 1 6.4 2.8a5.6 5.6 0 1 0 6.8 6.8z" fill="none" '
              'stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>')
ICON_CLOSE = ('<svg class="ico-svg" viewBox="0 0 16 16" aria-hidden="true"><path '
              'd="M4.2 4.2l7.6 7.6M11.8 4.2l-7.6 7.6" fill="none" stroke="currentColor" '
              'stroke-width="1.5" stroke-linecap="round"/></svg>')


# The reading half of the page, with `__BODY__` where the document goes.
# render_change.py replaces this whole run with its own tabbed shell, and it
# matched it as a hand-copied literal — so changing the markup here silently
# turned that replace into a no-op and rendered the change page with an empty
# column. One constant, read by both, and a test that the substitution fired.
SHELL_MARKUP = ('<main class="page"><div class="wrap">'
                '<div class="col" id="doc">__BODY__</div>'
                '<div class="gutter" id="gutter" aria-label="Annotations in the margin"></div>'
                '</div></main>')


def page(title, doc_key, body_html, blocks, words, sections=()):
    favicon = "data:image/svg+xml;base64," + base64.b64encode(
        FAVICON_SVG.encode("utf-8")).decode("ascii")
    js = (JS.replace("__DOC__", json.dumps(doc_key))
            .replace("__NON_SOURCE__",
                     ", ".join("." + c for c in INJECTED_CLASSES)))
    rail_html = rail(sections)
    nav = ('<nav class="rail" aria-label="Sections">'
           '<p class="rail-h">Sections</p>' + rail_html +
           '<div class="rail-foot">Bars are section length, against the longest'
           ' section. A count marks open annotations.</div></nav>') if rail_html else ""
    return (
        # data-theme is set here rather than by the script, so the page cannot
        # paint one palette and then swap to the other on load.
        '<!doctype html>\n<html lang="en" data-theme="light">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<link rel="icon" href="' + favicon + '">\n'
        '<title>' + esc(title) + '</title>\n'
        '<style>' + CSS + '</style>\n'
        '</head>\n<body>\n'
        '<div class="bar">'
        '<span class="bar-doc mono">' + esc(doc_key) + '</span>'
        '<span class="bar-stat">' + str(blocks) + ' blocks · '
        + format(words, ",d") + ' words</span>'
        '<span class="bar-sp"></span>'
        '<span class="bar-tools">'
        '<button class="bar-ico" id="t-reload" title="Rebuild this page from the document"'
        ' aria-label="Rebuild">' + ICON_REBUILD + '</button>'
        '<button class="bar-ico" id="t-theme" title="Theme" aria-label="Theme">'
        + ICON_THEME + '</button>'
        '</span>'
        '<button class="opener" id="cmt-open" aria-expanded="false">'
        '<span>Annotations</span><span class="cmt-n" id="cmt-count">0</span></button>'
        '</div>\n'
        # `.wrap` is the two-column reading grid: the prose, and the margin the
        # annotations stand in. render_change.py substitutes this exact markup
        # for its own tabbed shell, so SHELL_MARKUP below is the one copy of the
        # string and both sides read it from there.
        '<div class="shell">' + nav
        + SHELL_MARKUP.replace("__BODY__", body_html)
        + '</div>\n'
        '<div class="sel-btn" id="sel-btn" hidden><span>+</span> annotate</div>\n'
        '<div class="cmt-pop" id="cmt-pop" hidden>'
        '<p class="cmt-anchor" id="cmt-anchor"></p>'
        '<textarea id="cmt-text" rows="4" placeholder="What is wrong with it, or what it needs."></textarea>'
        '<div class="cmt-actions">'
        '<span class="cmt-where" id="cmt-where"></span>'
        '<button class="cmt-ico" id="cmt-cancel" title="Cancel" aria-label="Cancel">✕</button>'
        '<button class="cmt-ico cmt-ok" id="cmt-save" title="Save — or ⌘/ctrl+enter"'
        ' aria-label="Save annotation">✓</button>'
        '</div></div>\n'
        '<div class="scrim" id="scrim"></div>\n'
        # `inert` from the markup, not from the script: the drawer opens closed,
        # and a keyboard user reaching it before the first click is exactly the
        # state a script-set attribute would miss. setCmt() owns it after that.
        '<aside class="drawer" id="cdrawer" aria-label="Annotations" inert aria-hidden="true">'
        '<div class="dr-top"><span class="dr-title">Annotations</span>'
        '<span class="dr-sub" id="cmt-status">—</span>'
        '<button class="dr-x" id="cd-x" title="Close" aria-label="Close annotations">'
        + ICON_CLOSE + '</button></div>'
        '<div class="dr-body"><div id="cmt-list"></div></div>'
        '</aside>\n'
        '<div class="undo" id="undo" inert aria-hidden="true">'
        '<span id="undo-t"></span>'
        '<button class="undo-b" id="undo-b">Undo</button></div>\n'
        '<script>' + js + '</script>\n'
        '</body>\n</html>\n'
    )


# ---------------------------------------------------------------- anchors


def check_anchors(ctx, corpus_path):
    """Which open annotations no longer find their text on the freshly built
    page. Returns (checked, lost ids, problems, fatal message or None).

    A lost anchor is a finding, not a fault: it means the text an annotation was
    written against has changed since. It is reported rather than repaired,
    because the note may be the reason the change was wrong.
    """
    problems = []
    try:
        rows = store.read_all(corpus_path, problems=problems)
    except store.CorpusUnreadable as e:
        return 0, [], problems, str(e)
    openc, _done = store.split(rows or [])
    texts = list(ctx.blocks.values())
    lost = []
    for c in openc:
        needle = c.get("text") or ""
        if not needle:
            lost.append(c.get("id", "?"))
            continue
        by_id = ctx.blocks.get(c.get("blk"))
        if by_id is not None and needle in by_id:
            continue
        full = (c.get("before") or "")[-24:] + needle + (c.get("after") or "")[:24]
        hits = [t for t in texts if full in t]
        if len(hits) == 1:
            continue
        # One match or none, the same rule the page's hostFor() applies: it
        # tries the stored block, then the context needle, and returns null
        # otherwise. This used to fall back to a bare text search across every
        # block — which the comment already said it must not, three lines above
        # the line that did it. The fallback only fires when the context search
        # missed, i.e. exactly when the page CANNOT relocate the record, so it
        # was wrong every time it triggered: the CLI reported "0 could not be
        # read back" over annotations the drawer was painting as ANCHOR LOST.
        lost.append(c.get("id", "?"))
    return len(openc), lost, problems, None


# ---------------------------------------------------------------- main


def page_dir(root):
    """Where rendered pages go: a temp directory keyed to the repo.

    Not the repo. The page is a working view rather than something the repo
    keeps, and writing it into the tree would need a `.gitignore` entry in every
    consuming repo — which an install has no business adding.
    """
    key = hashlib.sha1(
        os.path.normcase(os.path.abspath(root)).encode("utf-8")).hexdigest()[:10]
    return os.path.join(tempfile.gettempdir(), "cla-annotate", key)


def build(doc_path, root=None, out=None):
    """Render one document. Returns (out_path, ctx, words)."""
    root = root or store.repo_root(doc_path)
    doc_path = os.path.abspath(doc_path)
    # Encoding is not optional. Python's default is the locale codepage, so on
    # Windows a UTF-8 document decodes as cp1252 and every non-ASCII character
    # arrives mangled — silently, while POSIX is fine throughout, which is
    # precisely what makes it dangerous in a repo with no CI.
    with open(doc_path, "r", encoding="utf-8") as fh:
        text = fh.read()
    is_text = os.path.splitext(doc_path)[1].lower() not in (".md", ".markdown", ".mdown")
    body, ctx = render_document(text, os.path.dirname(doc_path), plain_text=is_text)
    key = store.doc_key(doc_path, root)
    title = ctx.title or os.path.basename(doc_path)
    words = sum(len(t.split()) for t in ctx.blocks.values())
    out = out or os.path.join(page_dir(root), store.page_name(doc_path, root))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page(title, key, body, len(ctx.blocks), words, ctx.sections))
    return out, ctx, words


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("document", help="the .md or .txt file to render")
    ap.add_argument("--out", help="where to write the page (default: a temp directory)")
    ap.add_argument("--root", help="repo root (default: resolved from git)")
    a = ap.parse_args(argv)

    if not os.path.isfile(a.document):
        print("no such document: %s" % a.document)
        return 1
    root = a.root or store.repo_root(a.document)
    try:
        out, ctx, words = build(a.document, root, a.out)
    except UnicodeDecodeError as e:
        print("%s is not valid UTF-8 (%s at byte %d)" % (a.document, e.reason, e.start))
        return 1

    corpus = store.path_for(a.document, root)
    print("built     %d blocks, %s words  ->  %s" % (len(ctx.blocks), format(words, ",d"), out))
    checked, lost, problems, fatal = check_anchors(ctx, corpus)
    if fatal:
        print("CORPUS UNREADABLE: %s" % fatal)
        return 1
    if checked:
        print("anchors   %d open, %d could not be read back" % (checked, len(lost)))
        if lost:
            # Named, not just counted: these are the ones that cannot be seen in
            # place on the page, so they are the ones to read first.
            print("          ANCHOR LOST: %s" % ", ".join(lost[:10]))
    if problems:
        print("          %d line(s) of %s could not be read:" % (len(problems), corpus))
        for p in problems:
            print("            %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
