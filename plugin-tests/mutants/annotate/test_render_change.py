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

    # ------------------------------------------------ counterpart clamp
    ("opening a counterpart stops re-laying-out the margin",
     CHANGE,
     "  syncMargin();                        // one counterpart just grew or shrank",
     "  /* nothing */",
     TESTS),

    ("opening a counterpart re-lays-out the margin only in a branch that never runs",
     CHANGE,
     "  syncMargin();                        // one counterpart just grew or shrank",
     "  if (false) syncMargin();",
     TESTS),

    ("a counterpart is no longer clamped to two lines",
     CHANGE,
     "-webkit-line-clamp:2;overflow:hidden;",
     "-webkit-line-clamp:none;overflow:hidden;",
     TESTS),

    # ------------------------------------------------ requirement diffs
    ("a diff card lands inside its heading, so its words count into the block",
     CHANGE,
     '        bodies[c["file"]] = after_block(bodies[c["file"]], blk, diff_markup(rec))',
     '        bodies[c["file"]] = inside_block(bodies[c["file"]], blk, diff_markup(rec))',
     TESTS),

    ("an archived change is never recognised as archived",
     CHANGE,
     '    return len(parts) >= 3 and parts[-2] == "archive" and parts[-3] == "changes"',
     "    return False",
     TESTS),

    ("an active change's main specs are read from the repo root, not beside it",
     CHANGE,
     '    elif len(parts) >= 2 and parts[-2] == "changes":',
     "    elif False:",
     TESTS),

    ("an archived change's main specs folder is read from the wrong level",
     CHANGE,
     "        base = parts[:-3]",
     "        base = parts[:-2]",
     TESTS),

    ("a main spec that is not UTF-8 fails the whole build",
     CHANGE,
     "        except UnicodeDecodeError as e:",
     "        except KeyError as e:",
     TESTS),

    ("dark-mode --danger goes back to a red that fails AA on the drawer's ground",
     CHANGE,
     ':root[data-theme="dark"]{--danger:#E85D55}',
     ':root[data-theme="dark"]{--danger:#E5534B}',
     TESTS + [DEV / "tests" / "skills" / "annotate" / "test_render_doc.py"]),

    # ------------------------------------------------ overview
    ("the page no longer opens on the overview",
     CHANGE,
     "    panes = ['<div class=\"pane on\" data-pane=\"__overview__\"><div class=\"col\">%s</div></div>'",
     "    panes = ['<div class=\"pane\" data-pane=\"__overview__\"><div class=\"col\">%s</div></div>'",
     TESTS),

    ("a breaking promise shows no chip",
     CHANGE,
     '            if c["id"] in ov["breaking"]:',
     "            if False:",
     TESTS),

    ("a skip_specs change shows an empty requirements table instead of saying so",
     CHANGE,
     '    if ov["skip_specs"]:',
     "    if False:",
     TESTS),

    ("the .openspec.yaml flag is never read",
     CHANGE,
     "            return OC.skip_specs_set(fh.read())",
     "            return False",
     TESTS),

    ("the renamed column shows when nothing was renamed",
     CHANGE,
     '        renamed = any(ov["renamed"].values())',
     "        renamed = True",
     TESTS),

    # ------------------------------------------------ requirement groups
    ("a requirement heading never gets its group label",
     CHANGE,
     "    attr = '%s=\"%s\"' % (name, esc_attr(value))",
     "    return html_str",
     TESTS),

    ("a removed requirement's sections are never set apart",
     CHANGE,
     '    return html_str[:m.end(1)] + " " + cls + html_str[m.end(1):]',
     "    return html_str",
     TESTS),

    ("a removed requirement's span runs past the next group heading",
     CHANGE,
     '                           itertools.takewhile(lambda s: s["level"] > 3,',
     '                           itertools.takewhile(lambda s: s["level"] > 1,',
     TESTS),

    ("a removed requirement's Reason block is never marked",
     CHANGE,
     '                    bodies[f] = add_class(bodies[f], b, "rm-why")',
     "                    pass",
     TESTS),
]
