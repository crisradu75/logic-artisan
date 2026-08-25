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
     "    let top = c.mark.getBoundingClientRect().top + window.scrollY - top0 - 6;",
     "    let top = c.mark.parentElement.getBoundingClientRect().top + window.scrollY - top0 - 6;",
     TESTS),
]
