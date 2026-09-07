"""The page as a browser actually lays it out.

WHY THIS FILE EXISTS. Every other check on this page is a string grep against
generated HTML and JS, because that is all a stdlib-only suite can do. That is a
real constraint and those checks earn their place — but they measure the presence
of text, not the behaviour of a layout, and the gap between the two is not small.
Measured on the change that added the margin: a reviewer simulated 21 plausible
regressions against the rendered page and **19 survived** every one of the 46
tests then covering it. Two of the defects that shipped in that change were found
by driving a browser and could not have been found any other way:

  * the open drawer landing ON the margin at 1440px — notes rendered, hoverable,
    and covered by a fixed panel;
  * a note drawn at top:-135.78px, beside nothing, for a block on a tab that was
    not showing, because `isConnected` is true for a `display:none` subtree.

Neither has a string to grep for. Both are one assertion here.

OPT-IN, AND NEVER A REQUIRED DEPENDENCY. `CLAUDE.md` pins this repo to stdlib
Python plus pytest, and that stays true: this module skips itself unless
`playwright` and a browser are already installed, so a clean checkout runs the
suite exactly as before and sees one skip. It is a second gate for whoever has
the tooling, not a new barrier for whoever does not.

    pip install playwright && playwright install chromium
    python3 -m pytest plugin-tests/tests/skills/annotate/test_page_in_a_browser.py

WHAT BELONGS HERE. Only what a string cannot answer: geometry, stacking, what a
breakpoint does to the flow, and whether a round-trip through the server leaves
the page in the state it claims. Anything checkable by reading the generated
source belongs in `test_render_doc.py`, which is cheaper and always runs.
"""
import json
import os
import threading
import time
from functools import partial
from http.server import ThreadingHTTPServer

import pytest

sync_api = pytest.importorskip(
    "playwright.sync_api",
    reason="playwright is not installed; this browser gate is opt-in "
           "(pip install playwright && playwright install chromium)",
)

import annotate_server
import annotations_store as store
import render_doc


DOC = """# A document to lay out

This is the first paragraph, and it runs long enough that a selection inside it
has real context on either side of the words that were selected.

Here is a second paragraph. It carries two annotations, which is the case the
stacking rule exists for, and the second note has to be pushed clear of the
first rather than drawn on top of it.

## A second section

A third paragraph, far enough down the page that a note beside it is nowhere
near the notes above it.

A closing paragraph.
"""


