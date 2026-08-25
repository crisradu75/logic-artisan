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

# The counterpart card and the gutter both sit against a block. The gutter is
# INSIDE it, so it is declared in render_doc.INJECTED_CLASSES and stripped before
# any text is read; the card is a SIBLING, which is not decoration but a
# requirement — inside the block its words would be counted into every offset
# measured against that block, and every annotation below it would report itself
# lost against a document nobody had touched.
CHANGE_CSS = """
.tabs{display:flex;align-items:flex-end;padding:.32rem 1.1rem 0;background:var(--paper);
 border-bottom:1px solid var(--rule);position:sticky;top:2.9rem;z-index:55}
.tabs-scroll{display:flex;gap:.15rem;align-items:flex-end;flex:1;min-width:0;
 overflow-x:auto;overflow-y:hidden;padding-bottom:1px;margin-bottom:-1px;scrollbar-width:thin}
.tab{font:inherit;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.72rem;
 letter-spacing:.05em;cursor:pointer;background:transparent;border:1px solid transparent;
 border-bottom:0;border-radius:3px 3px 0 0;padding:.45rem .8rem;color:var(--muted);
 white-space:nowrap;display:flex;align-items:center;gap:.4rem;margin-bottom:-1px}
.tab:hover{color:var(--ink);background:var(--sunk)}
.tab.on{color:var(--ink);background:var(--paper);border-color:var(--rule);
 box-shadow:inset 0 2px 0 var(--accent)}
.tab-n{font-variant-numeric:tabular-nums;background:var(--mark-wash);color:var(--mark);
 border-radius:999px;padding:.02rem .34rem;font-size:0.69rem;min-width:1rem;text-align:center}
:root{--danger:#B3261E}
:root[data-theme="dark"]{--danger:#E5534B}
.tab-gap{flex:none;width:1px;align-self:center;height:1.1rem;background:var(--rule);margin:0 .7rem}
.tab-cov{border:1px dashed var(--accent-2)!important;border-radius:999px!important;
 color:var(--accent);background:var(--accent-wash);padding:.34rem .75rem;
 margin-bottom:.28rem;line-height:1.1}
.tab-cov:hover{background:var(--accent-wash);color:var(--accent);filter:brightness(.97)}
.tab-cov.on{background:var(--accent);border-style:solid!important;
 border-color:var(--accent)!important;color:var(--paper);box-shadow:none}
.cov-glyph{font-size:.72rem;line-height:1;opacity:.85}
.tab-n-cov,.tab-cov.on .tab-n-cov{background:var(--danger);color:#fff}
.rail-n-danger{color:var(--danger)}
.pane{display:none}
.pane.on{display:block}
.rail-wrap{display:none}
.rail-wrap.on{display:block}

.tgl-group{margin-left:auto;margin-bottom:.28rem;flex:none;display:flex;align-items:center;
 gap:.18rem;background:var(--sunk);border:1px solid var(--rule);border-radius:3px;
 padding:.1rem .1rem .1rem .45rem}
.tgl-l{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;letter-spacing:.16em;
 text-transform:uppercase;color:var(--muted);margin-right:.28rem;white-space:nowrap;line-height:1}
.tgl{font:inherit;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.72rem;
 cursor:pointer;color:var(--ink-2);background:transparent;border:1px solid transparent;
 border-radius:2px;padding:.2rem .5rem;letter-spacing:.07em;text-transform:uppercase;
 white-space:nowrap;line-height:1}
.tgl:hover{color:var(--accent);background:var(--paper)}
.tgl[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:var(--paper)}

/* The panes sit in the reading column of render_doc's grid, and the annotation
   margin takes the other track. `.col` inside a pane is not a DIRECT child of
   `.wrap`, so it does not pick up the sizing that neutralises the standalone
   page's centred 44rem measure — it has to be said here, or every pane
   overflows its own track. */
.wrap>.panes{min-width:0}
.panes .col{max-width:none;margin:0;padding-top:0}
.col{padding-left:4rem}
.linked{position:relative}
/* Anchored to the text's left edge rather than a fixed offset, so a block with
   three marks grows leftward into the margin instead of colliding with the
   prose — the marks stay aligned to the same edge whatever their number. */
.gut{position:absolute;right:100%;margin-right:.5rem;top:.2rem;display:flex;gap:.14rem}
.gut b{display:inline-flex;align-items:center;justify-content:center;width:1.25rem;
 height:1.25rem;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;
 font-weight:400;border-radius:2px;border:1px solid var(--accent-2);color:var(--accent);
 background:var(--accent-wash);cursor:pointer;line-height:1}
.gut b:hover{background:var(--accent);color:var(--paper)}
.gut b.weak{border-style:dashed;opacity:.75}
.cf{display:block;margin:.45rem 0 1rem;border-left:2px solid var(--accent-2);
 background:var(--accent-wash);border-radius:0 3px 3px 0;padding:.45rem .7rem;
 font-size:.82rem;line-height:1.5;color:var(--ink-2)}
.cf.weak{border-left-style:dashed}
.cf + .cf{margin-top:-.7rem;border-top:1px solid var(--paper)}
.cf-h{display:block;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;
 letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin-bottom:.2rem}
.cf-why{opacity:.7;text-transform:none;letter-spacing:.02em}
.cf-go{float:right;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;
 color:var(--accent);cursor:pointer;opacity:.75}
.cf-go:hover{opacity:1;text-decoration:underline}
body.nocf .cf{display:none}
.peek{position:absolute;z-index:97;width:min(30rem,92vw);background:var(--paper);
 border:1px solid var(--accent);border-left:3px solid var(--accent);border-radius:3px;
 box-shadow:0 8px 30px rgba(0,0,0,.24);padding:.7rem .85rem;font-size:.84rem;line-height:1.55;
 color:var(--ink-2)}
.peek-h{display:block;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;
 letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin-bottom:.35rem}
@keyframes flash{0%{background:var(--accent-wash)}100%{background:transparent}}
.flash{animation:flash 1.6s ease-out}

.pane[data-pane="__coverage__"] .col{padding-left:0}
.cov-prov{margin:0 0 .9rem;font-family:ui-monospace,Menlo,Consolas,monospace;
 font-size:.78rem;letter-spacing:.03em;color:var(--muted)}
.cov-note{color:var(--muted);font-size:.82rem;line-height:1.6;margin:.4rem 0 1.6rem}
.cov h2{font-size:1.05rem;margin:1.9rem 0 .8rem;padding:0;border:0;
 font-family:ui-monospace,Menlo,Consolas,monospace;letter-spacing:.1em;text-transform:uppercase}
.cov-bad h2{color:var(--mark)}
.cov-row{border:1px solid var(--hair);border-left:3px solid var(--accent-2);border-radius:3px;
 padding:.7rem .85rem;margin:0 0 .55rem}
.cov-bad .cov-row{border-left-color:var(--mark);background:var(--mark-wash)}
.cov-grey .cov-row{border-left-color:var(--rule)}
.cov-src,.cov-src-go{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;
 letter-spacing:.08em;text-transform:uppercase;color:var(--muted);display:block;
 margin-bottom:.25rem}
.cov-go{cursor:pointer;border-bottom:1px dotted var(--accent-2)}
.cov-go:hover{color:var(--accent);border-bottom-style:solid;background:var(--accent-wash)}
.cov-src-go{border-bottom:0;width:fit-content}
.cov-src-go:hover{color:var(--accent);background:none;text-decoration:underline}
.cov-dead{opacity:.75}
.cov-claim{margin:0;font-size:.92rem;line-height:1.5}
.cov-why{display:block;margin-top:.45rem;font-size:.86rem;line-height:1.5;color:var(--mark)}
.cov-why::before{content:"\\25B3  ";font-size:.85em}
.cov-grey .cov-why{color:var(--muted)}
.cov-grey .cov-why::before{content:"\\2014  "}
.cov-pay{display:flex;gap:.5rem;align-items:baseline;margin-top:.4rem;font-size:.84rem}
.cov-pay-k{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.7rem;color:var(--accent);
 min-width:4.6rem;flex:none;letter-spacing:.04em}
.cov-pay-k.weak{color:var(--muted)}
@media (max-width:900px){.col{padding-left:1.9rem}.gut{margin-right:.25rem}}
"""

