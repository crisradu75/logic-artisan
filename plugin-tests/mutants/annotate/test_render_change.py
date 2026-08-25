"""Mutants for the change page's seam with render_doc, and its own reflow.

The seam is a string match against another module's markup — the coupling that
breaks with no symptom, and the one this change had to touch to put a margin in.

    python3 plugin-tests/mutate.py plugin-tests/mutants/annotate/test_render_change.py
"""
from pathlib import Path

DEV = Path(__file__).resolve().parents[2]                 # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
CHANGE = PLUGIN / "skills" / "annotate" / "scripts" / "render_change.py"
TESTS = [DEV / "tests" / "skills" / "annotate" / "test_render_change.py"]

MUTANTS = [
    ("the shell substitution goes back to a silent no-op",
     CHANGE,
     "    if target not in page:",
     "    if False:",
     TESTS),

    # Both call sites carry a distinguishing trailing comment, because an anchor
    # may not span a newline (see mutate.py) and `  syncMargin();` alone appears
    # at both — an ambiguous anchor mutates a site you did not mean, and a kill
    # on the wrong site reads exactly like a kill on the right one.
    ("switching tabs stops re-laying-out the margin",
     CHANGE,
     "  syncMargin();                        // one whole document just swapped for another",
     "  /* nothing */",
     TESTS),

    ("hiding the counterparts stops re-laying-out the margin",
     CHANGE,
     "  syncMargin();                        // every counterpart just left the flow",
     "  /* nothing */",
     TESTS),

    ("the panes stop being sized to their own grid track, so every one overflows",
     CHANGE,
     ".panes .col{max-width:none;margin:0;padding-top:0}",
     ".panes .col{margin:0;padding-top:0}",
     TESTS),

    # The dead-call shape, at both flow-control sites. The first version of the
    # test that guards these was a presence check, and `if (false) syncMargin();`
    # still CONTAINS "syncMargin()" — measured surviving at both.
    ("switching tabs re-lays-out the margin only in a branch that never runs",
     CHANGE,
     "  syncMargin();                        // one whole document just swapped for another",
     "  if (false) syncMargin();",
     TESTS),

    ("hiding the counterparts re-lays-out the margin only in a branch that never runs",
     CHANGE,
     "  syncMargin();                        // every counterpart just left the flow",
     "  if (false) syncMargin();",
     TESTS),

    ("the panes' grid track refuses to shrink below its content, so every pane "
     "overflows it",
     CHANGE,
     ".wrap>.panes{min-width:0}",
     ".wrap>.panes{min-width:auto}",
     TESTS),

    # Targets BOTH test files. The floor is enforced by a single parametrised
    # test that sweeps the doc page and the change page together, and it lives in
    # test_render_doc.py — so this batch's own TESTS list does not run it, and the
    # mutant survived on the first attempt for that reason alone. A mutant whose
    # covering test is in another file has to say so.
    ("type on the change page drops back below the 11px floor",
     CHANGE,
     ".cf-h{display:block;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;",
     ".cf-h{display:block;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.56rem;",
     TESTS + [DEV / "tests" / "skills" / "annotate" / "test_render_doc.py"]),
]
