"""The first half of the annotation page's script: the page chrome.

The content root, the theme, the navigation rail and the drawer. `render_doc.py`
joins this with `render_doc_js_notes.JS_NOTES` into the one script the page
carries; the join is a plain string concatenation, so the two halves are one
function scope in the browser. Page text only. Not a command.
"""


JS_PAGE = r"""
const DOC = __DOC__;

/* ---- the content root ----
   The document being annotated is either this page's own body (Markdown and
   plain text) or a frame holding the author's own HTML, whose CSS must not
   reach this page's and whose page's CSS must not reach it. Every content-side
   call goes through CDOC/CWIN so the two are one code path; unframed they ARE
   `document`/`window`, and that identity is the whole safety argument for
   touching a path that already worked.

   They are `let` because a frame's document does not exist yet when this runs.
   Nothing content-side may run before onContentReady's callback. */
const FRAME = document.getElementById('cla-frame');
let CDOC = document, CWIN = window;

/* A fresh frame's contentDocument is `about:blank`, and about:blank is already
   `readyState === 'complete'` — so the obvious readiness test passes against an
   empty document and every lookup after it returns null. The symptom is a frame
   left at its unstyled default height and lookups that find nothing for content
   plainly in the file. The href check is what distinguishes the placeholder from the real
   document. */
function contentReady() {
  if (!FRAME) return true;
  const d = FRAME.contentDocument;
  return !!(d && d.body && d.readyState === 'complete'
            && d.location && d.location.href !== 'about:blank');
}

/* Same-origin is a SERVING property, not a structural one. Opened straight off
   disk Chromium gives both documents opaque origins, `contentDocument` throws,
   and the page renders with no annotation layer — silently, looking merely
   empty. Engines differ here (Firefox treats `file:` documents as same-origin),
   which is itself a reason to detect the condition rather than reason about it. Detected
   rather than prevented: nothing stops a reader opening the path the renderer
   prints. Gated on the framed path, because a Markdown page over `file:` has no
   frame, needs no origin, and has always worked. */
function warnIfUnserved() {
  if (!FRAME || location.protocol !== 'file:') return false;
  const el = document.getElementById('frame-warn');
  if (el) {
    el.textContent = 'This page has to be served to be read: an HTML document is'
      + ' shown in a frame, and a page opened from disk cannot reach into it.'
      + ' Run the annotate server on this document and open the URL it prints.';
    el.hidden = false;
  }
  FRAME.hidden = true;
  /* The unframed path always reaches render(), so the opener shows the count and
     any fatal. Returning early here skipped that, and a `file:` page could not
     even report that the server was unreachable. */
  try { render(); } catch (e) {}
  return true;
}

/* One place for a message the reader can actually see. The frame path has
   several ways to end up with a document and no layer, and every one of them
   looks identical to "this document has no annotations yet". */
function note(msg) {
  const el = document.getElementById('frame-warn');
  if (!el) return;
  if (!el.hidden && el.textContent === msg) return;
  el.textContent = msg;
  el.hidden = false;
  /* The banner sits ABOVE the frame, so showing it pushes the frame down and
     every margin note is off by its height until something re-lays them out.
     `syncMargin` is this page's one entry point for "the geometry moved", and a
     banner appearing is exactly that. Guarded because `note()` can fire before
     the layer is wired, which is the case it was written for. */
  try { syncMargin(); } catch (e) {}
}

function onContentReady(fn) {
  if (!FRAME) { fn(); return; }
  if (warnIfUnserved()) return;
  /* A frame whose `load` never fires — a 404, a blocked request, a stall —
     leaves the layer unwired forever with nothing said anywhere. There is no
     event for "this is not going to load", so the only way to report it is to
     stop waiting. */
  const waited = setTimeout(() => {
    note('the document did not load, so nothing on this page can be annotated.'
       + ' Check the server is still running and rebuild.');
  }, 10000);
  const done = fn;
  fn = () => { clearTimeout(waited); done(); };
  const go = () => {
    CDOC = FRAME.contentDocument;
    CWIN = FRAME.contentWindow;
    fn();
  };
  if (contentReady()) go();
  else FRAME.addEventListener('load', go, {once: true});
}

/* Bind a listener on the shell AND on the content, which are the same object
   unframed. `addEventListener` de-duplicates only an identical
   (type, callback, capture) triple, so the handler must be ONE named function
   passed to both — an inline arrow at each call site creates two closures and
   fires twice. The guard makes that independent of how it is called. */
function onBoth(type, handler, opts) {
  document.addEventListener(type, handler, opts);
  if (CDOC !== document) CDOC.addEventListener(type, handler, opts);
}

const CMT = {list:[], problems:[], err:null, fatal:null, readonly:false, pending:null, el:{
  btn:  document.getElementById('sel-btn'),
  pop:  document.getElementById('cmt-pop'),
  anch: document.getElementById('cmt-anchor'),
  where:document.getElementById('cmt-where'),
  text: document.getElementById('cmt-text'),
  list: document.getElementById('cmt-list'),
  st:   document.getElementById('cmt-status'),
  n:    document.getElementById('cmt-count'),
  open: document.getElementById('cmt-open'),
}};

/* ---- theme ----
   Light is the default, and the system preference is deliberately not consulted:
   the page opens the same way on every machine. Dark is a choice the reader
   makes here, and it is remembered. The root already carries data-theme="light"
   from the renderer, so nothing flashes while this runs. */
(function () {
  const btn = document.getElementById('t-theme');
  let choice = null;
  try { choice = localStorage.getItem('cla-annotate-theme'); } catch (e) {}
  const apply = () => {
    const dark = choice === 'dark';
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
    btn.title = dark ? 'Light theme' : 'Dark theme';
  };
  btn.onclick = () => {
    choice = choice === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem('cla-annotate-theme', choice); } catch (e) {}
    apply();
  };
  apply();
})();

/* ---- the navigation rail ----
   Which entry is lit is decided by an observer over the sections rather than by
   scroll arithmetic, so it stays right when the page reflows — which it does on
   every repaint, because painting an annotation inserts a marker into the prose. */
const RAIL = new Map(
  [...document.querySelectorAll('.rail-item')].map(a => [a.dataset.goSec, a]));

/* The band the scroll-spy lights within. Percentages resolve against the ROOT's
   height, and inside a frame sized to its own content that root is the whole
   document rather than the visible viewport. On a document several screens
   tall that makes the band several times too tall, and it lights several
   entries at once. So the framed path states the same intent in pixels off the
   outer viewport, where the percentages meant what they say. */
function railBand() {
  if (!FRAME) return '-12% 0px -70% 0px';
  const h = window.innerHeight;
  return '-' + Math.round(h * 0.12) + 'px 0px -' + Math.round(h * 0.70) + 'px 0px';
}

function wireRail() {
  if (!RAIL.size) return;
  /* Constructed in the CONTENT's window, not the shell's — for ORDERING, not
     capability. A shell-side observer works too, once the frame has been sized
     to its content; measured both ways, each lit the same single correct
     heading. But `wireRail()` runs BEFORE the frame is fitted, and an observer
     that is only correct in one order is one refactor away from being wrong.

     An earlier comment here claimed a shell-side observer "reported 0 of 12".
     That measurement was real and the conclusion was not: it was taken with the
     frame still at its default height, so every target below the fold was
     outside the frame's box and genuinely did not intersect. Recorded because
     the wrong version was fixed in the design doc and left standing here, which
     is how one corrected fact becomes two contradictory comments. */
  const Obs = CWIN.IntersectionObserver;
  let io = null;
  const wire = () => {
    if (io) io.disconnect();
    io = new Obs(entries => {
      entries.forEach(e => {
        if (!e.isIntersecting) return;
        const a = RAIL.get(e.target.dataset.secId);
        if (!a) return;
        RAIL.forEach(x => x.classList.remove('on'));
        a.classList.add('on');
      });
    }, {rootMargin: railBand()});
    /* `[data-sec-id]` rather than `.sec`: the HTML path injects no wrappers, and
       the Markdown path's wrapper already carries the attribute, so the two
       converge instead of needing a rule each. */
    CDOC.querySelectorAll('[data-sec-id]').forEach(s => io.observe(s));
  };
  wire();
  if (FRAME) window.addEventListener('resize', wire);
  RAIL.forEach(a => a.addEventListener('click', e => {
    RAIL.forEach(x => x.classList.remove('on'));
    a.classList.add('on');
    /* Only the framed path intercepts. Unframed, `rail()` emits a plain anchor
       with no listener and the browser's own fragment navigation runs: it moves
       the page AND pushes a history entry, so Back returns to where the reader
       was. Calling preventDefault() on both paths would take that entry away on
       the Markdown path too, where nothing was wrong — and this design's first
       goal is that the Markdown path is provably unchanged. Framed, the shell
       holds no element with the target id, so the fragment goes nowhere and the
       scroll has to be done here. */
    if (!FRAME) return;
    /* By section id, not by the href's slug. The instrumentation adds no `id`
       to the author's headings — it may not, since an author's own id would win
       the collision and the fragment would land somewhere arbitrary — so the
       slug names nothing inside the frame. `data-sec-id` is ours and is on the
       heading that opens each section. */
    /* preventDefault FIRST. The shell holds no element with the fragment's id,
       so falling through on a miss navigates nowhere and looks like a dead
       click with nothing said. */
    e.preventDefault();
    const sec = a.dataset.goSec;
    const h = sec ? CDOC.querySelector('[data-sec-id="' + CSS.escape(sec) + '"]') : null;
    if (!h) { note('that section is no longer in the document; rebuild the page.'); return; }
    h.scrollIntoView({block: 'center', behavior: 'smooth'});
  }));
}

/* How many open annotations sit in each section. Derived from where the markers
   actually landed rather than from the stored section name: a heading that has
   been retitled since would otherwise leave its annotations uncounted, and the
   rail would say a section was never argued with. */
function paintRailCounts() {
  if (!RAIL.size) return;
  const tally = new Map();
  openOnes().forEach(c => {
    if (!c.blk || c.lost) return;
    const el = CDOC.querySelector('[data-blk="' + CSS.escape(c.blk) + '"]');
    if (!el) return;
    /* The block's own id first, its nearest labelled ancestor second. The
       HTML path injects no wrapper to close over, so `closest('.sec')`
       returned null for every block and every badge read zero. */
    const holder = el.dataset.secId ? el : el.closest('[data-sec-id]');
    if (!holder) return;
    const id = holder.dataset.secId;
    tally.set(id, (tally.get(id) || 0) + 1);
  });
  RAIL.forEach((a, id) => {
    const badge = a.querySelector('.rail-c');
    if (!badge) return;
    const n = tally.get(id) || 0;
    badge.textContent = n;
    badge.hidden = !n;
    badge.title = n === 1 ? '1 annotation' : n + ' annotations';
  });
}

/* ---- the drawer ---- */
/* A closed drawer is translated off-screen, which removes it from view and from
   nothing else: every button inside it stayed in the tab order, so tabbing
   across the page walked an invisible list of edit and delete controls. `inert`
   is what actually takes it out — and it is set here rather than in the CSS
   because it also has to be true before the first click, which the initial call
   below provides. */
function setCmt(on) {
  document.body.classList.toggle('cmt', on);
  CMT.el.open.setAttribute('aria-expanded', String(on));
  const dr = document.getElementById('cdrawer');
  if (dr) { dr.toggleAttribute('inert', !on); dr.setAttribute('aria-hidden', String(!on)); }
  /* Above the wide breakpoint the margin stays up while the drawer is open, so
     both surfaces would render an editor for the same record; below it the
     margin folds away entirely. Either way the answer to "is there a margin"
     changes with the drawer, so opening or closing one is a geometry event.
     Called unguarded: syncMargin is a function declaration and is hoisted, and
     every caller of setCmt runs after load. A `typeof` guard here bought
     nothing and made the call impossible to distinguish, in a test, from a call
     that can never fire. */
  syncMargin();
}
CMT.el.open.onclick = () => setCmt(!document.body.classList.contains('cmt'));
document.getElementById('cd-x').onclick = () => setCmt(false);
document.getElementById('scrim').onclick = () => setCmt(false);
function openList(id) {
  setCmt(true);
  const el = document.getElementById('card-' + id);   // not `card` — that is the renderer
  if (el) el.scrollIntoView({block:'center', behavior:'smooth'});
}

/* Bring a block into view. On a single-document page that is a scroll; on a page
   of several files the tab has to change first, so a multi-file page replaces
   this one function rather than carrying its own copy of the anchor layer. */
window.focusBlock = function (blk) {
  const h = blk ? CDOC.querySelector('[data-blk="' + CSS.escape(blk) + '"]') : null;
  if (!h) return false;
  setCmt(false);
  h.scrollIntoView({block: 'center', behavior: 'smooth'});
  return true;
};

/* Everything the renderer injects that the document does not contain. An
   annotation records the document's characters, so every one of these must come
   out before text is read or offsets are counted — in all three places, from
   this one constant. */
const NON_SOURCE = '__NON_SOURCE__';

function blockText(el) {
  const c = el.cloneNode(true);
  c.querySelectorAll(NON_SOURCE).forEach(s => s.remove());
  return c.textContent;
}

/* Text nodes of a block, with the markers left out. blockText(), the offset
   captured on selection and the offset replayed on paint must all agree about
   what counts as text, or a second annotation in an already-marked block lands
   one character out and reports itself lost. */
function textNodes(host) {
  const w = CDOC.createTreeWalker(host, NodeFilter.SHOW_TEXT, {
    acceptNode: n => n.parentElement && n.parentElement.closest(NON_SOURCE)
      ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT
  });
  const out = []; let n;
  while ((n = w.nextNode())) out.push(n);
  return out;
}

/* An element's or range's rect in OUTER VIEWPORT coordinates.

   The coordinate space is the whole point of stating this precisely. A raw
   `getBoundingClientRect()` is viewport-relative, so a helper returning "page
   coordinates when framed, the raw rect when not" would be returning two
   different spaces that differ by the scroll offset — an error that grows as
   you scroll, which is the `top:-135.78px` defect class this page already paid
   for. Both branches return viewport coordinates; callers keep their own
   `+ window.scrollY` term, which is already right against the outer viewport.

   It takes an element OR a range, because the selection-button site measures a
   Range and has no element at all. The arithmetic, by way of example: an inner
   rect of 5688 with the frame's own top at -5304 puts the element at 384 in the
   outer viewport. */
function contentRect(target) {
  const r = target.getBoundingClientRect();
  if (!FRAME) return r;
  const f = FRAME.getBoundingClientRect();
  return {top: r.top + f.top, bottom: r.bottom + f.top,
          left: r.left + f.left, right: r.right + f.left,
          width: r.width, height: r.height};
}

/* Locate a painted selection in the source text of its block. What the browser
   hands back is what is on screen, and that is not always what the block says —
   CSS can transform it and layout can insert breaks the source does not have.
   Four passes, narrowest first — exact, case-folded, whitespace-normalised,
   whitespace-stripped — each returning the SOURCE spelling
   rather than the painted one. One match or none at every pass: guessing files
   an annotation against the wrong sentence while showing text that looks right. */
function findLoose(full, text) {
  const only = (hay, needle) => {
    const a = hay.indexOf(needle);
    return (a < 0 || hay.indexOf(needle, a + 1) >= 0) ? -1 : a;
  };
  let i = only(full, text);
  if (i >= 0) return [i, text];
  i = only(full.toLowerCase(), text.toLowerCase());
  if (i >= 0) return [i, full.substr(i, text.length)];
  const map = []; let norm = '';
  for (let k = 0; k < full.length; k++) {
    const ws = /\s/.test(full[k]);
    if (ws && norm.endsWith(' ')) continue;
    norm += ws ? ' ' : full[k];
    map.push(k);
  }
  const nt = text.replace(/\s+/g, ' ').trim().toLowerCase();
  if (!nt) return null;
  let j = only(norm.toLowerCase(), nt);
  if (j >= 0) {
    const start = map[j];
    const end = map[Math.min(j + nt.length - 1, map.length - 1)];
    return [start, full.slice(start, end + 1)];
  }
  const tmap = []; let tight = '';
  for (let k = 0; k < full.length; k++) {
    if (/\s/.test(full[k])) continue;
    tight += full[k]; tmap.push(k);
  }
  const tt = text.replace(/\s+/g, '').toLowerCase();
  if (!tt) return null;
  j = only(tight.toLowerCase(), tt);
  if (j < 0) return null;
  const ts = tmap[j];
  const te = tmap[Math.min(j + tt.length - 1, tmap.length - 1)];
  return [ts, full.slice(ts, te + 1)];
}

function captureSelection() {
  const sel = CWIN.getSelection();
  if (!sel || sel.isCollapsed) return null;
  if (sel.toString().trim().length < 2) return null;
  const rng = sel.getRangeAt(0);
  const el = n => n && (n.nodeType === 1 ? n : n.parentElement);
  /* Anchor to the block the selection starts in, or the nearest one enclosing
     it, and keep only the part of the selection inside that block. A selection
     running across a paragraph break ends in the next one, and requiring both
     ends in the same block returned nothing at all. */
  let host = el(rng.startContainer).closest('[data-blk]')
          || el(rng.commonAncestorContainer).closest('[data-blk]');
  if (!host) return null;

  /* The text is taken from the range's own contents, clipped to the block and
     with the markers stripped — never from sel.toString(). A block that already
     carries an annotation has a marker inside it, and the selection swallows the
     marker's digits, so the captured string is not a substring of the block and
     no amount of matching will find it. */
  const clip = rng.cloneRange();
  if (!host.contains(rng.startContainer)) clip.setStart(host, 0);
  if (!host.contains(rng.endContainer)) clip.setEnd(host, host.childNodes.length);
  const box = CDOC.createElement('div');
  box.appendChild(clip.cloneContents());
  box.querySelectorAll(NON_SOURCE).forEach(x => x.remove());
  let text = box.textContent.trim();
  if (text.length < 2) return null;
  const full = blockText(host);
  let off = -1, seen = 0;
  for (const n of textNodes(host)) {
    if (n === rng.startContainer) { off = seen + rng.startOffset; break; }
    seen += n.nodeValue.length;
  }
  if (off < 0 || full.substr(off, text.length) !== text) {
    const hit = findLoose(full, text);
    if (!hit) return null;
    off = hit[0]; text = hit[1];
  }
  return {
    blk: host.dataset.blk,
    line: Number(host.dataset.line) || 0,
    sec: host.dataset.sec || '',
    /* Which file the passage came from, read off the enclosing pane. Empty on a
       single-document page, which has no panes — the field costs nothing there
       and is the whole address on a page holding a change's four files. */
    file: (host.closest('[data-pane]') || {dataset: {}}).dataset.pane || '',
    off, text,
    /* Sixty characters is the authoritative figure and it is set here. The
       replay uses the inner 24 to bracket the passage; the far context usually
       survives an edit and what is immediately around the selection usually
       does not. Anything quoting "sixty" elsewhere is quoting this. */
    before: full.slice(Math.max(0, off - 60), off),
    after:  full.slice(off + text.length, off + text.length + 60),
  };
}

/* Named and passed to both, so the de-dup rule applies and the unframed
   path registers one listener rather than two closures. */
function onMouseUp(e) {
  if (e.target.closest('#cmt-pop') || e.target.closest('#sel-btn')
      || e.target.closest('.drawer')) return;
  /* While the popup is open it is QUOTING the pending passage. Letting a new
     selection replace `pending` underneath it filed the note against a passage
     the reader was not looking at — and the stored record is self-consistent, so
     nothing downstream could ever notice. */
  if (!CMT.el.pop.hidden) return;
  const cap = captureSelection();
  const b = CMT.el.btn;
  if (!cap) { b.hidden = true; return; }
  const r = contentRect(CWIN.getSelection().getRangeAt(0));
  b.style.left = (window.scrollX + r.left) + 'px';
  b.style.top  = (window.scrollY + r.bottom + 8) + 'px';
  b.hidden = false;
  CMT.pending = cap;
}

CMT.el.btn.addEventListener('mousedown', e => {
  e.preventDefault();
  const cap = CMT.pending; if (!cap) return;
  const b = CMT.el.btn, p = CMT.el.pop;
  b.hidden = true;
  p.style.left = Math.min(parseFloat(b.style.left), window.scrollX + innerWidth - 420) + 'px';
  p.style.top  = b.style.top;
  p.hidden = false;
  CMT.el.anch.textContent = '"' + cap.text + '"';
  CMT.el.where.textContent = (cap.sec || DOC) + ' · line ' + cap.line;
  CMT.el.text.value = '';
  CMT.el.text.focus();
});

function closePop() { CMT.el.pop.hidden = true; CMT.el.btn.hidden = true; CMT.pending = null; }
document.getElementById('cmt-cancel').onclick = closePop;
/* One Escape handler, and the innermost thing wins. Editing is checked first and
   from the LIST rather than from the focused element: the note being edited is
   the most recent thing opened, and cancelling it must work whether focus is
   still in the textarea or the reader has clicked away — otherwise Escape
   closes the whole drawer over an open edit, which loses the same keystrokes it
   was pressed to discard.

   Cancelling changes nothing. The textarea is re-rendered from `c.note` on every
   render and `c.note` is only ever written by editNote(), so dropping out of edit
   mode restores the stored wording by construction rather than by an undo. */
function onKeyDown(e) {
  if (e.key !== 'Escape') return;
  const editing = CMT.list.find(c => c.editing);
  if (editing) { editing.editing = false; render(); return; }
  if (!CMT.el.pop.hidden) return closePop();
  if (document.body.classList.contains('cmt')) setCmt(false);
}

async function submit() {
  const cap = CMT.pending, note = CMT.el.text.value.trim();
  if (!cap || !note) return closePop();
  if (CMT.readonly) {
    /* Refusing the write is right; discarding what was typed is not. The note
       goes into the list as unsaved, which the card and the counter already
       know how to show. */
    closePop();
    CMT.list.push(Object.assign({note, doc: DOC, unsaved: true,
                                 id: localId()}, cap));
    return render();
  }
  closePop();
  await postAnnotation(Object.assign({note, doc: DOC}, cap));
}
document.getElementById('cmt-save').onclick = () => submit();
CMT.el.text.addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') submit();
});

/* Never `CMT.list.length`: it is reused after a delete, and two records sharing
   an id means find() returns the first while filter() removes both. */
let LOCAL_N = 0;
function localId() { return 'local-' + (++LOCAL_N) + '-' + Date.now(); }

async function postAnnotation(rec) {
  try {
    const r = await fetch('/api/annotations', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(rec)
    });
    if (!r.ok) {
      /* A refused write is not an absent server, and saying so is the only
         message that tells the reader what to fix. */
      let msg = 'HTTP ' + r.status;
      try { msg = (await r.json()).error || msg; } catch (e) {}
      throw new Error(msg);
    }
    const j = await r.json();
    if (j.record) Object.assign(rec, j.record);   // adopt what was actually stored
    rec.id = j.id || rec.id;
    rec.unsaved = false;
    CMT.err = null;
  } catch (err) {
    rec.id = rec.id || localId();
    rec.unsaved = true;
    CMT.err = String(err.message || err);
  }
  CMT.list.push(rec);
  render();
}

/* Nothing leaves the list until the tombstone lands. Removing the card first and
   swallowing the error means watching an annotation vanish while it stays live
   in the corpus. */
async function del(id) {
  const rec = CMT.list.find(c => c.id === id); if (!rec) return;
  if (rec.unsaved && String(rec.id).startsWith('local-')) {
    /* A local- id means postComment's catch fired, which happens for a lost
       response as well as a failed write — so this record MAY be on the file
       under a server id. Dropping it from the page is still right, because the
       page has no id the server would accept; the strip says what is actually
       known rather than claiming a clean removal. */
    CMT.list = CMT.list.filter(c => c.id !== id);
    undoBar(true, 'Removed from this page. It was never confirmed saved, so it'
                + ' may still be in the annotations file.', null);
    clearTimeout(undoT);
    undoT = setTimeout(hideUndo, 9000);
    return render();
  }
  rec.deleting = true;
  /* A retry must not look identical to the failure it is retrying: stateBadge
     tests delFailed first, so leaving it set shows "delete failed" over an
     in-flight second attempt. */
  rec.delFailed = false;
  render();
  rec.wasAt = CMT.list.indexOf(rec);          // so undo can put it back in place
  try {
    const r = await fetch('/api/annotations', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id, deleted: true})});
    if (!r.ok) {
      /* The server distinguishes an unreadable corpus from a failed write from a
         refused amendment, and says which in the body. Throwing the status alone
         drops the one sentence naming what to fix. */
      let msg = 'HTTP ' + r.status;
      try { msg = (await r.json()).error || msg; } catch (e) {}
      throw new Error(msg);
    }
    CMT.list = CMT.list.filter(c => c.id !== id);
    CMT.err = null;
    /* The corpus is append-only, so the record is still on disk and the undo is
       one POST. A delete with no way back, from an unlabelled 24px glyph, is
       not a thing this page should offer. */
    offerUndo(rec);
  } catch (e) {
    rec.deleting = false;
    rec.delFailed = String(e.message || e);
    CMT.err = 'delete failed: ' + rec.delFailed;
  }
  render();
}

/* Editing a note is an amendment, not a new annotation: the same id with a new
   `note`, appended. The store merges later lines onto earlier ones and never
   overwrites `at`, so the record keeps when the objection was made and the file
   keeps every wording the note has had. Nothing is rewritten in place. */
async function editNote(id, note) {
  const rec = CMT.list.find(c => c.id === id); if (!rec) return;
  note = (note || '').trim();
  /* An emptied note is not a no-op the reader meant, and discarding it in
     silence is indistinguishable from a save. The store has no way to record
     "no note" — that is what deleting is for — so it is refused out loud.

     The refusal rides on the RECORD, not on CMT.err, and the editor stays open.
     CMT.err renders only into #cmt-status, which lives inside the drawer, and
     the whole point of the margin is that the reader now works with the drawer
     closed — so a message sent there is a message nobody reads. And an editor
     that closes on a refusal looks exactly like an editor that saved. */
  if (!note) {
    rec.editFailed = 'an annotation cannot have an empty note — delete it instead';
    return render();
  }
  rec.editing = false;
  /* `!rec.editFailed` is what makes a retry possible at all. `rec.note` is set
     optimistically below, so after a failed POST the record already holds the
     text the reader typed — reopening the editor prefills it, and Save then hit
     `note === rec.note` and returned with no POST, no message and the badge
     unchanged. The reader was retrying a failed save and the page did nothing,
     forever, unless they thought to alter a character. del() was given exactly
     this fix and editNote was not. */
  if (note === rec.note && !rec.editFailed) return render();   // nothing to record
  rec.note = note;
  /* Cleared at the START of the attempt, so an in-flight retry does not wear the
     badge of the failure it is retrying. Same rule as del()'s delFailed. */
  rec.editFailed = false;                    // before the POST, not after it
  if (rec.unsaved && String(rec.id).startsWith('local-')) return render();
  render();
  try {
    const r = await fetch('/api/annotations', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id, note, edited: true})});
    if (!r.ok) {
      let msg = 'HTTP ' + r.status;
      try { msg = (await r.json()).error || msg; } catch (e) {}
      throw new Error(msg);
    }
    rec.editFailed = false;
    CMT.err = null;
  } catch (e) {
    /* The new wording stays on screen rather than being rolled back — throwing
       away what was just typed is a worse failure than an unsaved one, and the
       badge says which it is. The MESSAGE is carried on the record, not only in
       CMT.err: CMT.err renders inside the drawer, and with the margin up the
       drawer is closed. */
    rec.editFailed = String(e.message || e);
    CMT.err = 'edit failed: ' + rec.editFailed;
  }
  render();
}

"""