CHANGE_JS = """
/* ---- tabs ---- */
const PANES = [...document.querySelectorAll('.pane')];
const TABS  = [...document.querySelectorAll('.tab')];
const RAILS = [...document.querySelectorAll('.rail-wrap')];
/* Every control on this page that changes the FLOW has to go through
   syncMargin, not just the resize handler. A margin note's top is an absolute
   pixel computed once from where its block was standing; switching tabs swaps
   one whole document for another, so every note would be left beside a block
   from the pane that is no longer showing — with its tie still drawn SOLID,
   which is the page's promise that the note is level with its own line. */
function showTab(key) {
  TABS.forEach(t => t.classList.toggle('on', t.dataset.tab === key));
  PANES.forEach(p => p.classList.toggle('on', p.dataset.pane === key));
  RAILS.forEach(r => r.classList.toggle('on', r.dataset.rail === key));
  syncMargin();                        // one whole document just swapped for another
}
TABS.forEach(t => t.onclick = () => { showTab(t.dataset.tab); window.scrollTo(0, 0); });

/* The one function render_doc leaves replaceable: on a page of several files a
   block cannot be scrolled to until its tab is showing. */
window.focusBlock = function (blk) {
  const h = blk ? document.querySelector('[data-blk="' + CSS.escape(blk) + '"]') : null;
  if (!h) return false;
  const pane = h.closest('[data-pane]');
  if (pane) showTab(pane.dataset.pane);
  setCmt(false);
  h.scrollIntoView({block: 'center', behavior: 'smooth'});
  h.classList.remove('flash'); void h.offsetWidth; h.classList.add('flash');
  return true;
};

/* ---- counterparts ---- */
const cfBtn = document.getElementById('cf-toggle');
cfBtn.onclick = () => {
  const on = cfBtn.getAttribute('aria-pressed') !== 'true';
  cfBtn.setAttribute('aria-pressed', String(on));
  /* `.cf{display:none}` takes every counterpart out of the FLOW, so a pane with
     thirty of them moves by thousands of pixels. Same reason as showTab. */
  document.body.classList.toggle('nocf', !on);
  syncMargin();                        // every counterpart just left the flow
};

let peek = null;
function closePeek() { if (peek) { peek.remove(); peek = null; } }
document.addEventListener('mouseover', e => {
  const b = e.target.closest('.gut b');
  if (!b) return;
  closePeek();
  peek = document.createElement('div');
  peek.className = 'peek';
  peek.innerHTML = '<span class="peek-h">' + b.dataset.label + '</span>' + b.dataset.excerpt;
  document.body.appendChild(peek);
  const r = b.getBoundingClientRect();
  peek.style.left = (window.scrollX + r.right + 8) + 'px';
  peek.style.top = (window.scrollY + r.top - 4) + 'px';
});
document.addEventListener('mouseout', e => {
  if (e.target.closest('.gut b')) closePeek();
});
document.addEventListener('click', e => {
  const go = e.target.closest('.gut b, .cf-go, .cov-go');
  if (!go) return;
  closePeek();
  window.focusBlock(go.dataset.goBlk);
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') closePeek(); });

/* The tab badges count annotations per file, from where the markers actually
   landed. Wrapped around render()'s own rail pass so both stay in step. */
const _renderInner = render;
function paintTabCounts() {
  const tally = new Map();
  openOnes().forEach(c => { if (c.file) tally.set(c.file, (tally.get(c.file) || 0) + 1); });
  TABS.forEach(t => {
    const badge = t.querySelector('.tab-n');
    if (!badge || t.classList.contains('tab-cov')) return;
    const n = tally.get(t.dataset.tab) || 0;
    badge.textContent = n;
    badge.style.visibility = n ? 'visible' : 'hidden';
  });
}
render = function () { _renderInner(); paintTabCounts(); };
render();
"""


