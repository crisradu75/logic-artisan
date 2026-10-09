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


def _a(text):
    """A multi-line anchor carrying render_change.py's own line separator: the
    file may be CRLF on disk in a clone with `core.autocrlf` on (see mutate.py,
    KEEP `\\n` OUT OF AN ANCHOR)."""
    nl = "\r\n" if b"\r\n" in CHANGE.read_bytes() else "\n"
    return text.replace("\n", nl)


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
     '        bodies[c["file"]] = after_block(bodies[c["file"]], blk, card)',
     '        bodies[c["file"]] = inside_block(bodies[c["file"]], blk, card)',
     TESTS),

    ("a diff that cannot be placed vanishes",
     CHANGE,
     '            _unplaced(model, c, "diff", why)',
     "            pass",
     TESTS),

    ("a label that cannot be placed vanishes",
     CHANGE,
     '            _unplaced(model, c, "label", why)',
     "            pass",
     TESTS),

    ("the coverage pane stops listing what could not be placed",
     CHANGE,
     _a('    unplaced = model.get("unplaced", [])\n    if unplaced:\n        out.append('),
     _a('    unplaced = []\n    if unplaced:\n        out.append('),
     TESTS),

    ("render_change's CLI prints requirement names through the locale codepage",
     CHANGE,
     "    render_html.use_utf8_stdout()",
     "    pass",
     TESTS),

    ("sweep_changes' CLI prints change text through the locale codepage",
     PLUGIN / "skills" / "annotate" / "scripts" / "sweep_changes.py",
     "    render_html.use_utf8_stdout()",
     "    pass",
     TESTS),

    ("the server's CLI prints document names through the locale codepage",
     PLUGIN / "skills" / "annotate" / "scripts" / "annotate_server.py",
     "    render_html.use_utf8_stdout()",
     "    pass",
     TESTS),

    ("a requirement header in lower case gets no label",
     CHANGE,
     '        m = re.match(r"(?i)requirement:\\s*(.*)$", " ".join(text.split()))',
     '        m = re.match(r"Requirement:\\s*(.*)$", " ".join(text.split()))',
     TESTS),

    ("a covered promise's chip goes back to a teal too light to read",
     CHANGE,
     ".ov-covered,.ov-modified{border-color:var(--accent);color:var(--accent)}",
     ".ov-covered,.ov-modified{border-color:var(--accent);color:var(--accent-2)}",
     TESTS + [DEV / "tests" / "skills" / "annotate" / "test_render_doc.py"]),

    ("the MODIFIED label goes back to a teal too light to read",
     CHANGE,
     " letter-spacing:.12em;line-height:1.2;color:var(--accent);background:transparent}",
     " letter-spacing:.12em;line-height:1.2;color:var(--accent-2);background:transparent}",
     TESTS + [DEV / "tests" / "skills" / "annotate" / "test_render_doc.py"]),

    ("the group label is no longer drawn from its attribute",
     CHANGE,
     "h3[data-group]::before{content:attr(data-group);",
     'h3[data-group]::before{content:"";',
     TESTS + [DEV / "tests" / "skills" / "annotate" / "test_render_doc.py"]),

    ("a heading closed with ### is never found",
     CHANGE,
     '    name = " ".join(OC.strip_md(OC._norm_name(claim.get("raw") or claim["text"])).split())',
     '    name = " ".join(claim["text"].split())',
     TESTS),

    ("a repeated heading is reported as not found",
     CHANGE,
     '    return None, "heading not found" if not hits else "heading not unique"',
     '    return None, "heading not found"',
     TESTS),

    ("an unchanged requirement is called unchanged again",
     CHANGE,
     '        "same": "no word-level difference from %s" % spec,',
     '        "same": "unchanged · the same text as %s" % spec,',
     TESTS),

    ("a diff note names the repo's path instead of the file it read",
     CHANGE,
     "    p = os.path.abspath(main_spec_path(specs_dir, cap))",
     '    p = os.path.abspath(os.path.join(root, "openspec", "specs", cap, "spec.md"))',
     TESTS),

    ("a change folder outside changes/ borrows the repo's main specs",
     CHANGE,
     _a("    else:\n        return None\n    return os.path.join(os.sep.join(base) or os.sep, \"specs\")"),
     _a("    else:\n        base = real[:-2]\n    return os.path.join(os.sep.join(base) or os.sep, \"specs\")"),
     TESTS),

    ("a change folder with no main specs gets a note that does not say why",
     CHANGE,
     '        return "no base · " + NO_SPECS_DIR',
     '        return "no base"',
     TESTS),

    ("an archive folder spelled in another case is missed where the OS folds case",
     CHANGE,
     "    return os.path.normcase(os.path.normpath(os.path.abspath(change_dir))).split(os.sep)",
     "    return os.path.normpath(os.path.abspath(change_dir)).split(os.sep)",
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
     "        base = real[:-3]",
     "        base = real[:-2]",
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
     '    if ov["skip_specs"] and not ov["reqs"]:',
     "    if False:",
     TESTS),

    ("skip_specs beside real deltas says nothing about the conflict",
     CHANGE,
     '    elif ov["skip_specs"]:',
     "    elif False:",
     TESTS),

    ("skip_specs hides the requirements table even when there are deltas",
     CHANGE,
     '    if ov["reqs"]:',
     '    if ov["reqs"] and not ov["skip_specs"]:',
     TESTS),

    ("a capability of unknown status is shown as modified",
     CHANGE,
     '            kind = ov["status"].get(cap, "unknown")',
     '            kind = "new" if ov["status"].get(cap) == "new" else "modified"',
     TESTS),

    ("a missing ## Why leaves the overview silent",
     CHANGE,
     '        out.append(none("nothing parsed · the proposal has no ## Why section"))',
     "        pass",
     TESTS),

    ("no promises leaves the overview silent",
     CHANGE,
     '        out.append(none("nothing parsed · no top-level bullets under the proposal\'s "',
     '        out.append(("" ',
     TESTS),

    ("a change with no tasks.md shows 0 of 0 done",
     CHANGE,
     '    if not ov["tasks_file"]:',
     "    if False:",
     TESTS),

    ("a cut promise carries no ellipsis",
     CHANGE,
     '    return text if len(text) <= n else text[:n].rstrip() + "…"',
     "    return text[:n]",
     TESTS),

    ("the overview rail goes back to links that lead nowhere",
     CHANGE,
     "                 '<a class=\"rail-item\" href=\"#%s\" data-depth=\"0\"><span class=\"rail-main\">'",
     "                 '<a class=\"rail-item\" href=\"#\" data-x=\"%s\" data-depth=\"0\"><span class=\"rail-main\">'",
     TESTS),

    ("the dark coverage badge goes back to white text on the lighter red",
     CHANGE,
     ':root[data-theme="dark"] .tab-n-cov,:root[data-theme="dark"] .tab-cov.on .tab-n-cov{color:var(--paper)}',
     ':root[data-theme="dark"] .tab-n-cov,:root[data-theme="dark"] .tab-cov.on .tab-n-cov{color:#fff}',
     TESTS + [DEV / "tests" / "skills" / "annotate" / "test_render_doc.py"]),

    ("an inserted word goes back to a teal too light to read on its wash",
     CHANGE,
     ".rd-ins{color:var(--accent);background:var(--accent-wash);",
     ".rd-ins{color:var(--accent-2);background:var(--accent-wash);",
     TESTS + [DEV / "tests" / "skills" / "annotate" / "test_render_doc.py"]),

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
