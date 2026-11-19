"""The Markdown and plain-text reader behind `render_doc.py`.

Turns a document's text into the annotatable body: every block the reader can
select carries `data-blk` and `data-line` (see `render_doc.py` for why). It
writes nothing and starts no server. Not a command: import it, or run
`render_doc.py`.
"""

import base64
import html
import mimetypes
import os
import re


MAX_INLINE_IMAGE_BYTES = 2 * 1024 * 1024

FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*([^`]*)$")
# A closing run of `#` ends an ATX heading only after a space or tab, as in
# CommonMark and in OpenSpec's own requirement names: `### Uses C#` is the
# heading "Uses C#", and `### Foo ###` is "Foo".
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)(?:[ \t]+#+)?[ \t]*$")
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