class ChangeUnreadable(Exception):
    """This change cannot be rendered. A real exception rather than SystemExit,
    which is a BaseException: raised inside the server's worker thread it was
    caught by nothing — `_render` catches OSError, `ThreadingMixIn` catches
    Exception — and `threading` swallowed it in silence. The reader saw the
    browser's generic "Failed to fetch", identical to a dead server, while the
    one sentence saying what to fix was constructed and thrown into a void."""


def esc_attr(s):
    return html.escape(s or "", quote=True)


def add_class(html_str, blk, cls):
    """Add `cls` to the block's opening tag, merging with any class already
    there. Inserting a second `class=` attribute is not a merge — HTML keeps the
    first and silently drops the rest, so a block that already had one would lose
    it. No markdown-rendered block carries one today; `<p class="pt">` in
    plain-text mode does, and that is one caller away."""
    import re
    m = re.search(r'<(\w+)([^>]*)\bdata-blk="%s"' % re.escape(blk), html_str)
    if not m:
        return html_str
    if re.search(r'\bclass="', m.group(2)):
        return (html_str[:m.start(2)]
                + re.sub(r'\bclass="', 'class="%s ' % cls, m.group(2), count=1)
                + html_str[m.end(2):])
    return html_str[:m.end(1)] + ' class="%s"' % cls + html_str[m.end(1):]


