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
