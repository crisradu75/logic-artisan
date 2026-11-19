#!/usr/bin/env python3
"""Render a whole OpenSpec change as one annotatable page: its files in tabs,
their correlations shown in place, and a derived coverage view.

Stdlib only, and it runs on Windows and POSIX alike.

    python3 <plugin>/skills/annotate/scripts/render_change.py remove-update-cla

**The four files are only worth reading together because a claim in one is
answered in another.** Tabs alone cannot show that — they show one side at a
time — so the correlation is carried by two things that need no click: a margin
gutter marking which other files reference a block, and the counterpart itself
inlined beneath the block it answers to. The coverage tab then asks the question
no layout answers: what does nothing cover.

**The coverage tab is derived and is dressed to say so** — set apart from the
file tabs by a rule, shaped as a pill rather than a folder tab. A reader who
takes it for a file goes looking for it on disk.

Everything about anchoring, selection and the annotation corpus comes from
[render_doc.py](render_doc.py) and [annotations_store.py](annotations_store.py)
unchanged. This module adds panes, links and coverage; it does not reimplement
the layer that decides where an annotation lives, because two copies of that
would disagree the first time either was touched.
"""
import argparse
import html
import io
import os
import sys

import annotations_store as store
import openspec_change as OC
import render_doc as R

from render_change_assets import CHANGE_CSS, CHANGE_JS
from render_change_markup import bind_claims, counterparts, esc_attr, mark_groups
from render_change_panes import (
    coverage_pane,
    diff_cards,
    is_archived,
    main_specs_dir,
    overview_pane,
    read_main_specs,
    read_skip_specs,
)

# Names this module held before its parts were split out: other scripts and the tests read them from here.
from render_change_markup import (
    REQ_GROUPS,
    add_attr,
    add_class,
    after_block,
    heading_blk,
    heading_lookup,
    inside_block,
    section_class,
)
from render_change_panes import (
    BUCKET_LABELS,
    NO_SPECS_DIR,
    PROMISE_CLIP,
    diff_markup,
    main_spec_path,
    spec_label,
)

# The one class, defined where discovery raises it (see its docstring); the
# server catches it under this name.
ChangeUnreadable = OC.ChangeUnreadable


class _MergedCtx:
    """Every pane's blocks under one roof, for the anchor check.

    Block ids are namespaced per file, so they cannot collide — which is what
    makes one merged view of them correct rather than merely convenient.
    """

    def __init__(self, ctxs):
        self.blocks = {}
        for ctx in ctxs.values():
            self.blocks.update(ctx.blocks)


def check_change_anchors(ctxs, corpus):
    """Which open annotations no longer find their text anywhere in the change.

    The single-document path has done this from the beginning; the change path
    did not, and printed a cheerful build summary over a corpus whose every
    anchor the rebuild had just orphaned. That is the case where anchors are most
    fragile — several files, all edited in response to the very review the
    annotations are — and it was the one with no reporting at all.
    """
    return R.check_anchors(_MergedCtx(ctxs), corpus)