def _outermost_block(html_str, blk):
    """The match for the outermost element carrying `data-blk` that encloses the
    one named — or the block itself when nothing encloses it."""
    import re
    m = re.search(r"<(\w+)([^>]*\bdata-blk=\"%s\")" % re.escape(blk), html_str)
    if not m:
        return None
    for outer in re.finditer(r"<(\w+)([^>]*\bdata-blk=\"[^\"]+\")", html_str):
        if outer.start() >= m.start():
            break
        if _element_end(html_str, outer) > m.start():
            return outer          # it opens before and closes after: it encloses
    return m


def _element_end(html_str, m):
    """The index just past the closing tag of the element `m` opens."""
    import re
    tag, i, depth = m.group(1), m.end(), 1
    open_re, close_re = re.compile(r"<%s\b" % tag), re.compile(r"</%s>" % tag)
    while depth and i < len(html_str):
        o, c = open_re.search(html_str, i), close_re.search(html_str, i)
        if not c:
            return len(html_str)
        if o and o.start() < c.start():
            depth += 1
            i = o.end()
        else:
            depth -= 1
            i = c.end()
    return i


def after_block(html_str, blk, extra):
    """Insert `extra` immediately after the element carrying data-blk=`blk`, and
    outside every block that encloses it.

    A sibling, never a child: inside a block, `extra`'s words are counted into
    every offset measured against that block, and annotations on it start
    reporting themselves lost against a document nobody touched.

    Closing the inner element is not enough, because blocks NEST. A nested list
    puts `<li data-blk="tasks:b2">` inside `<li data-blk="tasks:b1">`, so landing
    after the inner `</li>` lands inside the outer block — which is the failure
    this docstring already forbade, arriving one level up. Walk out to the
    outermost enclosing block first.
    """
    import re
    m = _outermost_block(html_str, blk)
    if not m:
        return html_str
    tag, i, depth = m.group(1), m.end(), 1
    open_re, close_re = re.compile(r"<%s\b" % tag), re.compile(r"</%s>" % tag)
    while depth and i < len(html_str):
        o, c = open_re.search(html_str, i), close_re.search(html_str, i)
        if not c:
            return html_str
        if o and o.start() < c.start():
            depth += 1
            i = o.end()
        else:
            depth -= 1
            i = c.end()
    return html_str[:i] + extra + html_str[i:]


