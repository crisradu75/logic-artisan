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
import json
import os
import sys
import tempfile

import annotations_store as store

from render_doc_css import CSS, FAVICON_SVG
from render_doc_js_notes import JS_NOTES
from render_doc_js_page import JS_PAGE
from render_doc_markdown import esc, render_document

# Names this module held before its parts were split out: other scripts and the tests read them from here.
from render_doc_markdown import (
    CODE_CLOSE,
    CODE_OPEN,
    Ctx,
    FENCE_RE,
    HEADING_RE,
    HR_RE,
    LIST_RE,
    MAX_INLINE_IMAGE_BYTES,
    QUOTE_RE,
    TABLE_SEP_RE,
    inline,
    plain,
    render_blocks,
    render_list,
    render_table,
    slugify,
    strip_html_comments,
)

# What the page injects into the prose that the document does not contain: the
# annotation marker, and the change page's link gutter. This
# constant is the Python half of the page's own NON_SOURCE, and the two must
# agree — an annotation records the document's characters, so anything the
# renderer added has to come out on both sides, or the browser and this script
# disagree about what a block says. One constant per side, never a list per use
# site: three hand-maintained copies is how a class gets missed.
INJECTED_CLASSES = ("cmt-sup", "gut")


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


JS = JS_PAGE + JS_NOTES

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

# The same reading grid, with the author's own document in a frame instead of
# markup this script generated. The frame carries no height here: the script
# sets it from the content so the OUTER page scrolls and there is no inner
# scrollbar, which is what keeps the margin arithmetic and the rail as they are.
# The notice is the `file:` case — a page opened straight off disk gives both
# documents opaque origins, so `contentDocument` throws and the layer would
# simply not appear. It is hidden unless that happens.
FRAME_MARKUP = ('<main class="page"><div class="wrap">'
                '<div class="col" id="doc">'
                '<p class="frame-warn" id="frame-warn" hidden></p>'
                '<iframe id="cla-frame" title="__TITLE__" src="__SRC__"></iframe>'
                '</div>'
                '<div class="gutter" id="gutter" aria-label="Annotations in the margin"></div>'
                '</div></main>')


def page(title, doc_key, body_html, blocks, words, sections=(), frame_src=None):
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
        + (FRAME_MARKUP.replace("__SRC__", esc(frame_src))
                       .replace("__TITLE__", esc(title))
           if frame_src else SHELL_MARKUP.replace("__BODY__", body_html))
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


HTML_SUFFIXES = (".html", ".htm")
MARKDOWN_SUFFIXES = (".md", ".markdown", ".mdown")


def target_kind(path):
    """Which renderer a path belongs to: "html" or "doc".

    One rule, read by this module's own CLI and by the server. Scoping it to the
    server alone would leave two documented commands producing different pages
    for one file — `render_doc.py foo.html` still emitting escaped markup while
    the server emitted the frame — and SKILL.md documents the CLI as step one.
    A change is resolved by the caller before this is asked, because a bare
    change id is neither a file nor a suffix.
    """
    return "html" if os.path.splitext(path)[1].lower() in HTML_SUFFIXES else "doc"


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
    is_text = os.path.splitext(doc_path)[1].lower() not in MARKDOWN_SUFFIXES
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
    # It prints lost anchors and warnings quoting document text; see
    # render_html.use_utf8_stdout. A call-site import, for the reason given at
    # the html branch below.
    import render_html
    render_html.use_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("document",
                    help="the .md, .txt, .html or .htm file to render")
    ap.add_argument("--out", help="where to write the page (default: a temp directory)")
    ap.add_argument("--root", help="repo root (default: resolved from git)")
    a = ap.parse_args(argv)

    if not os.path.isfile(a.document):
        print("no such document: %s" % a.document)
        return 1
    root = a.root or store.repo_root(a.document)
    if target_kind(a.document) == "html":
        # Imported HERE, not at module level. `render_html` needs `page()` from
        # this module, so a top-level import either way closes a cycle and fails
        # while the first module is still initialising. Nothing is needed from
        # it at import time, so a call-site import is not a workaround — it
        # matches when the dependency actually exists.
        import render_html
        try:
            out, ctx, words = render_html.build(a.document, root, a.out)
        except render_html.Refused as e:
            print("REFUSED: %s" % e)
            return 1
        print("built     %d blocks, %s words  ->  %s"
              % (len(ctx.blocks), format(words, ",d"), out))
        for w in getattr(ctx, "warnings", []):
            print("warning   %s" % w)
        checked, lost, problems, fatal = check_anchors(
            ctx, store.path_for(a.document, root))
        if fatal:
            print("CORPUS UNREADABLE: %s" % fatal)
            return 1
        if checked:
            print("anchors   %d open, %d could not be read back" % (checked, len(lost)))
            if lost:
                print("          ANCHOR LOST: %s" % ", ".join(lost[:10]))
        return 0
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