def build(change_dir, root=None, out=None):
    root = root or store.repo_root(change_dir)
    files = OC.change_files(change_dir)
    if not files:
        raise ChangeUnreadable("no readable files in %s" % change_dir)

    texts, bodies, ctxs, labels = {}, {}, {}, {}
    for key, label, path in files:
        with open(path, "r", encoding="utf-8") as fh:
            texts[key] = fh.read()
        labels[key] = label
        bodies[key], ctxs[key] = R.render_document(
            texts[key], os.path.dirname(path), prefix=key + ":")

    archived = is_archived(change_dir)
    caps = [k[len("spec-"):] for k in texts if k.startswith("spec-")]
    # An archived change is never compared — see OC.requirement_diffs — so its
    # main specs are not even read; nor is anything for a change folder that has
    # no main specs folder, whose notes then say why.
    specs_dir = main_specs_dir(change_dir)
    main_specs = ({} if archived or specs_dir is None
                  else read_main_specs(specs_dir, caps))
    model = OC.build(change_dir, texts, main_specs, archived,
                     skip_specs=read_skip_specs(change_dir))
    bind_claims(model, ctxs)
    bodies = counterparts(model, bodies, ctxs, labels)
    bodies = diff_cards(model, bodies, ctxs, specs_dir, root)
    bodies = mark_groups(model, bodies, ctxs)

    change_key = store.doc_key(change_dir, root)
    total_words = sum(len(t.split()) for c in ctxs.values() for t in c.blocks.values())

    # The page opens on the overview, a derived tab dressed like coverage: the
    # change's shape before any one file of it.
    ov = OC.overview(model, texts)
    tabs = ['<button class="tab tab-cov tab-ov on" data-tab="__overview__">'
            '<span class="cov-glyph">≡</span>overview</button>'
            '<span class="tab-gap"></span>']
    panes = ['<div class="pane on" data-pane="__overview__"><div class="col">%s</div></div>'
             % overview_pane(ov, labels)]
    done, total = ov["tasks"]
    rails = ['<div class="rail-wrap on" data-rail="__overview__"><p class="rail-h">overview</p>'
             + "".join(
                 # Each entry jumps to its heading in the overview pane.
                 '<a class="rail-item" href="#%s" data-depth="0"><span class="rail-main">'
                 '<span class="rail-title">%s</span></span><span class="rail-meta">'
                 '<span class="rail-n">%s</span></span></a>' % (anchor, name, n)
                 for anchor, name, n in (
                     ("ov-promises", "Promises", len(ov["promises"])),
                     ("ov-requirements", "Requirements",
                      sum(sum(g.values()) for g in ov["reqs"].values())),
                     ("ov-tasks", "Tasks", "%d/%d" % (done, total))))
             + "</div>"]
    for key, label, _p in files:
        tabs.append('<button class="tab" data-tab="%s">%s'
                    '<span class="tab-n" style="visibility:hidden">0</span></button>'
                    % (esc_attr(key), html.escape(label)))
        panes.append('<div class="pane" data-pane="%s"><div class="col">%s</div></div>'
                     % (esc_attr(key), bodies[key]))
        rails.append('<div class="rail-wrap" data-rail="%s"><p class="rail-h">%s</p>%s</div>'
                     % (esc_attr(key), html.escape(label), R.rail(ctxs[key].sections)))

    cov = model["coverage"]
    bad = len(cov["uncovered"]) + len([c for c in cov["capabilities"] if c["why"]])
    undone = cov.get("undone", [])
    tabs.append('<span class="tab-gap"></span>'
                '<button class="tab tab-cov" data-tab="__coverage__">'
                '<span class="cov-glyph">∑</span>coverage'
                '<span class="tab-n tab-n-cov">%d</span></button>' % bad)
    panes.append('<div class="pane" data-pane="__coverage__"><div class="col">%s</div></div>'
                 % coverage_pane(model, labels))
    rails.append('<div class="rail-wrap" data-rail="__coverage__">'
                 '<p class="rail-h">coverage</p>'
                 + "".join(
                     '<a class="rail-item" href="#" data-depth="0"><span class="rail-main">'
                     '<span class="rail-title">%s</span></span><span class="rail-meta">'
                     '<span class="rail-n%s">%d</span></span></a>'
                     % (name, " rail-n-danger" if danger else "", n)
                     for name, n, danger in (("Uncovered", len(cov["uncovered"]), True),
                                             ("Not done", len(undone), False),
                                             ("Not checkable", len(cov["unchecked"]), False),
                                             ("Covered", len(cov["covered"]), False)))
                 + "</div>")

    toggle = ('<span class="tgl-group"><span class="tgl-l">show</span>'
              '<button class="tgl" id="cf-toggle" aria-pressed="true">counterparts</button>'
              '</span>')

    page = (R.page(os.path.basename(change_dir), change_key, "", 0, 0)
            .replace("</head>", "<style>" + CHANGE_CSS + "</style>\n</head>"))
    # The reading half of render_doc's page, with an empty document in it — the
    # exact run this build replaces with its own tabbed shell. Built from
    # R.SHELL_MARKUP rather than hand-copied: a hand-copied literal turns into a
    # silent no-op the moment that markup changes, and the change page then
    # renders with an empty column and no error anywhere.
    target = ('<div class="shell">' + R.SHELL_MARKUP.replace("__BODY__", "")
              + '</div>')
    shell = ('<div class="tabs"><div class="tabs-scroll">' + "".join(tabs) + '</div>'
             + toggle + '</div>\n'
             '<div class="shell"><nav class="rail" aria-label="Sections">'
             + "".join(rails) + '</nav>'
             '<main class="page"><div class="wrap">'
             '<div class="panes" id="doc">' + "".join(panes) + '</div>'
             '<div class="gutter" id="gutter" aria-label="Annotations in the margin"></div>'
             '</div></main></div>')
    if target not in page:
        # Never a silent no-op. This is a string match against another module's
        # markup, which is exactly the coupling that breaks without a symptom.
        raise ChangeUnreadable(
            "render_doc's shell markup did not match what this build expects; "
            "the tabbed shell was not substituted")
    page = page.replace(target, shell)
    page = page.replace("</body>", "<script>" + CHANGE_JS + "</script>\n</body>")
    page = page.replace("0 blocks · 0 words",
                        "%d files · %d blocks · %s words"
                        % (len(files), sum(len(c.blocks) for c in ctxs.values()),
                           format(total_words, ",d")))

    out = out or os.path.join(R.page_dir(root), "change-" + os.path.basename(change_dir) + ".html")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    return out, model, ctxs


