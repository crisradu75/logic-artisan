"""Mutants for the annotation margin, the badges, the undo and the legibility floor.

What is mutated is what the change TOUCHED rather than only what it targeted: a
mutant that re-breaks the headline case says nothing about the branch beside it.
Two pairs here exist because their first version SURVIVED — a presence check
reads `if (false) syncMargin();` as a live call, and an absence check for the
literal "· DELETE FAILED" misses the same caption spelled `\\u00b7`.

    python3 plugin-tests/mutate.py plugin-tests/mutants/annotate/test_render_doc.py
"""
from pathlib import Path

DEV = Path(__file__).resolve().parents[2]                 # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
DOC = PLUGIN / "skills" / "annotate" / "scripts" / "render_doc.py"
TESTS = [DEV / "tests" / "skills" / "annotate" / "test_render_doc.py"]

MUTANTS = [
    # ---- the margin ----
    ("the margin note is anchored to a mark that is merely CONNECTED, so a block "
     "on a tab that is not showing gets a note beside nothing",
     DOC,
     "c.mark.getClientRects().length",
     "c.mark.isConnected",
     TESTS),

    ("the inline marker is drawn whether or not there is a margin, so every "
     "annotation appears twice with two delete buttons",
     DOC,
     "    if (paintedMarginOff) {",
     "    if (true) {",
     TESTS),

    ("opening the drawer stops re-laying-out the margin",
     DOC,
     "  syncMargin();",
     "  /* nothing */",
     TESTS),

    ("opening the drawer re-lays-out the margin only in a branch that never runs",
     DOC,
     "  syncMargin();",
     "  if (false) syncMargin();",
     TESTS),

    ("a resize stops re-laying-out the margin",
     DOC,
     "addEventListener('resize', () => { clearTimeout(marginT); marginT = setTimeout(syncMargin, 120); });",
     "addEventListener('resize', () => { clearTimeout(marginT); });",
     TESTS),

    ("the margin never folds away, so an open drawer lands on top of it",
     DOC,
     " body.cmt .gutter{display:none}",
     " body.cmt .gutter{display:block}",
     TESTS),

    # ---- state as a badge ----
    ("a failure state goes back to being a caption suffix, spelled with an escape",
     DOC,
     "    + stateBadge(c)",
     "    + (c.delFailed ? ' \\u00b7 DELETE FAILED' : '')",
     TESTS),

    ("a failure state goes back to being a caption suffix, spelled literally",
     DOC,
     "    + stateBadge(c)",
     "    + (c.editFailed ? ' · EDIT NOT SAVED' : '')",
     TESTS),

    ("only the worst badge prints and the rest are dropped, hiding the more "
     "serious of a pair",
     DOC,
     "  const more = all.length > 1 ? ' +' + (all.length - 1) : '';",
     "  const more = '';",
     TESTS),

    # ---- undo ----
    ("a delete stops offering a way back",
     DOC,
     "    offerUndo(rec);",
     "    hideUndo();",
     TESTS),

    ("the undo strip stays in the tab order after its window closes",
     DOC,
     "  UNDO.bar.toggleAttribute('inert', !on);",
     "  UNDO.bar.classList.toggle('was-on', !!on);",
     TESTS),

    ("the closed drawer keeps its ten controls in the tab order",
     DOC,
     '<aside class="drawer" id="cdrawer" aria-label="Annotations" inert aria-hidden="true">',
     '<aside class="drawer" id="cdrawer" aria-label="Annotations">',
     TESTS),

    # ---- legibility ----
    ("type drops back below the 11px floor",
     DOC,
     ".cmt-loc{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;color:var(--muted);",
     ".cmt-loc{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.63rem;color:var(--muted);",
     TESTS),

    ("--muted goes back to failing AA on the drawer's own ground",
     DOC,
     "--muted:#585E62;",
     "--muted:#6E7478;",
     TESTS),

    ("--mark goes back to failing AA as text",
     DOC,
     "--mark:#9E4718;",
     "--mark:#C8622F;",
     TESTS),

    ("the favicon's bar drifts from --mark, so the tab wears the old colour",
     DOC,
     "'<style>.a{fill:#2F5C57}.b{fill:#9E4718}'",
     "'<style>.a{fill:#2F5C57}.b{fill:#C8622F}'",
     TESTS),

    ("the favicon loses its dark override, so the tab keeps the light bar",
     DOC,
     "'@media (prefers-color-scheme:dark){.a{fill:#84B8B0}.b{fill:#E0915E}}</style>'",
     "'</style>'",
     TESTS),
]