def inside_block(html_str, blk, extra):
    """Insert `extra` just inside the end of the block — for the gutter, which is
    positioned against it and is declared in render_doc.INJECTED_CLASSES."""
    import re
    m = re.search(r"<(\w+)([^>]*\bdata-blk=\"%s\")" % re.escape(blk), html_str)
    if not m:
        return html_str
    tag, i, depth = m.group(1), m.end(), 1
    open_re, close_re = re.compile(r"<%s\b" % tag), re.compile(r"</%s>" % tag)
    while depth and i < len(html_str):
        o, c = open_re.search(html_str, i), close_re.search(html_str, i)
        if not c:
            return html_str
        if o and o.start() < c.start():
            depth += 1
            i = o.end()
        else:
            depth -= 1
            i = c.start() if depth == 0 else c.end()
    return html_str[:i] + extra + html_str[i:]


def bind_claims(model, ctxs):
    """Give every claim the block it was rendered into, or None.

    Bound by text, one match or none — the rule the anchor layer keeps. A claim
    that cannot be placed keeps its row in the coverage tab and loses only its
    link; it is never bound to a guess, because a link that scrolls somewhere
    arbitrary is worse than no link.
    """
    for c in model["claims"]:
        ctx = ctxs.get(c["file"])
        c["blk"] = None
        if not ctx:
            continue
        needle = c["text"][:70]
        if not needle:
            continue
        hits = [b for b, t in ctx.blocks.items() if needle in t]
        # One match or none. Two blocks holding the same text is exactly the case
        # where a guess sends the reader to the wrong passage while showing them
        # text that looks right.
        c["blk"] = hits[0] if len(hits) == 1 else None


def counterparts(model, bodies, ctxs, labels):
    """Hang a gutter mark and an inlined counterpart off every linked block."""
    by_id = {c["id"]: c for c in model["claims"]}
    per_claim = {}
    for l in model["links"]:
        for a, b in ((l["src"], l["dst"]), (l["dst"], l["src"])):
            per_claim.setdefault(a, []).append((by_id.get(b), l))

    for cid, partners in per_claim.items():
        c = by_id.get(cid)
        if not c or not c.get("blk"):
            continue
        marks, cards = "", ""
        # Strongest first: a citation, then a path, then an identifier, then
        # shared wording — so the best evidence is the one read first.
        order = {k: i for i, k in enumerate(OC.LINK_KINDS)}
        seen = set()
        # No .get default: a kind nobody ranked is a bug, and sorting it
        # quietly last is how it stays one.
        for other, link in sorted(partners, key=lambda p: order[p[1]["kind"]]):
            if not other or not other.get("blk") or other["id"] in seen:
                continue
            seen.add(other["id"])
            weak = link["kind"] == "wording"
            label = "%s · %s %s" % (labels.get(other["file"], other["file"]),
                                    other["kind"], other["num"])
            excerpt = html.escape(other["text"][:400], quote=False)
            marks += ('<b class="%s" data-label="%s" data-excerpt="%s" data-go-blk="%s">%s</b>'
                      % ("weak" if weak else "", esc_attr(label), esc_attr(excerpt),
                         esc_attr(other["blk"]), esc_attr(other["file"][0])))
            cards += ('<span class="cf%s"><span class="cf-h">%s '
                      '<span class="cf-why">%s %s</span>'
                      '<span class="cf-go" data-go-blk="%s">open in tab →</span>'
                      '</span>%s</span>'
                      % (" weak" if weak else "", esc_attr(label),
                         link["kind"], esc_attr(link["why"][:60]),
                         esc_attr(other["blk"]), excerpt))
        if not marks:
            continue
        f = c["file"]
        bodies[f] = add_class(bodies[f], c["blk"], "linked")
        bodies[f] = inside_block(bodies[f], c["blk"], '<span class="gut">%s</span>' % marks)
        bodies[f] = after_block(bodies[f], c["blk"], cards)
    return bodies