def main(argv=None):
    # This prints requirement names and claim text. On Windows a piped stdout
    # is the locale codepage, and one `ț` in a heading raised
    # UnicodeEncodeError after the page was already written.
    import render_html
    render_html.use_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("change", help="a change id, or the path to its directory")
    ap.add_argument("--root", help="repo root (default: resolved from git)")
    ap.add_argument("--out", help="where to write the page")
    a = ap.parse_args(argv)

    root = os.path.abspath(a.root) if a.root else store.repo_root(a.change)
    d = OC.find_change(a.change, root)
    if not d:
        print("no such change: %s" % a.change)
        print("looked in openspec/changes/ and openspec/changes/archive/")
        return 1
    out, model, ctxs = build(d, root, a.out)
    cov = model["coverage"]
    st = cov["stats"]
    print("built     %d files, %d blocks  ->  %s"
          % (st["files"], sum(len(c.blocks) for c in ctxs.values()), out))
    print("claims    %d · %d links · %d tasks (%d done)"
          % (st["claims"], st["links"], st["tasks"], st["tasks_done"]))
    print("coverage  %d uncovered · %d not checkable · %d covered · %d task(s) not done"
          % (len(cov["uncovered"]), len(cov["unchecked"]), len(cov["covered"]),
             len(cov.get("undone", []))))
    if not st["promises"]:
        print("          NO PROMISES PARSED — no `## What Changes` bullets found;"
              " coverage is empty because nothing was read, not because nothing is owed")
    corpus = store.path_for(d, root)
    checked, lost, problems, fatal = check_change_anchors(ctxs, corpus)
    if fatal:
        print("CORPUS UNREADABLE: %s" % fatal)
    elif checked:
        print("anchors   %d open, %d could not be read back" % (checked, len(lost)))
        if lost:
            # Named, not just counted: these are the ones the reader cannot see
            # in place on the page, so they are the ones to read first.
            print("          ANCHOR LOST: %s" % ", ".join(lost[:10]))
    if problems:
        print("          %d line(s) of %s could not be read" % (len(problems), corpus))
    unbound = [c for c in model["claims"] if not c.get("blk")]
    if unbound:
        # Reported, never hidden: a claim with no block is a row the reader
        # cannot click back to, and knowing how many there are is how they judge
        # whether the tab is trustworthy on this change.
        print("          %d claim(s) could not be bound to a block" % len(unbound))
    unplaced = model.get("unplaced", [])
    if unplaced:
        print("          %d requirement(s) whose label or diff could not be placed: %s"
              % (len(unplaced), ", ".join("%s (%s)" % (r["claim"]["text"], r["why"])
                                          for r in unplaced[:5])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