def _seed(corpus, blocks, doc_key):
    """Three annotations: two on one block — the stacking case — and one far
    below. Written straight to the corpus so the browser opens on a page that
    already has something to lay out."""
    def rec(rid, blk, needle, note):
        text = blocks[blk]
        off = text.index(needle)
        return {"id": rid, "doc": doc_key, "blk": blk, "sec": "", "line": 1,
                "off": off, "text": needle,
                "before": text[max(0, off - 60):off],
                "after": text[off + len(needle):off + len(needle) + 60],
                "note": note, "at": "2026-08-25T10:00:00"}

    rows = [rec("b1", "b3", "second paragraph", "First note on this block."),
            rec("b2", "b3", "stacking rule", "Second note on the same block."),
            rec("b3", "b5", "third paragraph", "A note far down the page.")]
    os.makedirs(os.path.dirname(corpus), exist_ok=True)
    with open(corpus, "w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    """The real renderer and the real server, on an ephemeral port."""
    root = tmp_path_factory.mktemp("browser")
    (root / ".git").mkdir()
    doc = root / "doc.md"
    doc.write_text(DOC, encoding="utf-8")
    pages = tmp_path_factory.mktemp("pages")
    page = pages / "doc.html"
    _out, ctx, _w = render_doc.build(str(doc), str(root), str(page))

    corpus = store.path_for(str(doc), str(root))
    _seed(corpus, ctx.blocks, store.doc_key(str(doc), str(root)))

    annotate_server.Handler.out_path = str(corpus)
    annotate_server.Handler.doc_path = str(doc)
    annotate_server.Handler.doc_key = store.doc_key(str(doc), str(root))
    annotate_server.Handler.root = str(root)
    annotate_server.Handler.page_path = str(page)
    annotate_server.Handler.is_change = False
    srv = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(annotate_server.Handler, directory=str(pages)))
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:%d/doc.html" % srv.server_address[1]
    srv.shutdown()
    srv.server_close()
    thread.join(timeout=10)


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as pw:
        try:
            b = pw.chromium.launch()
        except Exception as e:                       # noqa: BLE001 — any launch fault
            pytest.skip("no usable chromium: %s" % e)
        yield b
        b.close()


@pytest.fixture
def page(browser, served):
    p = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    p.on("pageerror", lambda e: errors.append(str(e)))
    p.goto(served)
    p.wait_for_selector("#gutter .mnote")
    yield p
    # A page that throws still renders its server-side prose, so a script error
    # is invisible unless something asks. This is the cheapest assertion in the
    # file and it covers every test that used it.
    assert errors == [], "the page threw: %s" % errors
    p.close()


def test_each_note_stands_beside_the_block_it_names(page):
    """The claim the whole margin makes. A note whose top is not level with its
    own mark is a note pointing at the wrong sentence, and its tie is drawn SOLID
    to say that it is not."""
    pairs = page.evaluate("""() => [...document.querySelectorAll('#gutter .mnote')]
        .filter(n => n.dataset.cmt)
        .map(n => {
          const mark = document.querySelector('mark.cmt-hl[data-cmt="' + n.dataset.cmt + '"]');
          return {id: n.dataset.cmt,
                  stacked: n.classList.contains('stacked'),
                  drift: Math.round(n.getBoundingClientRect().top
                                    - mark.getBoundingClientRect().top)};
        })""")
    assert [p["id"] for p in pairs] == ["b1", "b2", "b3"]
    # The first note on a block sits at the designed offset from its mark. The
    # ones below may be pushed clear, and say so by going dashed.
    assert pairs[0]["drift"] == -6 and not pairs[0]["stacked"]
    assert pairs[1]["stacked"], "two notes on one block did not stack"


def test_two_notes_on_one_block_do_not_overlap(page):
    """Stacking is not decoration: without the push, the second note is drawn on
    top of the first and one of them cannot be read at all."""
    boxes = page.evaluate("""() => [...document.querySelectorAll('#gutter .mnote')]
        .map(n => n.getBoundingClientRect())
        .map(r => [Math.round(r.top), Math.round(r.bottom)])""")
    for (top_a, bottom_a), (top_b, _b) in zip(boxes, boxes[1:]):
        assert top_b >= bottom_a, "margin notes overlap: %s then %s" % (
            (top_a, bottom_a), (top_b, _b))


def test_the_margin_never_shares_a_pixel_with_the_prose(page):
    """The layout this page was rebuilt for. The drawer used to be a fixed panel
    laid over the reading column, so an annotation and the sentence it named
    could not be read at once."""
    geom = page.evaluate("""() => ({
        col: document.querySelector('.wrap > .col').getBoundingClientRect().right,
        gut: document.getElementById('gutter').getBoundingClientRect().left,
    })""")
    assert geom["gut"] >= geom["col"], "the margin overlaps the reading column"


def test_an_open_drawer_never_covers_the_margin(page):
    """Found in a browser and by nothing else: at 1440px the drawer is a fixed
    27rem panel and it landed ON the margin — notes rendered, hoverable, and
    covered. Below 1600px the margin folds away instead; above it, both fit."""
    for width in (1280, 1440, 1700):
        page.set_viewport_size({"width": width, "height": 900})
        page.click("#cmt-open")
        page.wait_for_timeout(350)
        state = page.evaluate("""() => {
            const g = document.getElementById('gutter');
            const d = document.getElementById('cdrawer');
            const shown = getComputedStyle(g).display !== 'none';
            return {shown,
                    overlap: shown ? Math.round(g.getBoundingClientRect().right
                                                - d.getBoundingClientRect().left) : 0};
        }""")
        assert state["overlap"] <= 0, (
            "at %dpx the open drawer covers the margin by %dpx"
            % (width, state["overlap"]))
        page.click("#cd-x")
        page.wait_for_timeout(250)


def test_crossing_the_breakpoint_leaves_every_annotation_on_exactly_one_surface(page):
    """Two failures, one in each direction. Narrowing used to leave the notes
    behind with no inline marker drawn, so every annotation was on NO surface;
    widening again drew the notes while the old markers stayed, so every one
    appeared twice with two delete buttons."""
    def surfaces():
        return page.evaluate("""() => ({
            notes: document.querySelectorAll('#gutter .mnote[data-cmt]').length,
            inline: document.querySelectorAll('.cmt-sup').length,
        })""")

    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(300)
    assert surfaces() == {"notes": 3, "inline": 0}

    page.set_viewport_size({"width": 900, "height": 900})
    page.wait_for_timeout(400)
    assert surfaces() == {"notes": 0, "inline": 3}, "an annotation is on no surface"

    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(400)
    assert surfaces() == {"notes": 3, "inline": 0}, "an annotation is on both surfaces"


def test_a_delete_and_its_undo_round_trip_through_the_file(page, served):
    """End to end, through the real server and the real corpus. The undo posts
    `{deleted: false}`, which the server read as a NEW annotation until this was
    fixed — and refused for anchor fields an undo never sends."""
    page.click('.mnote[data-cmt="b2"] [data-mdel]')
    page.wait_for_timeout(400)
    assert page.evaluate("() => document.getElementById('undo').classList.contains('on')")
    live = page.evaluate("async () => (await (await fetch('/api/annotations')).json())"
                         ".annotations.map(a => a.id)")
    assert live == ["b1", "b3"], "the delete did not reach the file"

    page.click("#undo-b")
    page.wait_for_timeout(600)
    live = page.evaluate("async () => (await (await fetch('/api/annotations')).json())"
                         ".annotations.map(a => a.id)")
    # Back, and back IN PLACE — re-sorting would renumber the whole margin.
    assert live == ["b1", "b2", "b3"], "the undo did not restore the record"
    assert page.evaluate(
        "() => document.querySelectorAll('#gutter .mnote[data-cmt]').length") == 3, \
        "the undo left a duplicate note in the margin"


def test_a_failed_undo_neither_duplicates_the_record_nor_lies_about_the_file(page):
    """The defect a review found: undoDelete splices the record back before the
    POST and its catch leaves it in the list, so a retry spliced the same object
    in twice — two notes, two cards, a count one too high, and no error."""
    page.evaluate("""() => {
        window.__realFetch = window.fetch;
        window.fetch = (u, o) =>
          (o && o.method === 'POST' && /"deleted":false/.test(o.body))
            ? Promise.reject(new Error('simulated lost response'))
            : window.__realFetch(u, o);
    }""")
    page.click('.mnote[data-cmt="b1"] [data-mdel]')
    page.wait_for_timeout(400)
    for _ in range(3):                         # fail, then retry twice
        page.click("#undo-b")
        page.wait_for_timeout(300)
    state = page.evaluate("""() => ({
        ids: CMT.list.map(c => c.id),
        notes: document.querySelectorAll('#gutter .mnote[data-cmt]').length,
        strip: document.getElementById('undo-t').textContent,
        opener: document.getElementById('cmt-open').classList.contains('failing'),
    })""")
    page.evaluate("() => { window.fetch = window.__realFetch; }")

    assert state["ids"] == ["b1", "b2", "b3"], "a retried undo duplicated the record"
    assert state["notes"] == 3
    # It cannot know the file's state after a lost response, so it must not claim to.
    assert "still deleted" not in state["strip"]
    assert "could not be confirmed" in state["strip"]
    # And the alarm reaches the one surface that is always visible.
    assert state["opener"], "a failed undo left no mark on the opener"


# ======================================================================
# The HTML path: the author's own document in a frame.
#
# Every check below needs a browser by construction. The frame boundary is
# invisible to a string grep: whether the layer can reach across it, whether the
# author's CSS and the shell's stayed on their own sides, and whether a rect
# taken in one viewport means anything in the other are all questions about a
# running page.
# ======================================================================

import render_html                                              # noqa: E402


# Defines the three names the shell also uses — `.wrap`, `.bar` and
# `:root[data-theme="dark"]` — because those are the measured collisions the
# frame exists to prevent, and a fixture without them would prove nothing.
DESIGNED = """<!doctype html><meta charset="utf-8">
<title>A designed document</title>
<style>
  :root { --ink:#123456 }
  :root[data-theme="dark"] { --ink:#eeeeee }
  .wrap { max-width:62rem; margin:0 auto }
  .bar  { height:.7rem; background:#cc0000 }
  section { margin-top:3.5rem }
  body { margin:0; font:16px system-ui; color:var(--ink) }
</style>
<div class="wrap">
  <header class="masthead"><p class="kicker">Kicker text</p></header>
  <h2>First section</h2>
  <p>The opening paragraph of the first section, long enough that a selection
  inside it has real context on either side of the selected words.</p>
  <div class="wf-row"><span class="lbl">Row label</span><div class="bar" style="width:40%"></div><span class="amt">&minus;0,99</span></div>
  <p style="height:900px">Filler that makes the document taller than one screen.</p>
  <h2>Second section</h2>
  <p>The second section's paragraph.</p>
  <p style="height:900px">More filler.</p>
  <h2>Third section</h2>
  <p>The third section's paragraph.</p>
</div>
"""


@pytest.fixture(scope="module")
def served_html(tmp_path_factory):
    """The real HTML renderer and the real server, on an ephemeral port."""
    root = tmp_path_factory.mktemp("browser-html")
    (root / ".git").mkdir()
    doc = root / "designed.html"
    doc.write_text(DESIGNED, encoding="utf-8")
    pages = tmp_path_factory.mktemp("pages-html")
    page = pages / "designed-page.html"
    _out, ctx, _w = render_html.build(str(doc), str(root), str(page))

    # An EMPTY corpus. `_seed` is written against the Markdown fixture's own
    # blocks and needles; none of the checks below need a pre-existing
    # annotation, and they wait on the frame's blocks rather than on a note.
    corpus = store.path_for(str(doc), str(root))
    os.makedirs(os.path.dirname(corpus), exist_ok=True)
    open(corpus, "w", encoding="utf-8").close()

    # Its OWN Handler subclass. The server carries its per-target state as
    # CLASS attributes, and this module now runs two servers at once — setting
    # them on the shared class let whichever fixture built last redirect the
    # other's requests, which showed up as the Markdown page waiting forever for
    # a note that had been seeded into a different corpus.
    # Bound out here: inside a class body, `root = str(root)` makes `root` local
    # to that body, so the right-hand side raises NameError before it is read.
    _root, _doc, _page = str(root), str(doc), str(page)
    _key = store.doc_key(_doc, _root)

    class HtmlHandler(annotate_server.Handler):
        out_path = str(corpus)
        doc_path = _doc
        doc_key = _key
        root = _root
        page_path = _page
        is_change = False
        kind = "html"

        def do_GET(self):
            # Hold the frame back so the shell's script runs while
            # `contentDocument` is still `about:blank`. Without this the frame
            # wins the race on every local run, the placeholder is never seen,
            # and the readiness guard cannot be shown to do anything — a guard
            # whose absence changes no test is one nobody can defend keeping.
            if self.path.endswith(".frame.html"):
                time.sleep(0.35)
            return annotate_server.Handler.do_GET(self)

    srv = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(HtmlHandler, directory=str(pages)))
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:%d/designed-page.html" % srv.server_address[1]
    srv.shutdown()
    srv.server_close()
    thread.join(timeout=10)


@pytest.fixture
def hpage(browser, served_html):
    p = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    p.on("pageerror", lambda e: errors.append(str(e)))
    p.goto(served_html)
    p.wait_for_function(
        "() => { const f = document.getElementById('cla-frame');"
        " return f && f.contentDocument"
        " && f.contentDocument.querySelectorAll('[data-blk]').length > 0; }")
    p.wait_for_timeout(300)
    yield p
    assert errors == [], "the page threw: %s" % errors
    p.close()


def test_the_layer_bound_to_the_real_document_not_the_placeholder(hpage):
    """A fresh frame's contentDocument is `about:blank`, which is already
    `readyState === 'complete'`. Without the href check the layer initialises
    against that placeholder and never rebinds — and the frame still loads its
    real document afterwards, so every check that looks at the DOCUMENT rather
    than at the LAYER still passes. This one looks at the layer."""
    assert hpage.evaluate(
        "() => CDOC === document.getElementById('cla-frame').contentDocument"), \
        "the content root is not the frame's real document"


def test_the_layer_reaches_across_the_frame_boundary(hpage):
    """Nothing else in the suite can tell whether CDOC resolved. If it did not,
    every content-side call silently finds nothing and the page looks merely
    empty."""
    n = hpage.evaluate(
        "() => document.getElementById('cla-frame')"
        ".contentDocument.querySelectorAll('[data-blk]').length")
    assert n > 5, "the shell cannot see the frame's blocks"


def test_the_authors_css_and_the_shells_keep_their_own_values(hpage):
    """The three measured collisions. `.wrap`, `.bar` and the theme attribute are
    each the obvious name for what they do, on both sides — which is why the
    isolation had to be structural rather than a naming convention."""
    got = hpage.evaluate("""() => {
      const D = document.getElementById('cla-frame').contentDocument;
      const shellBar = document.querySelector('.bar');
      return {
        authorBar: getComputedStyle(D.querySelector('.bar')).height,
        authorWrap: getComputedStyle(D.querySelector('.wrap')).maxWidth,
        shellBar: shellBar ? getComputedStyle(shellBar).height : null,
      };
    }""")
    # 0.7rem at the frame's own 16px root.
    assert got["authorBar"].startswith("11."), got
    assert got["authorWrap"] == "992px", got          # 62rem
    # The shell's top bar is its own height, not the author's chart-bar rule.
    assert not got["shellBar"].startswith("11."), got


def test_the_marker_stylesheet_reached_the_frame(hpage):
    """The shell's stylesheet does not cross the boundary, and the markers are
    painted INTO the frame — so without this they render unstyled: present,
    functional and invisible."""
    assert hpage.evaluate(
        "() => !!document.getElementById('cla-frame').contentDocument"
        ".querySelector('style[data-cla-marks]')")


def test_a_selection_inside_the_frame_anchors_to_its_block(hpage):
    """The capture path end to end across the boundary: the selection is made in
    the frame's own window, and the block, offset and context all have to come
    back right."""
    cap = hpage.evaluate("""() => {
      const D = document.getElementById('cla-frame').contentDocument;
      const ps = [...D.querySelectorAll('[data-blk]')];
      const p = ps.find(e => e.textContent.includes('opening paragraph'));
      const r = D.createRange();
      const t = [...p.childNodes].find(n => n.nodeType === 3);
      r.setStart(t, 4); r.setEnd(t, 20);
      const s = D.defaultView.getSelection();
      s.removeAllRanges(); s.addRange(r);
      return {blk: p.dataset.blk, line: p.dataset.line};
    }""")
    # A synthetic mouseup ON THE FRAME'S DOCUMENT. A real mouse.down() there
    # collapses the selection this test just made, and a click on the shell
    # would not exercise the cross-boundary binding at all — measured, an event
    # inside the frame reaches the shell's document 0 times.
    hpage.evaluate("() => { const D = document.getElementById('cla-frame')"
                   ".contentDocument;"
                   " D.body.dispatchEvent(new D.defaultView.MouseEvent("
                   "'mouseup', {bubbles: true})); }")
    hpage.wait_for_timeout(300)
    pending = hpage.evaluate("() => CMT.pending && {blk: CMT.pending.blk,"
                             " text: CMT.pending.text, off: CMT.pending.off,"
                             " line: CMT.pending.line}")
    assert pending, "no selection was captured across the frame boundary"
    assert pending["blk"] == cap["blk"]
    assert pending["off"] == 4
    assert str(pending["line"]) == cap["line"], \
        "the recorded line must be the SOURCE line, which is where an edit lands"


def test_the_annotate_button_lands_beside_the_selection(hpage):
    """The rect that positions it is measured in the FRAME's viewport and used in
    the SHELL's. If the frame offset is dropped the button appears somewhere
    unrelated — and it still appears, so nothing reports it."""
    box = hpage.evaluate("""() => {
      const D = document.getElementById('cla-frame').contentDocument;
      const p = [...D.querySelectorAll('[data-blk]')]
        .find(e => e.textContent.includes('opening paragraph'));
      const r = D.createRange(); r.selectNodeContents(p);
      const s = D.defaultView.getSelection();
      s.removeAllRanges(); s.addRange(r);
      return null;
    }""")
    # A synthetic mouseup ON THE FRAME'S DOCUMENT. A real mouse.down() there
    # collapses the selection this test just made, and a click on the shell
    # would not exercise the cross-boundary binding at all — measured, an event
    # inside the frame reaches the shell's document 0 times.
    hpage.evaluate("() => { const D = document.getElementById('cla-frame')"
                   ".contentDocument;"
                   " D.body.dispatchEvent(new D.defaultView.MouseEvent("
                   "'mouseup', {bubbles: true})); }")
    hpage.wait_for_timeout(300)
    got = hpage.evaluate("""() => {
      const b = document.getElementById('sel-btn');
      if (b.hidden) return null;
      const F = document.getElementById('cla-frame');
      const D = F.contentDocument;
      const p = [...D.querySelectorAll('[data-blk]')]
        .find(e => e.textContent.includes('opening paragraph'));
      const want = p.getBoundingClientRect().top + F.getBoundingClientRect().top
                 + window.scrollY;
      return {btnTop: parseFloat(b.style.top), want: want};
    }""")
    assert got, "the annotate button did not appear"
    # Below the passage, and near it — not off in the shell's own coordinates.
    assert got["want"] - 40 < got["btnTop"] < got["want"] + 400, got


def test_a_rail_click_scrolls_the_outer_page_to_that_section(hpage):
    """Measured first as an open question: `scrollIntoView` inside a
    content-sized frame does move the outer page. This is the assertion that
    keeps it true."""
    before = hpage.evaluate("window.scrollY")
    hpage.evaluate("() => document.querySelectorAll('.rail-item')[2].click()")
    hpage.wait_for_timeout(900)
    after = hpage.evaluate("window.scrollY")
    assert after > before + 100, "the rail did not move the page (%s -> %s)" % (
        before, after)


def test_the_frame_is_sized_to_its_content_so_the_outer_page_scrolls(hpage):
    """The premise the whole geometry rests on. An inner scrollbar would put a
    second scroll offset into every margin calculation."""
    got = hpage.evaluate("""() => {
      const F = document.getElementById('cla-frame');
      const D = F.contentDocument;
      return {frame: Math.round(F.getBoundingClientRect().height),
              inner: D.documentElement.scrollHeight,
              innerScrollable: D.documentElement.scrollHeight
                             > D.documentElement.clientHeight,
              outerScrollable: document.documentElement.scrollHeight
                             > window.innerHeight};
    }""")
    assert abs(got["frame"] - got["inner"]) < 4, got
    assert not got["innerScrollable"], "the frame scrolls itself; it must not"
    assert got["outerScrollable"], "the outer page must be what scrolls"


def test_the_scroll_spy_lights_one_rail_entry_not_all_of_them(hpage):
    """A shell-side observer sees nothing across the boundary, and one built in
    the frame with a percentage band computes it against the whole document
    rather than the viewport. Either way the rail is wrong, and neither has a
    string to grep for."""
    hpage.evaluate("window.scrollTo(0, 1200)")
    hpage.wait_for_timeout(700)
    lit = hpage.evaluate(
        "() => [...document.querySelectorAll('.rail-item.on')].length")
    assert lit == 1, "%d rail entries are lit" % lit


def test_one_mouseup_captures_one_selection(hpage):
    """The handler binds on the shell AND the content. Unframed those are one
    document, so a second closure would fire twice — silently, because neither
    handler is meaningfully non-idempotent."""
    n = hpage.evaluate("""() => {
      let n = 0;
      const count = () => { n++; };
      document.addEventListener('mouseup', count);
      const F = document.getElementById('cla-frame');
      F.contentDocument.addEventListener('mouseup', count);
      document.body.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
      document.removeEventListener('mouseup', count);
      F.contentDocument.removeEventListener('mouseup', count);
      return n;
    }""")
    assert n == 1, "a shell mouseup reached the handler %d times" % n


def test_the_markdown_rail_still_navigates_natively(page):
    """The regression the framed-path gating exists to prevent. Unframed, a rail
    click is native fragment navigation: it moves the page AND pushes a history
    entry, so Back returns the reader to where they were. An unconditional
    preventDefault would have taken that away on a path where nothing was
    wrong."""
    before = page.evaluate("history.length")
    page.evaluate("() => document.querySelectorAll('.rail-item')[1].click()")
    page.wait_for_timeout(400)
    after = page.evaluate("history.length")
    assert page.evaluate("location.hash"), "the rail did not set a fragment"
    assert after > before, "the rail click pushed no history entry"


def test_the_python_block_text_equals_what_the_browser_reports(hpage):
    """Both halves of the anchoring machinery rest on this, and neither can
    detect its failure: the page captures a selection as an offset into the
    block's text, and the renderer later looks for the recorded passage in the
    text it computed. When the two disagree the check reports an annotation lost
    against a document that never changed."""
    import render_html

    doc = hpage.evaluate(
        "() => document.getElementById('cla-frame').contentDocument.location.href")
    assert doc
    # What the renderer recorded, recomputed from the same source.
    _o, ctx, _w = render_html.instrument(DESIGNED)
    live = hpage.evaluate("""() => {
      const D = document.getElementById('cla-frame').contentDocument;
      const out = {};
      D.querySelectorAll('[data-blk]').forEach(e => { out[e.dataset.blk] = blockText(e); });
      return out;
    }""")
    assert live, "the page reported no blocks"
    for blk, text in ctx.blocks.items():
        assert blk in live, "block %s is on no element" % blk
        assert live[blk] == text, (
            "block %s: python %r != browser %r" % (blk, text, live[blk]))


def test_a_margin_note_stands_beside_its_block_after_scrolling(hpage):
    """The coordinate-space error is invisible at scroll position zero: a rect
    taken in the frame's viewport and used in the shell's differs by exactly the
    scroll offset, so the note is right until you move and then drifts."""
    blk = hpage.evaluate("""() => {
      const D = document.getElementById('cla-frame').contentDocument;
      const e = [...D.querySelectorAll('[data-blk]')]
        .find(x => x.textContent.includes("second section's"));
      return e && e.dataset.blk;
    }""")
    assert blk, "no block to annotate"
    hpage.evaluate("""(blk) => {
      CMT.list = [{id: 'x1', blk: blk, text: "second section's",
                   note: 'a note', at: '2026-09-07T10:00:00'}];
      render();
    }""", blk)
    hpage.evaluate("window.scrollTo(0, 1400)")
    hpage.wait_for_timeout(600)
    hpage.evaluate("() => syncMargin()")
    hpage.wait_for_timeout(400)
    got = hpage.evaluate("""() => {
      const note = document.querySelector('#gutter .mnote');
      if (!note) return null;
      const F = document.getElementById('cla-frame');
      const D = F.contentDocument;
      const mark = D.querySelector('mark.cmt-hl');
      if (!mark) return {noMark: true};
      return {note: note.getBoundingClientRect().top,
              mark: mark.getBoundingClientRect().top + F.getBoundingClientRect().top};
    }""")
    assert got and not got.get("noMark"), "nothing was painted into the frame"
    assert abs(got["note"] - got["mark"]) < 60, (
        "the note is %.0fpx from its mark after scrolling" %
        abs(got["note"] - got["mark"]))


# A document whose own sizing is viewport-relative. The frame's height IS this
# document's viewport, so sizing the frame to its content feeds straight back
# into the measurement — which is why it gets a fixture of its own.
VIEWPORT_SIZED = """<!doctype html><meta charset="utf-8">
<title>Viewport sized</title>
<style>body{margin:0;font:16px system-ui}</style>
<h2>First</h2><section style="height:100vh">One screen.</section>
<h2>Second</h2><section style="height:100vh">Another screen.</section>
"""


@pytest.fixture(scope="module")
def served_vh(tmp_path_factory):
    root = tmp_path_factory.mktemp("browser-vh")
    (root / ".git").mkdir()
    doc = root / "vh.html"
    doc.write_text(VIEWPORT_SIZED, encoding="utf-8")
    pages = tmp_path_factory.mktemp("pages-vh")
    page = pages / "vh-page.html"
    render_html.build(str(doc), str(root), str(page))

    corpus = store.path_for(str(doc), str(root))
    os.makedirs(os.path.dirname(corpus), exist_ok=True)
    open(corpus, "w", encoding="utf-8").close()
    _root, _doc, _page = str(root), str(doc), str(page)
    _key = store.doc_key(_doc, _root)

    class VhHandler(annotate_server.Handler):
        out_path = str(corpus)
        doc_path = _doc
        doc_key = _key
        root = _root
        page_path = _page
        is_change = False
        kind = "html"

    srv = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(VhHandler, directory=str(pages)))
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:%d/vh-page.html" % srv.server_address[1]
    srv.shutdown()
    srv.server_close()
    thread.join(timeout=10)


def test_a_viewport_sized_document_does_not_grow_the_frame_without_bound(browser,
                                                                        served_vh):
    """Sizing the frame to its content is a feedback loop when the document's own
    sizing is viewport-relative: the frame IS that document's viewport, so each
    fit makes `100vh` taller and the next fit taller again.

    Measured before the guard existed: 33,554,432px — the browser's maximum
    element height — within a second. It did not hang, which is worse. It
    saturated, and a saturated frame looks like a rendered page.
    """
    p = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    p.on("pageerror", lambda e: errors.append(str(e)))
    try:
        p.goto(served_vh)
        p.wait_for_function(
            "() => { const f = document.getElementById('cla-frame');"
            " return f && f.contentDocument"
            " && f.contentDocument.querySelectorAll('[data-blk]').length > 0; }")
        p.wait_for_timeout(1500)
        h = p.evaluate(
            "() => document.getElementById('cla-frame').getBoundingClientRect().height")
        assert h < 20000, "the frame ran away to %.0fpx" % h
        # And it is still usable: the document scrolls somewhere.
        scrolls = p.evaluate("""() => {
          const F = document.getElementById('cla-frame');
          const D = F.contentDocument;
          return D.documentElement.scrollHeight > D.documentElement.clientHeight
              || document.documentElement.scrollHeight > window.innerHeight;
        }""")
        assert scrolls, "neither surface can scroll; the document is unreachable"
        assert errors == [], "the page threw: %s" % errors
    finally:
        p.close()


def test_an_ordinary_document_still_gets_a_content_sized_frame(hpage):
    """The non-vacuity partner. A guard that pinned every frame to the viewport
    would pass the test above and quietly give up the outer-page scrolling the
    margin arithmetic was built on."""
    got = hpage.evaluate("""() => {
      const F = document.getElementById('cla-frame');
      return {styleH: F.style.height,
              inner: F.contentDocument.documentElement.scrollHeight,
              boxH: Math.round(F.getBoundingClientRect().height)};
    }""")
    assert got["styleH"] != "100vh", "an ordinary document was pinned to the viewport"
    assert abs(got["boxH"] - got["inner"]) < 4, got


def test_a_pinned_frame_relays_out_the_margin_as_it_scrolls(browser, served_vh):
    """A pinned frame scrolls itself, so a note's own line moves under it while
    the outer page does not move at all. Without a listener on the frame's
    scroll, every note stays where the first layout put it — beside a different
    sentence, with its tie still drawn solid, which is this page's promise that
    the note is level with its own line."""
    p = browser.new_page(viewport={"width": 1440, "height": 900})
    try:
        p.goto(served_vh)
        p.wait_for_function(
            "() => { const f = document.getElementById('cla-frame');"
            " return f && f.contentDocument"
            " && f.contentDocument.querySelectorAll('[data-blk]').length > 0; }")
        p.wait_for_timeout(1500)
        pinned = p.evaluate(
            "() => document.getElementById('cla-frame').style.height === '100vh'")
        assert pinned, "this fixture is meant to pin the frame; it did not"

        painted = p.evaluate("""() => {
          const D = document.getElementById('cla-frame').contentDocument;
          const e = [...D.querySelectorAll('[data-blk]')]
            .find(x => x.textContent.includes('One screen'));
          if (!e) return null;
          const full = blockText(e), needle = 'One screen';
          const off = full.indexOf(needle);
          CMT.list = [{id: 'v1', blk: e.dataset.blk, text: needle, off: off,
                       before: full.slice(Math.max(0, off - 60), off),
                       after: full.slice(off + needle.length,
                                         off + needle.length + 60),
                       sec: '', line: 1, note: 'a note',
                       at: '2026-09-07T10:00:00'}];
          render();
          return {marks: D.querySelectorAll('mark.cmt-hl').length,
                  lost: !!CMT.list[0].lost};
        }""")
        assert painted and not painted["lost"] and painted["marks"] == 1, painted
        p.wait_for_timeout(500)
        # Scroll the FRAME, not the page.
        p.evaluate("() => document.getElementById('cla-frame')"
                   ".contentWindow.scrollTo(0, 700)")
        p.wait_for_timeout(700)
        got = p.evaluate("""() => {
          const note = document.querySelector('#gutter .mnote');
          const F = document.getElementById('cla-frame');
          const mark = F.contentDocument.querySelector('mark.cmt-hl');
          if (!note || !mark) return null;
          return {note: note.getBoundingClientRect().top,
                  mark: mark.getBoundingClientRect().top
                      + F.getBoundingClientRect().top};
        }""")
        assert got, "nothing was painted"
        assert abs(got["note"] - got["mark"]) < 80, (
            "the note is %.0fpx from its mark after the frame scrolled"
            % abs(got["note"] - got["mark"]))
    finally:
        p.close()


def test_the_rail_says_so_when_its_section_is_gone(hpage):
    """The defensive path. A rail entry whose section is no longer in the
    document must not fall through to a fragment the shell cannot resolve —
    that is a dead click with nothing said, which is indistinguishable from a
    page that is simply not responding."""
    hpage.evaluate("""() => {
      const D = document.getElementById('cla-frame').contentDocument;
      D.querySelectorAll('[data-sec-id]').forEach(e => e.removeAttribute('data-sec-id'));
    }""")
    before = hpage.evaluate("window.scrollY")
    hpage.evaluate("() => document.querySelectorAll('.rail-item')[1].click()")
    hpage.wait_for_timeout(400)
    state = hpage.evaluate("""() => {
      const w = document.getElementById('frame-warn');
      return {hidden: w.hidden, text: (w.textContent || '').slice(0, 60),
              hash: location.hash, scrollY: window.scrollY};
    }""")
    assert not state["hidden"], "the rail failed silently"
    assert "no longer in the document" in state["text"], state
    assert state["hash"] == "", "the click fell through to a fragment"
    assert state["scrollY"] == before