def coverage_pane(model, labels):
    cov = model["coverage"]
    st = cov["stats"]
    out = ['<h1 style="margin-top:1.4rem">Coverage</h1>',
           '<p class="cov-prov">read %d files · %d promises · %d claims · %d links · '
           '%d tasks (%d done)</p>'
           % (st["files"], st["promises"], st["claims"], st["links"],
              st["tasks"], st["tasks_done"]),
           '<p class="cov-note"><strong>Uncovered means no link was found</strong>, which is '
           'not the same as no link existing — every row says what was looked for. '
           'A bullet naming no file and no identifier gives nothing to match on at all; '
           'those are listed separately rather than counted against the change.</p>']

    def go(claim, inner, cls="cov-go"):
        if not claim.get("blk"):
            return '<span class="cov-dead">%s</span>' % inner
        return ('<span class="%s" data-go-blk="%s">%s</span>'
                % (cls, esc_attr(claim["blk"]), inner))

    def rows(items, css, heading):
        if not items:
            return ""
        buf = ['<div class="%s"><h2>%s — %d</h2>' % (css, heading, len(items))]
        for row in items:
            c = row["claim"]
            src = "%s · %s %s" % (labels.get(c["file"], c["file"]), c["kind"], c["num"])
            pays = "".join(
                '<div class="cov-pay"><span class="cov-pay-k%s">%s %s</span>%s</div>'
                % (" weak" if link["kind"] == "wording" else "",
                   labels.get(o["file"], o["file"]), o["num"],
                   go(o, html.escape(o["text"][:150], quote=False)))
                for o, link in row.get("pays", [])[:6])
            buf.append('<div class="cov-row">%s<p class="cov-claim">%s</p>'
                       '%s%s</div>'
                       % (go(c, src, "cov-go cov-src-go"),
                          go(c, html.escape(c["text"][:300], quote=False)),
                          '<span class="cov-why">%s</span>' % html.escape(row["why"])
                          if row.get("why") else "", pays))
        buf.append("</div>")
        return "".join(buf)

    if not st["promises"]:
        # "Nothing was parsed" and "nothing is wrong" printed identically, in the
        # one view whose whole purpose is saying what nothing answers.
        out.append('<div class="cov cov-bad"><h2>Nothing to check</h2>'
                   '<div class="cov-row"><span class="cov-src">proposal</span>'
                   '<p class="cov-claim">No <code>## What Changes</code> bullets were '
                   'found.</p><span class="cov-why">this tab has nothing to check — '
                   'coverage below is empty because nothing was parsed, not because '
                   'nothing is owed</span></div></div>')
    out.append(rows(cov["uncovered"], "cov cov-bad", "Uncovered"))
    out.append(rows(cov.get("undone", []), "cov cov-grey", "Not done"))
    out.append(rows(cov["unchecked"], "cov cov-grey", "Not checkable"))
    out.append(rows(cov["covered"], "cov", "Covered"))

    caps = [c for c in cov["capabilities"] if c["why"]]
    if caps:
        out.append('<div class="cov cov-bad"><h2>Capabilities — %d</h2>' % len(caps))
        for c in caps:
            out.append('<div class="cov-row"><span class="cov-src">capability</span>'
                       '<p class="cov-claim">%s</p><span class="cov-why">%s</span></div>'
                       % (html.escape(c["name"]), html.escape(c["why"])))
        out.append("</div>")
    return "".join(out)


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

    model = OC.build(change_dir, texts)
    bind_claims(model, ctxs)
    bodies = counterparts(model, bodies, ctxs, labels)

    change_key = store.doc_key(change_dir, root)
    total_words = sum(len(t.split()) for c in ctxs.values() for t in c.blocks.values())

    tabs, panes, rails = [], [], []
    for i, (key, label, _p) in enumerate(files):
        on = " on" if i == 0 else ""
        tabs.append('<button class="tab%s" data-tab="%s">%s'
                    '<span class="tab-n" style="visibility:hidden">0</span></button>'
                    % (on, esc_attr(key), html.escape(label)))
        panes.append('<div class="pane%s" data-pane="%s"><div class="col">%s</div></div>'
                     % (on, esc_attr(key), bodies[key]))
        rails.append('<div class="rail-wrap%s" data-rail="%s"><p class="rail-h">%s</p>%s</div>'
                     % (on, esc_attr(key), html.escape(label), R.rail(ctxs[key].sections)))

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
    return 0


if __name__ == "__main__":
    sys.exit(main())
