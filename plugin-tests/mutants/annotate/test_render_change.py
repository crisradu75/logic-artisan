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
]
