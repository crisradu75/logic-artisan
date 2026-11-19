"""The change page's own stylesheet and script, on top of `render_doc.py`'s.

Page text only: two string constants, read by `render_change.py`. Not a
command.
"""


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
:root[data-theme="dark"]{--danger:#E85D55}
.tab-gap{flex:none;width:1px;align-self:center;height:1.1rem;background:var(--rule);margin:0 .7rem}
.tab-cov{border:1px dashed var(--accent-2)!important;border-radius:999px!important;
 color:var(--accent);background:var(--accent-wash);padding:.34rem .75rem;
 margin-bottom:.28rem;line-height:1.1}
.tab-cov:hover{background:var(--accent-wash);color:var(--accent);filter:brightness(.97)}
.tab-cov.on{background:var(--accent);border-style:solid!important;
 border-color:var(--accent)!important;color:var(--paper);box-shadow:none}
.cov-glyph{font-size:.72rem;line-height:1;opacity:.85}
.tab-n-cov,.tab-cov.on .tab-n-cov{background:var(--danger);color:#fff}
/* Dark --danger is light enough to read as TEXT on every dark surface, so white
   on it falls short of 4.5:1 and the dark paper does not. The command that
   measures both is the test:
     python3 -m pytest plugin-tests/tests/skills/annotate/test_render_doc.py -k wcag */
:root[data-theme="dark"] .tab-n-cov,:root[data-theme="dark"] .tab-cov.on .tab-n-cov{color:var(--paper)}
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
/* Two lines until asked. Unclamped, a card is about as tall as the bullet it
   answers, and a proposal with a card under every bullet reads twice as long. */
.cf-x{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;
 cursor:pointer}
.cf.open .cf-x{display:block}
.cf-x:focus-visible{outline-offset:1px}
body.nocf .cf{display:none}
.peek{position:absolute;z-index:97;width:min(30rem,92vw);background:var(--paper);
 border:1px solid var(--accent);border-left:3px solid var(--accent);border-radius:3px;
 box-shadow:0 8px 30px rgba(0,0,0,.24);padding:.7rem .85rem;font-size:.84rem;line-height:1.55;
 color:var(--ink-2)}
.peek-h{display:block;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;
 letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin-bottom:.35rem}
/* A requirement's group, drawn from an attribute rather than written into the
   heading: generated content is not in textContent, so the heading's text — what
   annotation offsets count against — is unchanged. Teal, never --mark, which
   means "annotated" everywhere on this page. */
h3[data-group]::before{content:attr(data-group);display:inline-block;vertical-align:.14em;
 margin-right:.6rem;padding:.1rem .42rem;border:1px solid var(--accent);border-radius:2px;
 font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;font-weight:400;
 letter-spacing:.12em;line-height:1.2;color:var(--accent);background:transparent}
h3[data-group="ADDED"]::before{background:var(--accent);color:var(--paper)}
h3[data-group="REMOVED"]::before{border-color:var(--danger);color:var(--danger)}
/* Colour, not opacity: a faded passage still has to be read, and selected. */
.req-removed,.req-removed h3,.req-removed h4,.req-removed h5,.req-removed h6,
.req-removed strong,.req-removed code{color:var(--muted)}
.req-removed h3{text-decoration:line-through;text-decoration-thickness:1px}
.req-removed .rm-why{color:var(--ink-2);border-left:2px solid var(--danger);padding-left:.7rem}
.req-removed .rm-why strong{color:var(--ink-2)}
/* A MODIFIED requirement's diff against the main spec: a sibling under its
   heading, like a counterpart, so none of its words are counted into a block.
   --danger is read as TEXT here, so it answers to the same 4.5:1 as --muted. */
.rd{margin:.2rem 0 1rem;border-left:2px solid var(--rule);padding:.35rem .7rem;
 font-size:.86rem;line-height:1.55;color:var(--ink-2)}
.rd-h{display:block;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;
 letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:.2rem}
.rd-note .rd-h{margin:0;text-transform:none;letter-spacing:.02em}
.rd-t{margin:0}
.rd-del{color:var(--danger);text-decoration:line-through;text-decoration-thickness:1px}
.rd-ins{color:var(--accent);background:var(--accent-wash);text-decoration:underline;
 text-decoration-thickness:1px;text-underline-offset:2px;border-radius:2px;padding:0 .1em}
.rd-gap{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.72rem;color:var(--muted)}
@keyframes flash{0%{background:var(--accent-wash)}100%{background:transparent}}
.flash{animation:flash 1.6s ease-out}

.pane[data-pane="__coverage__"] .col,.pane[data-pane="__overview__"] .col{padding-left:0}
.ov-why{font-size:1.02rem;line-height:1.6;color:var(--ink-2);margin:0 0 1.4rem}
.ov h2{font-size:1.05rem;margin:1.9rem 0 .8rem;padding:0;border:0;
 font-family:ui-monospace,Menlo,Consolas,monospace;letter-spacing:.1em;text-transform:uppercase}
.ov-list{list-style:none;padding:0;margin:0}
.ov-p{margin:0 0 .55rem;line-height:1.5;font-size:.92rem}
.ov-chip{display:inline-block;font-family:ui-monospace,Menlo,Consolas,monospace;
 font-size:0.69rem;letter-spacing:.08em;text-transform:uppercase;line-height:1.2;
 padding:.1rem .4rem;border-radius:2px;border:1px solid var(--rule);color:var(--muted);
 margin-right:.35rem;vertical-align:.1em;white-space:nowrap}
.ov-covered,.ov-modified{border-color:var(--accent);color:var(--accent)}
.ov-new{border-color:var(--accent);background:var(--accent);color:var(--paper)}
.ov-uncovered{border-color:var(--danger);color:var(--danger)}
.ov-breaking{border-color:var(--danger);background:var(--danger);color:var(--paper)}
.ov-none{color:var(--muted);font-size:.9rem;margin:0}
.ov-reqs td,.ov-reqs th{padding:.3rem .7rem .3rem 0;text-align:left}
.ov-n{font-variant-numeric:tabular-nums;font-family:ui-monospace,Menlo,Consolas,monospace}
.ov-tasks{display:flex;align-items:center;gap:.8rem;margin:0}
.ov-bar{flex:1;max-width:18rem;height:4px;background:var(--hair);border-radius:2px;overflow:hidden}
.ov-bar i{display:block;height:100%;background:var(--accent-2)}
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

/* A counterpart opens to its full text on a click, Enter or Space. Its height
   changes, so every block below it moves — the same reason as showTab. */
function toggleCf(cf) {
  const open = !cf.classList.contains('open');
  cf.classList.toggle('open', open);
  const x = cf.querySelector('.cf-x');
  if (x) x.setAttribute('aria-expanded', String(open));
  syncMargin();                        // one counterpart just grew or shrank
}
document.addEventListener('click', e => {
  const cf = e.target.closest('.cf');
  if (!cf || e.target.closest('.cf-go')) return;
  // A drag that selected text inside the card ends in a click; that reader was
  // selecting, not asking for the card to change size under the selection.
  const sel = window.getSelection();
  if (sel && !sel.isCollapsed) return;
  toggleCf(cf);
});
document.addEventListener('keydown', e => {
  if (e.key !== 'Enter' && e.key !== ' ') return;
  const x = e.target.closest && e.target.closest('.cf-x');
  if (!x) return;
  e.preventDefault();
  toggleCf(x.closest('.cf'));
});

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
