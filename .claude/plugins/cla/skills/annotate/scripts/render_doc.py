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

# The page injects exactly one thing into the prose: the annotation marker. This
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

    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+&quot;[^&]*&quot;)?\)", image, text)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)(?:\s+&quot;[^&]*&quot;)?\)",
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
            cls = ' class="language-%s"' % esc(lang) if lang else ""
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
    '<style>.a{fill:#2F5C57}.b{fill:#C8622F}'
    '@media (prefers-color-scheme:dark){.a{fill:#84B8B0}.b{fill:#E0915E}}</style>'
    '<path class="a" d="M3.4 1h5.3l3.9 3.9V15H3.4z"/>'
    '<path class="a" opacity=".55" d="M8.7 1l3.9 3.9H8.7z"/>'
    '<path class="b" d="M1.5 8.7h11v3h-11z"/></svg>'
)

CSS = """
:root{
 --paper:#F2F2EE;--ground:#E5E6E1;--sunk:#DCDDD7;
 --ink:#1A1D1F;--ink-2:#3E4447;--muted:#6E7478;--rule:#C9CBC5;--hair:#DBDCD6;
 --accent:#2F5C57;--accent-2:#4C837C;--accent-wash:#DCE7E3;
 --mark:#C8622F;--mark-wash:#F1DFD4;
}
/* Light is the default outright, and there is deliberately no
   `prefers-color-scheme` rule: this page is a reading surface for a working
   document, and it opens the same way on every machine rather than tracking a
   system setting the reader did not choose for it. The emitted HTML carries
   data-theme="light" on the root, so dark applies only once the toggle has
   asked for it — which also means no flash of the other palette on load. */
:root[data-theme="dark"]{
 --paper:#16191B;--ground:#101314;--sunk:#1C2022;
 --ink:#DCDEDA;--ink-2:#B0B5B3;--muted:#828885;--rule:#2B3033;--hair:#23282A;
 --accent:#84B8B0;--accent-2:#5E938C;--accent-wash:#172523;
 --mark:#E0915E;--mark-wash:#291A11;
}
*{box-sizing:border-box}
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
.cmt-n{font-variant-numeric:tabular-nums;background:var(--mark-wash);color:var(--mark);
 border-radius:999px;padding:.05rem .42rem;font-size:.68rem;min-width:1.35rem;text-align:center}
.opener[aria-expanded="true"] .cmt-n{background:var(--paper);color:var(--mark)}

.shell{display:grid;grid-template-columns:clamp(13rem,18vw,17rem) minmax(0,1fr);
 align-items:start}
.rail{position:sticky;top:2.9rem;height:calc(100vh - 2.9rem);overflow-y:auto;
 padding:1.3rem .8rem 3rem 1.1rem;border-right:1px solid var(--rule);background:var(--paper)}
.rail-h{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.62rem;letter-spacing:.16em;
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
.rail-n{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.66rem;
 font-variant-numeric:tabular-nums;color:var(--muted);text-align:right}
.rail-item.on .rail-n{color:var(--accent)}
/* The annotation count is the reason to look at the rail once a pass is under
   way: it says which sections were argued with, which is not the same question
   as which are long. */
.rail-c{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.64rem;
 font-variant-numeric:tabular-nums;background:var(--mark);color:var(--paper);
 border-radius:999px;padding:.02rem .34rem;min-width:1.1rem;text-align:center}
.rail-c[hidden]{display:none}
.rail-foot{margin-top:1.1rem;padding-top:.9rem;border-top:1px solid var(--hair);
 font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.62rem;line-height:1.7;
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
.fm-t{display:block;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.58rem;
 letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin-bottom:.4rem}
.fm pre{margin:0;background:none;border:0;padding:0}
.pt{white-space:pre-wrap}
.tw{overflow-x:auto;margin:0 0 1.2rem}
table{border-collapse:collapse;font-size:.88rem;min-width:100%}
th,td{border:1px solid var(--hair);padding:.4rem .6rem;text-align:left;vertical-align:top}
th{background:var(--sunk);font-weight:600}

.sel-btn{position:absolute;z-index:90;cursor:pointer;background:var(--mark);color:var(--paper);
 font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.62rem;letter-spacing:.1em;
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
.cmt-where{flex:1;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.6rem;
 color:var(--muted);letter-spacing:.06em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cmt-hint{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.58rem;color:var(--muted)}
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
.cmt-num{font-size:.68rem;min-width:1.25rem;border-radius:2px}
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
.dr-sub{flex:1;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.62rem;
 letter-spacing:.07em;text-transform:uppercase;color:var(--muted);overflow:hidden;
 text-overflow:ellipsis;white-space:nowrap}
.dr-x{display:inline-flex;align-items:center;justify-content:center;width:1.6rem;height:1.6rem;
 padding:0;border:0;background:none;color:var(--muted);cursor:pointer}
.dr-x:hover{color:var(--ink)}
.dr-body{overflow-y:auto;padding:0 1rem 3rem}
.cmt-card{padding:.9rem 0;border-bottom:1px solid var(--hair)}
.cmt-head{display:flex;gap:.55rem;align-items:baseline;margin-bottom:.35rem}
.cmt-idx{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.66rem;color:var(--mark);flex:none}
.cmt-loc{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.63rem;color:var(--muted);
 letter-spacing:.04em;cursor:pointer;background:none;border:0;padding:0;text-align:left}
.cmt-loc:hover{color:var(--mark);text-decoration:underline}
.cmt-acts{margin-left:auto;display:flex;gap:.15rem;flex:none}
.cmt-quote{margin:0 0 .4rem;font-size:.84rem;line-height:1.45;color:var(--ink-2);
 border-left:2px solid var(--mark);padding-left:.6rem}
.cmt-note{margin:0;font-size:.9rem;line-height:1.5;cursor:text;white-space:pre-wrap}
.cmt-empty{color:var(--muted);font-size:.86rem;line-height:1.6;padding:1.4rem 0}
.cmt-fatal{color:var(--mark)}
.cmt-sep{margin:1.1rem 0 .5rem;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.6rem;
 letter-spacing:.12em;text-transform:uppercase;color:var(--muted);border-top:1px solid var(--rule);
 padding-top:.6rem}
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
function setCmt(on) {
  document.body.classList.toggle('cmt', on);
  CMT.el.open.setAttribute('aria-expanded', String(on));
}
CMT.el.open.onclick = () => setCmt(!document.body.classList.contains('cmt'));
document.getElementById('cd-x').onclick = () => setCmt(false);
document.getElementById('scrim').onclick = () => setCmt(false);
function openList(id) {
  setCmt(true);
  const card = document.getElementById('card-' + id);
  if (card) card.scrollIntoView({block:'center', behavior:'smooth'});
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
   Three fallback passes, narrowest first, each returning the SOURCE spelling
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
                                 id: 'local-' + CMT.list.length}, cap));
    return render();
  }
  closePop();
  await postAnnotation(Object.assign({note, doc: DOC}, cap));
}
document.getElementById('cmt-save').onclick = () => submit();
CMT.el.text.addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') submit();
});

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
    rec.id = rec.id || ('local-' + Date.now());
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
    CMT.list = CMT.list.filter(c => c.id !== id);      // never reached the file
    return render();
  }
  rec.deleting = true; render();
  try {
    const r = await fetch('/api/annotations', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id, deleted: true})});
    if (!r.ok) throw new Error('HTTP ' + r.status);
    CMT.list = CMT.list.filter(c => c.id !== id);
    CMT.err = null;
  } catch (e) {
    rec.deleting = false;
    rec.delFailed = true;
    CMT.err = 'delete failed: ' + String(e.message || e);
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
  rec.editing = false;
  if (!note || note === rec.note) return render();          // nothing to record
  rec.note = note;
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
       card says which it is. */
    rec.editFailed = true;
    CMT.err = 'edit failed: ' + String(e.message || e);
  }
  render();
}

/* ---- paint anchors back into the prose ---- */
/* extractContents splits <em>, <strong> and <code> when a range ends inside one,
   and unwrapping the highlight does not put the halves back together. */
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

function paint() {
  clearMarks();
  openOnes().forEach((c, i) => {
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
      if (!m.parentNode && m.firstChild) {
        try { r.insertNode(m.firstChild); } catch (e2) {}
      }
      c.lost = true;
      return;
    }
    c.lost = false;
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
  });
}

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

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
  CMT.el.st.textContent =
    CMT.fatal ? CMT.fatal
    : damaged ? (damaged + ' LINE(S) UNREADABLE')
    : CMT.err ? CMT.err
    : unsaved ? (unsaved + ' NOT SAVED')
    : !CMT.list.length ? 'none yet'
    : (done.length ? 'saved · ' + done.length + ' resolved' : 'saved');

  if (CMT.fatal) {
    CMT.el.list.innerHTML = '<p class="cmt-empty cmt-fatal">' + esc(CMT.fatal) + '</p>';
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

  const card = (c, i) => '<div class="cmt-card" id="card-' + c.id + '" data-id="' + c.id + '">'
    + '<div class="cmt-head">'
    + '<span class="cmt-idx">' + (i + 1) + '</span>'
    + '<button class="cmt-loc" data-go="' + c.id + '">'
    /* On a change, which FILE an annotation is on outranks which section: the
       reader is deciding whether to switch tabs. */
    + esc(c.file ? c.file + (c.sec ? ' · ' + c.sec : '') : (c.sec || DOC))
    + ' · line ' + (c.line || '?')
    + (c.lost ? ' · ANCHOR LOST' : '')
    + (c.unsaved ? ' · unsaved' : '')
    + (c.delFailed ? ' · DELETE FAILED' : '')
    + (c.editFailed ? ' · EDIT NOT SAVED' : '')
    + (c.deleting ? ' · deleting…' : '')
    + '</button>'
    + '<span class="cmt-acts">'
    + '<button class="cmt-ico' + (c.editing ? ' is-on' : '') + '" data-edit="' + c.id + '"'
    + ' title="edit this note" aria-label="edit annotation ' + (i + 1) + '">✎</button>'
    + (c.editing ? '' : '<button class="cmt-ico" data-del="' + c.id + '"'
        + ' title="delete this annotation" aria-label="delete annotation ' + (i + 1)
        + '">✕</button>')
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

  /* A resolved annotation leaves the page. It has been answered, and leaving it
     in view means reading the same objection twice — once as work to do and once
     as work already done. It is not deleted: the corpus keeps every one, and the
     count stays, so a page showing none is never mistaken for a corpus holding
     none. */
  CMT.el.list.innerHTML = live.map(card).join('')
    + (done.length ? '<p class="cmt-sep">' + done.length
        + ' resolved · kept in the annotations file, off the page</p>' : '');

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

/* Three states, and they must never print the same thing: reachable and empty,
   unreachable, and unreadable. A bare catch here would paint "No annotations
   yet." over a corpus that exists and cannot be parsed. */
(async function load() {
  try {
    const r = await fetch('/api/annotations');
    const j = await r.json().catch(() => ({}));
    if (!r.ok) {
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
        '<div class="shell">' + nav
        + '<main class="page"><div class="col" id="doc">' + body_html
        + '</div></main></div>\n'
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
        '<aside class="drawer" id="cdrawer" aria-label="Annotations">'
        '<div class="dr-top"><span class="dr-title">Annotations</span>'
        '<span class="dr-sub" id="cmt-status">—</span>'
        '<button class="dr-x" id="cd-x" title="Close" aria-label="Close annotations">'
        + ICON_CLOSE + '</button></div>'
        '<div class="dr-body"><div id="cmt-list"></div></div>'
        '</aside>\n'
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
        # One match or none, the same rule the page applies. Falling back to a
        # bare text search here would call an annotation anchored that the page
        # paints as lost — a disagreement about the same corpus.
        if not hits and sum(1 for t in texts if needle in t) == 1:
            continue
        lost.append(c.get("id", "?"))
    return len(openc), lost, problems, None


# ---------------------------------------------------------------- main


def page_dir(root):
    """Where rendered pages go: a temp directory keyed to the repo.

    Not the repo. The page is a working view rather than something the repo
    keeps, and writing it into the tree would need a `.gitignore` entry in every
    consuming repo — which an install has no business adding.
    """
    key = store.hashlib.sha1(
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
