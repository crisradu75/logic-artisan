"""Mutants for the browser gate — the regressions that survived every string check.

Each of these was measured surviving all 46 source-inspection tests on this page
during review. They are here to show the browser gate is not decorative: it
catches what a grep structurally cannot.

    python3 plugin-tests/mutate.py plugin-tests/mutants/annotate/test_page_in_a_browser.py
"""
from pathlib import Path

DEV = Path(__file__).resolve().parents[2]                 # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
DOC = PLUGIN / "skills" / "annotate" / "scripts" / "render_doc.py"
TESTS = [DEV / "tests" / "skills" / "annotate" / "test_page_in_a_browser.py"]

MUTANTS = [
    ("the stacking push goes, so two notes on one block are drawn on top of "
     "each other and one cannot be read at all",
     DOC,
     "    if (top < floor + 8) { top = floor + 8; el.classList.add('stacked'); }",
     "    if (false) { top = floor + 8; el.classList.add('stacked'); }",
     TESTS),

    ("marginOff's comparison is inverted",
     DOC,
     "getComputedStyle(GUTTER).display === 'none'",
     "getComputedStyle(GUTTER).display !== 'none'",
     TESTS),

    ("the margin stops folding away, so an open drawer covers it",
     DOC,
     " body.cmt .gutter{display:none}",
     " body.cmt .gutter{display:block}",
     TESTS),

    ("the wide layout stops reserving room for the drawer",
     DOC,
     " body.cmt .page{padding-right:27rem}",
     " body.cmt .page{padding-right:0}",
     TESTS),

    ("a retried undo splices the same record in a second time",
     DOC,
     "  if (CMT.list.indexOf(rec) < 0) {",
     "  if (true) {",
     TESTS),

    ("the note is anchored to its block's top rather than its own mark",
     DOC,
     "    let top = contentRect(c.mark).top + window.scrollY - top0 - 6;",
     "    let top = contentRect(c.mark.parentElement).top + window.scrollY - top0 - 6;",
     TESTS),

    # ---- the frame ----

    ("contentRect drops the frame's own offset, so every rect taken inside the "
     "frame is read as if the frame began at the top of the page",
     DOC,
     "  const f = FRAME.getBoundingClientRect();",
     "  const f = {top: 0, left: 0};",
     TESTS),

    # DELETED: "the scroll-spy observer is built in the SHELL's window".
    # It could not be killed, and not because the tests are weak: measured with
    # the frame sized to its content first, a shell-side observer and a
    # frame-side one light the same single correct heading. The two expressions
    # agree on every input a correct tree reaches, so the mutant discriminates
    # nothing. The frame-side form is kept for ordering (see design decision 4),
    # which is not a difference a mutant can express. Left in the batch it would
    # have been a survivor nobody could act on.

    ("the observer's band stays a percentage, which inside a content-sized "
     "frame resolves against the whole document rather than the viewport",
     DOC,
     "  if (!FRAME) return '-12% 0px -70% 0px';",
     "  return '-12% 0px -70% 0px'; if (!FRAME)",
     TESTS),

    ("the input handlers bind on the shell only, so nothing inside the frame "
     "ever reaches them",
     DOC,
     "  if (CDOC !== document) CDOC.addEventListener(type, handler, opts);",
     "  /* nothing */",
     TESTS),

    ("the rail intercept stops being gated on the framed path, taking the "
     "history entry away from the Markdown rail too",
     DOC,
     "    if (!FRAME) return;\n    /* By section id, not by the href's slug.",
     "    /* By section id, not by the href's slug.",
     TESTS),

    ("readiness stops excluding about:blank, so the layer initialises against "
     "the frame's empty placeholder document",
     DOC,
     "            && d.location && d.location.href !== 'about:blank');",
     "            );",
     TESTS),

    ("the frame is left at its default height, so it scrolls itself and the "
     "margin arithmetic loses the offset it depends on",
     DOC,
     "    lastH = h;\n    FRAME.style.height = h + 'px';",
     "    lastH = h;",
     TESTS),

    # ---- Revise round 1: the runaway frame and its neighbours ----

    ("the frame stops detecting that it is growing itself, so a viewport-sized "
     "document inflates the frame to the browser's maximum element height",
     DOC,
     "    if (fits > 6 || (lastH && h > lastH + 4 && fits > 2)) {",
     "    if (false) {",
     TESTS),

    ("every frame is pinned to the viewport, giving up the outer-page scrolling "
     "the margin arithmetic was built on",
     DOC,
     "    if (fits > 6 || (lastH && h > lastH + 4 && fits > 2)) {",
     "    if (true) {",
     TESTS),

    ("a pinned frame stops re-laying-out the margin as it scrolls, so every "
     "note drifts away from its own line",
     DOC,
     "      CWIN.addEventListener('scroll', syncMargin);",
     "      /* nothing */",
     TESTS),

    ("the rail stops preventing default on a miss, so a click navigates nowhere "
     "and says nothing",
     DOC,
     "    e.preventDefault();\n    const sec = a.dataset.goSec;",
     "    const sec = a.dataset.goSec;",
     TESTS),
]
