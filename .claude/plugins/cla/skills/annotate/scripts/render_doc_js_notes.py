"""The second half of the annotation page's script: the annotation layer.

Painting anchors back into the prose, the annotation margin, undo and start-up.
`render_doc.py` joins `render_doc_js_page.JS_PAGE` with this into the one script
the page carries. Page text only. Not a command.
"""


JS_NOTES = r"""/* ---- paint anchors back into the prose ---- */
/* extractContents splits an inline element when a range ends inside one, and
   unwrapping the highlight does not put the halves back together. Covers every
   inline the renderer emits — em, strong, code, del and a — and compares href so
   that two different links are never welded into one. */
function mergeSplitInline(root) {
  if (!root) return;
  root.querySelectorAll('em, strong, code, del, a').forEach(el => {
    let next = el.nextSibling;
    while (next && next.nodeType === 1 && next.tagName === el.tagName
           && next.className === el.className
           && next.getAttribute('href') === el.getAttribute('href')) {
      while (next.firstChild) el.appendChild(next.firstChild);
      const dead = next;
      next = next.nextSibling;
      dead.remove();
    }
    el.normalize();
  });
}

function clearMarks() {
  CDOC.querySelectorAll('.cmt-sup').forEach(s => s.remove());
  CDOC.querySelectorAll('mark.cmt-hl').forEach(m => {
    const p = m.parentNode; while (m.firstChild) p.insertBefore(m.firstChild, m);
    p.removeChild(m); p.normalize();
  });
  /* The content root as an ELEMENT, not a shared id. `id="doc"` is emitted
     only by the Markdown body variant, and the HTML path may not have an
     element added to it — so this threw on the first repaint and took the
     annotation layer with it. */
  mergeSplitInline(CDOC.body || CDOC.getElementById('doc'));
}

/* A resolved annotation is deliberately not painted: its text has gone from the
   document *because* something replaced it, so chasing its anchor would report
   ANCHOR LOST on every one already dealt with. */
function openOnes() { return CMT.list.filter(c => !c.resolved); }
function doneOnes() { return CMT.list.filter(c => c.resolved); }

/* The inner 24 characters either side. */
function needleOf(c) {
  return {lead: (c.before || '').slice(-24), tail: (c.after || '').slice(0, 24)};
}

/* Block ids are ordinals, so inserting one paragraph renumbers every block after
   it and every open annotation below the insertion stops finding its own block.
   The stored id is tried first; when it is gone — or now holds something else —
   the annotation is relocated by its text and the context either side, and only
   when exactly one block matches. An ambiguous match is left lost, which is the
   honest answer. */
function hostFor(c) {
  const byId = c.blk ? CDOC.querySelector('[data-blk="' + CSS.escape(c.blk) + '"]') : null;
  if (byId && blockText(byId).indexOf(c.text) >= 0) return byId;
  const n = needleOf(c), full = n.lead + c.text + n.tail;
  const hits = [...CDOC.querySelectorAll('[data-blk]')]
    .filter(el => blockText(el).indexOf(full) >= 0);
  if (hits.length === 1) { c.blk = hits[0].dataset.blk; c.line = Number(hits[0].dataset.line) || c.line; return hits[0]; }
  if (hits.length > 1) return null;
  return byId || null;
}

/* Where the anchor sits inside the block it was found in. The stored offset was
   counted against an older render, so it is trusted only when the text is
   actually there; otherwise the context brackets it, and a passage appearing
   twice in one block is left to the stored offset rather than guessed at. */
function offsetOf(c, host) {
  const t = blockText(host), n = needleOf(c);
  if (t.substr(c.off, c.text.length) === c.text) return c.off;
  const withCtx = t.indexOf(n.lead + c.text + n.tail);
  if (withCtx >= 0) return withCtx + n.lead.length;
  const bare = t.indexOf(c.text);
  return bare >= 0 && t.indexOf(c.text, bare + 1) < 0 ? bare : c.off;
}

/* Where the anchor starts and ends, as a range that may cross text nodes: an
   anchor spanning <em>, <code> or a link lives in two nodes or more, and
   requiring one node reported ANCHOR LOST for text sitting untouched. */
function rangeFor(host, off, text) {
  const nodes = textNodes(host);
  const total = nodes.reduce((n, x) => n + x.nodeValue.length, 0);
  /* A stored offset comes out of a committed, hand-editable file. A negative one
     throws IndexSizeError out of setStart, out of paint and out of render,
     leaving the drawer empty over a fully loaded corpus. */
  if (!(off >= 0) || off + text.length > total) return null;
  let seen = 0, start = null, end = null, got = '';
  for (const n of nodes) {
    const len = n.nodeValue.length;
    if (start === null && seen + len > off) start = [n, off - seen];
    if (start !== null) {
      const a = (n === start[0]) ? start[1] : 0;
      const b = Math.min(len, off + text.length - seen);
      if (b > a) got += n.nodeValue.slice(a, b);
      if (seen + len >= off + text.length) { end = [n, off + text.length - seen]; break; }
    }
    seen += len;
  }
  if (!start || !end) return null;
  /* Compared against what textNodes actually walked, never against
     range.toString(): toString concatenates every text node between the
     boundaries, including the markers textNodes filtered out. */
  if (got !== text) return null;
  const r = document.createRange();
  r.setStart(start[0], start[1]);
  r.setEnd(end[0], end[1]);
  return r;
}

/* Whether the last paint() ran with a margin or without one. paint() chooses
   between a margin note and an inline marker, so when that answer changes the
   page has to be REPAINTED, not merely re-laid-out. Null until the first paint,
   so the first sync after load always repaints. */
let paintedMarginOff = null;

function paint() {
  clearMarks();
  paintedMarginOff = marginOff();
  openOnes().forEach((c, i) => {
    c.idx = i + 1;
    c.mark = null;
    c.paintFailed = false;
    const host = hostFor(c);
    if (!host) { c.lost = true; return; }
    c.off = offsetOf(c, host);
    const r = rangeFor(host, c.off, c.text);
    if (!r) { c.lost = true; return; }
    const m = document.createElement('mark');
    m.className = 'cmt-hl';
    try {
      /* extract-and-insert rather than surroundContents, which throws the moment
         a range partially selects an element. The fragment is held so a failed
         insert can put the prose back: extractContents has already removed it
         from the document by then. */
      m.appendChild(r.extractContents());
      r.insertNode(m);
    } catch (e) {
      /* Put ALL of it back, not just the first node: a fragment spanning <em> or
         <code> has several children, and restoring one silently drops the rest —
         the block's text then differs from the document, and its neighbours
         start reporting themselves lost against a file nobody touched. And say
         so rather than swallowing: an empty catch here loses a clause of the
         prose the reader is annotating. */
      if (!m.parentNode) {
        try { while (m.firstChild) r.insertNode(m.lastChild); }
        catch (e2) {
          CMT.err = 'a passage could not be repainted — press Rebuild;'
                  + ' the corpus is untouched';
        }
      }
      /* Distinct from `lost`, and both are set. Reporting only ANCHOR LOST told
         the reader their document had moved — for an annotation whose text is
         exactly where it was. This one is a fault in the page, not in the
         corpus, and it is the only state here the reader can do nothing about
         except rebuild. */
      c.paintFailed = true;
      c.lost = true;
      return;
    }
    c.lost = false;
    c.mark = m;
    m.dataset.cmt = c.id;
    m.onmouseenter = () => lite(c.id, true);
    m.onmouseleave = () => lite(c.id, false);
    /* The inline marker is what the margin replaces. It stays for the widths
       where there is no margin — a phone, a narrow window — so no annotation is
       ever unreachable. syncMargin() is what keeps that true across a resize. */
    if (paintedMarginOff) {
      const sup = document.createElement('sup');
      sup.className = 'cmt-sup';
      const num = document.createElement('button');
      num.className = 'cmt-num'; num.textContent = String(i + 1);
      num.title = c.note; num.setAttribute('aria-label', 'annotation ' + (i + 1));
      num.onclick = e => { e.stopPropagation(); openList(c.id); };
      const x = document.createElement('button');
      x.className = 'cmt-x'; x.textContent = '×';
      x.title = 'delete this annotation';
      x.setAttribute('aria-label', 'delete annotation ' + (i + 1));
      x.onclick = e => { e.stopPropagation(); del(c.id); };
      sup.append(num, x);
      m.after(sup);
    }
  });
  layoutMargin();
}

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

/* ---- the annotation margin ---- */
const GUTTER = document.getElementById('gutter');
function marginOff() {
  return !GUTTER || getComputedStyle(GUTTER).display === 'none';
}

/* The drawer being open decides which surface owns editing. */
function drawerOpen() { return document.body.classList.contains('cmt'); }

/* The ONE entry point for "the geometry moved". Every reading control that
   changes the FLOW has to come through here — not just a resize. On the change
   page, switching tabs and hiding the counterparts both move every block by
   hundreds of pixels, and margin tops are absolute pixels computed once. Nothing
   re-laid them out, so a toggle left every note beside a different sentence with
   its tie still drawn SOLID, which is this page's promise that the note is level
   with its own line. Repaint when the margin has appeared or disappeared;
   otherwise just move the notes. */
function syncMargin() {
  if (marginOff() !== paintedMarginOff) render();
  else layoutMargin();
}

/* Light the note and its anchor together, from whichever end was touched. */
function lite(id, on) {
  document.querySelectorAll('[data-cmt="' + CSS.escape(id) + '"]')
    .forEach(el => el.classList.toggle('lit', on));
  const card = document.getElementById('card-' + id);
  if (card) card.classList.toggle('lit', on);
}

function layoutMargin() {
  if (!GUTTER) return;
  GUTTER.textContent = '';
  GUTTER.style.height = '';
  if (marginOff()) return;
  const top0 = GUTTER.getBoundingClientRect().top + window.scrollY;
  let floor = -Infinity;
  /* `isConnected` is not the test. On a change page every file is in the
     document at once and only the showing tab is displayed, so a mark in a
     hidden pane is connected, has a zero-sized rect, and produced a note pinned
     at the top of the margin beside nothing — measured at top:-135.78px while
     the tasks tab was showing and the note belonged to the proposal.
     getClientRects() is empty for a `display:none` subtree, which is the
     question actually being asked: is this mark on screen. */
  openOnes().filter(c => !c.lost && c.mark && c.mark.getClientRects().length).forEach(c => {
    const el = document.createElement('div');
    el.className = 'mnote';
    el.tabIndex = 0;
    el.dataset.cmt = c.id;
    el.innerHTML =
      '<span class="mn-tie"></span>'
      + '<div class="mn-head"><span class="mn-i">' + c.idx + '</span>' + stateBadge(c)
      + '<span class="mn-acts">'
      + '<button class="mn-act" data-medit="' + esc(c.id) + '">Edit</button>'
      + '<button class="mn-act" data-mdel="' + esc(c.id) + '">Delete</button>'
      + '</span></div>'
      /* ONE editor at a time. Above the wide breakpoint the margin is not hidden
         while the drawer is open, so both surfaces would render a textarea for
         the same c.editing, each prefilled from c.note — and saving from the
         drawer would read ITS stale textarea, match `note === rec.note`, and
         repaint the old wording with no message. The drawer owns editing
         whenever it is open. */
      + (c.editing && !drawerOpen()
          ? '<textarea class="mn-ta" rows="3" data-med="' + esc(c.id) + '">' + esc(c.note) + '</textarea>'
            + '<div class="mn-erow"><button class="mn-act" data-mesave="' + esc(c.id) + '">Save</button>'
            + '<button class="mn-act" data-mecancel="' + esc(c.id) + '">Cancel</button></div>'
          : '<p class="mn-note">' + esc(c.note) + '</p>');
    GUTTER.appendChild(el);
    /* Anchored to the marked block, then pushed clear of the note above it. A
       pushed note switches to a dashed rule: it is no longer level with its own
       line and should not say that it is. */
    let top = contentRect(c.mark).top + window.scrollY - top0 - 6;
    if (top < floor + 8) { top = floor + 8; el.classList.add('stacked'); }
    el.style.top = top + 'px';
    floor = top + el.offsetHeight;
    el.onmouseenter = () => lite(c.id, true);
    el.onmouseleave = () => lite(c.id, false);
    el.addEventListener('focus', () => lite(c.id, true));
    el.addEventListener('blur', () => lite(c.id, false));
  });
  /* An annotation whose passage the document no longer has cannot stand beside a
     block, and paint() gives it no inline marker either — so with the drawer
     closed it was on NO surface the reader had open. The margin says how many
     and opens the drawer. */
  const lostN = openOnes().filter(c => c.lost).length;
  if (lostN) {
    const note = document.createElement('div');
    note.className = 'mnote mn-lost';
    note.style.top = (floor > -Infinity ? floor + 24 : 0) + 'px';
    note.innerHTML =
      '<p class="mn-note"><button class="mn-act" id="mn-lost-b">'
      + (lostN === 1
          ? '1 annotation has lost its place in the document'
          : lostN + ' annotations have lost their place in the document')
      + ' →</button></p>';
    GUTTER.appendChild(note);
    note.querySelector('#mn-lost-b').onclick = () => setCmt(true);
    floor = (floor > -Infinity ? floor + 24 : 0) + note.offsetHeight;
  }
  GUTTER.style.height = (floor > -Infinity ? floor + 40 : 0) + 'px';

  GUTTER.querySelectorAll('[data-mdel]').forEach(bn =>
    bn.onclick = e => { e.stopPropagation(); del(bn.dataset.mdel); });
  GUTTER.querySelectorAll('[data-medit]').forEach(bn =>
    bn.onclick = e => {
      e.stopPropagation();
      const c = CMT.list.find(x => x.id === bn.dataset.medit); if (!c) return;
      CMT.list.forEach(x => { x.editing = (x === c); });
      render();
      /* With the drawer open the margin renders no textarea, so focus has to
         follow the editor to the surface that actually has it — otherwise Edit
         looks like it did nothing. */
      const t = GUTTER.querySelector('[data-med]')
             || CMT.el.list.querySelector('[data-ed="' + CSS.escape(c.id) + '"]');
      if (t) { t.focus(); t.setSelectionRange(t.value.length, t.value.length); }
    });
  GUTTER.querySelectorAll('[data-mecancel]').forEach(bn =>
    bn.onclick = e => {
      e.stopPropagation();
      const c = CMT.list.find(x => x.id === bn.dataset.mecancel);
      if (c) { c.editing = false; render(); }
    });
  GUTTER.querySelectorAll('[data-mesave]').forEach(bn =>
    bn.onclick = e => {
      e.stopPropagation();
      const t = GUTTER.querySelector('[data-med="' + CSS.escape(bn.dataset.mesave) + '"]');
      /* A missing textarea is a DOM fault, not an empty note. Feeding '' to
         editNote makes the two indistinguishable and throws away what the reader
         typed. */
      if (!t) { CMT.err = 'the editor went missing; nothing was saved'; return render(); }
      editNote(bn.dataset.mesave, t.value);
    });
  GUTTER.querySelectorAll('[data-med]').forEach(t => t.onkeydown = e => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); editNote(t.dataset.med, t.value); }
    if (e.key === 'Escape') {
      const c = CMT.list.find(x => x.id === t.dataset.med);
      if (c) { c.editing = false; render(); }
    }
  });
}

/* State as a badge. More than one can be true at once — a failed undo and then a
   failed edit — so the worst is shown and the rest are counted rather than
   dropped. `lost` is deliberately absent: the drawer card marks it and the
   margin's foot counts it, because it is information, not a failure. */
/* Each entry is [class, label, detail]. The label is what the badge prints and
   stays short enough to sit in a margin note's head; the detail is the server's
   own sentence naming what to fix, and it goes in the title alongside every
   other state that is true at once. Three of the flags carry a message string
   rather than `true`, because with the margin up the drawer is closed and
   CMT.err — which is where those sentences used to go — is inside it. */
function stateBadge(c) {
  const all = [];
  const detail = v => (typeof v === 'string' && v) ? v : '';
  if (c.paintFailed) all.push(['b-fail', 'could not be marked', '']);
  if (c.undoFailed)  all.push(['b-fail', 'undo not confirmed', detail(c.undoFailed)]);
  if (c.delFailed)   all.push(['b-fail', 'delete failed', detail(c.delFailed)]);
  if (c.editFailed)  all.push(['b-fail', 'edit not saved', detail(c.editFailed)]);
  if (c.unsaved)     all.push(['b-warn', 'not saved', '']);
  if (c.deleting)    all.push(['b-info', 'deleting…', '']);
  if (!all.length) return '';
  const more = all.length > 1 ? ' +' + (all.length - 1) : '';
  const title = all.map(x => x[2] ? x[1] + ' — ' + x[2] : x[1]).join(', ');
  return '<span class="badge ' + all[0][0] + '" title="' + esc(title) + '">'
       + all[0][1] + more + '</span>';
}

let marginT;
addEventListener('resize', () => { clearTimeout(marginT); marginT = setTimeout(syncMargin, 120); });

/* ---- undo ---- */
const UNDO = {
  bar:  document.getElementById('undo'),
  text: document.getElementById('undo-t'),
  btn:  document.getElementById('undo-b'),
};

/* opacity:0 does not remove a button from the tab order, and a handler holding
   its closure over the deleted record would let a keyboard user fire an
   un-delete long after the window closed. */
function undoBar(on, msg, onClick, label) {
  UNDO.text.textContent = msg || '';
  UNDO.btn.textContent = label || 'Undo';
  UNDO.btn.onclick = onClick || null;
  /* An informational strip has no action, and two call sites pass none: the
     local- delete, and the in-flight "Restoring…" state. The button used to
     render anyway — visible, focusable, labelled "Undo", and doing nothing, for
     the full nine seconds. A dead control is worse than an absent one, because
     it advertises a recovery that does not exist, and it advertised it hardest
     to the reader who had just destroyed the only copy of their own words.
     `hidden`, not opacity, for the same reason the bar itself is `inert`. */
  UNDO.btn.hidden = !onClick;
  UNDO.bar.classList.toggle('on', !!on);
  UNDO.bar.toggleAttribute('inert', !on);
  UNDO.bar.setAttribute('aria-hidden', String(!on));
}
let undoT;
function hideUndo() { clearTimeout(undoT); undoBar(false); }

/* A record's own name, for a strip read in a hurry. `idx` is assigned in paint()
   and a lost-anchor annotation still gets one, but a record deleted before the
   first paint has none. */
function nameOf(rec) {
  if (rec.idx) return 'Annotation ' + rec.idx;
  return rec.line ? ('The annotation on line ' + rec.line) : 'That annotation';
}

function offerUndo(rec) {
  undoBar(true, nameOf(rec) + ' deleted.', () => undoDelete(rec));
  clearTimeout(undoT);
  undoT = setTimeout(hideUndo, 7000);
}

async function undoDelete(rec) {
  clearTimeout(undoT);
  /* The strip stays up THROUGH the POST, saying what it is doing. Dismissing it
     first is what sends the failure to a panel nobody has open. */
  undoBar(true, 'Restoring ' + nameOf(rec).toLowerCase() + '…', null);
  delete rec.deleted; delete rec.deleting; delete rec.delFailed;
  delete rec.undoFailed;
  /* Back where it was, not re-sorted: sorting would renumber the whole list and
     put it out of step with the file's own order.

     Guarded, because the catch below leaves `rec` IN the list and re-arms the
     strip with this same function and this same object. A retry after a failed
     undo therefore ran this line a second time and spliced one record in twice:
     two margin notes, the second marked `.stacked` as though it were a separate
     annotation on the same block, two drawer cards sharing one DOM id, and a
     header count one too high — with no error anywhere. The page invented an
     annotation. Every further retry added another. */
  if (CMT.list.indexOf(rec) < 0) {
    const at = typeof rec.wasAt === 'number' ? rec.wasAt : CMT.list.length;
    CMT.list.splice(Math.min(at, CMT.list.length), 0, rec);
  }
  render();
  try {
    const r = await fetch('/api/annotations', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: rec.id, deleted: false})});
    if (!r.ok) {
      let msg = 'HTTP ' + r.status;
      try { msg = (await r.json()).error || msg; } catch (e2) {}
      throw new Error(msg);
    }
    CMT.err = null;
    hideUndo();
  } catch (e) {
    /* NOT "still deleted". This catch fires for a refused write AND for a lost
       response — a killed server, a slept laptop, a reset socket — and in the
       second case the tombstone may well have been lifted. Asserting the file's
       state is something the client cannot do from here, and `del()`'s local-
       branch already reasons this way about the same ambiguity. What is true in
       both cases is that the undo was not confirmed. */
    rec.undoFailed = String(e.message || e);
    CMT.err = 'undo not confirmed: ' + rec.undoFailed;
    undoBar(true, 'Undo could not be confirmed — reload to see the file. '
                + rec.undoFailed, () => undoDelete(rec), 'Retry');
  }
  render();
}

/* Hoisted out of render(): the fatal branch renders unsaved cards too, and it
   runs before render()'s own declarations. A function declaration hoists; a
   const does not, and referencing it early is a ReferenceError. */
const card = (c, i) => '<div class="cmt-card" id="card-' + c.id + '" data-id="' + c.id + '">'
    + '<div class="cmt-head">'
    + '<span class="cmt-idx">' + (i + 1) + '</span>'
    + '<button class="cmt-loc" data-go="' + c.id + '">'
    /* On a change, which FILE an annotation is on outranks which section: the
       reader is deciding whether to switch tabs. */
    + esc(c.file ? c.file + (c.sec ? ' · ' + c.sec : '') : (c.sec || DOC))
    + ' · line ' + (c.line || '?')
    /* ANCHOR LOST stays on the locator: it describes WHERE the annotation is,
       which is the locator's job, and it is information rather than a failure.
       The three states that mean the reader's work did not reach the file are
       badges — they were 10px --muted suffixes on this same line, the same size
       and weight as the routine locator they were bolted onto. */
    + (c.lost ? ' · ANCHOR LOST' : '')
    + '</button>'
    + stateBadge(c)
    + '<span class="cmt-acts">'
    + '<button class="cmt-ico' + (c.editing ? ' is-on' : '') + '" data-edit="' + c.id + '"'
    + ' title="edit this note" aria-label="edit annotation ' + (i + 1) + '">✎</button>'
    + (c.editing ? '' : '<button class="cmt-act" data-del="' + c.id + '"'
        + ' title="delete this annotation" aria-label="delete annotation ' + (i + 1)
        + '">Delete</button>')
    + '</span></div>'
    + '<p class="cmt-quote">' + esc(c.text) + '</p>'
    + (c.editing
        ? '<textarea class="cmt-ta" rows="4" data-ed="' + c.id + '">' + esc(c.note) + '</textarea>'
          + '<div class="cmt-erow">'
          + '<button class="cmt-ico cmt-ok" data-esave="' + c.id + '" title="save this note">✓</button>'
          + '<button class="cmt-ico" data-ecancel="' + c.id + '" title="discard the change">✕</button>'
          + '<span class="cmt-hint">⌘/ctrl+enter</span></div>'
        : '<p class="cmt-note" title="click to edit">' + esc(c.note) + '</p>')
    + '</div>';

function wireCards() {
  CMT.el.list.querySelectorAll('[data-del]').forEach(b => b.onclick = () => del(b.dataset.del));
  CMT.el.list.querySelectorAll('[data-edit]').forEach(b => b.onclick = () => {
    const c = CMT.list.find(x => x.id === b.dataset.edit); if (!c) return;
    CMT.list.forEach(x => { if (x !== c) x.editing = false; });
    c.editing = !c.editing;
    render();
    const t = CMT.el.list.querySelector('[data-ed]');
    if (t) { t.focus(); t.setSelectionRange(t.value.length, t.value.length); }
  });
  CMT.el.list.querySelectorAll('[data-ecancel]').forEach(b => b.onclick = () => {
    const c = CMT.list.find(x => x.id === b.dataset.ecancel);
    if (c) { c.editing = false; render(); }
  });
  CMT.el.list.querySelectorAll('[data-esave]').forEach(b => b.onclick = () => {
    const t = CMT.el.list.querySelector('[data-ed="' + CSS.escape(b.dataset.esave) + '"]');
    editNote(b.dataset.esave, t ? t.value : '');
  });
  // Escape is deliberately NOT handled here — it bubbles to the one handler
  // above, so cancelling behaves the same whether focus is in this textarea or
  // anywhere else on the page.
  CMT.el.list.querySelectorAll('[data-ed]').forEach(t => t.onkeydown = e => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); editNote(t.dataset.ed, t.value); }
  });
  // Clicking the card opens the note for editing. Buttons keep their own jobs
  // (delete, and the location line that scrolls to the passage), and a click
  // inside the open textarea must not toggle the edit it is part of.
  CMT.el.list.querySelectorAll('.cmt-card').forEach(el => el.onclick = e => {
    if (e.target.closest('button, textarea, a')) return;
    const c = CMT.list.find(x => x.id === el.dataset.id);
    if (!c || c.editing) return;
    CMT.list.forEach(x => { x.editing = (x === c); });
    render();
    const t = CMT.el.list.querySelector('[data-ed]');
    if (t) { t.focus(); t.setSelectionRange(t.value.length, t.value.length); }
  });
  CMT.el.list.querySelectorAll('[data-go]').forEach(b => b.onclick = () => {
    const c = CMT.list.find(x => x.id === b.dataset.go);
    if (c) window.focusBlock(c.blk);
  });
}

function render() {
  paint();
  paintRailCounts();          // after paint(), which is what decides `lost`
  const live = openOnes(), done = doneOnes();
  CMT.el.n.textContent = live.length;
  /* Derived from the records, never from a last-write-wins flag: one failed save
     followed by one successful save used to read 'saved' over an annotation that
     existed only in this tab. */
  const unsaved = CMT.list.filter(c => c.unsaved).length;
  const damaged = (CMT.problems || []).length;
  const bits = [];
  if (damaged) bits.push(damaged + ' LINE(S) UNREADABLE');
  if (unsaved) bits.push(unsaved + ' NOT SAVED');
  if (CMT.err) bits.push(CMT.err);
  /* Joined, not ranked. A damaged corpus and unsaved work are independent facts
     and the second one is the reader's own words; precedence hid it behind the
     first. */
  CMT.el.st.textContent =
    CMT.fatal ? CMT.fatal
    : bits.length ? bits.join(' · ')
    : !CMT.list.length ? 'none yet'
    : (done.length ? 'saved · ' + done.length + ' resolved' : 'saved');

  /* #cmt-status lives INSIDE the drawer, which is translateX(101%) when closed —
     and this page's whole premise is that the reader now works with the drawer
     closed, beside the margin. Every sentence above was therefore written to a
     surface nobody has open, including "no server" and "CORPUS UNREADABLE": a
     dead server rendered as an empty margin and an opener reading 0, which is
     pixel-identical to a document nobody has annotated yet.
     The opener is always visible, so it carries the alarm. */
  const alarm = CMT.fatal || bits.length ? (CMT.fatal || bits.join(' · ')) : '';
  CMT.el.open.classList.toggle('failing', !!alarm);
  CMT.el.open.title = alarm || 'Open the annotations';

  if (CMT.fatal) {
    /* Unsaved cards render ABOVE the banner rather than instead of it. Returning
       here dropped them entirely — and `readonly` is only ever set alongside
       `fatal`, so this was the one state in which a note written after the
       failure could be seen, and it could not be. The comment on submit()'s
       read-only branch claimed the card list already knew how to show these; it
       did not. */
    const held = CMT.list.filter(c => c.unsaved);
    CMT.el.list.innerHTML =
      '<p class="cmt-empty cmt-fatal">' + esc(CMT.fatal) + '</p>'
      + (held.length
          ? '<p class="cmt-sep">' + held.length + ' annotation(s) written since the'
            + ' failure are held in this tab only, and are lost if it closes</p>'
            + held.map(card).join('')
          : '');
    wireCards();
    return;
  }
  if (!CMT.list.length && damaged) {
    /* Not "none yet". The file exists and every line of it failed to parse,
       which must never read like a corpus nobody has started. */
    CMT.el.list.innerHTML = '<p class="cmt-empty cmt-fatal">' + damaged
      + ' line(s) of the annotations file could not be read, and no record'
      + ' survived.<br><br>The file is on disk and is not empty. Resolve it by'
      + ' hand — keeping every side, because every line is evidence.</p>';
    return;
  }
  if (!CMT.list.length) {
    CMT.el.list.innerHTML = '<p class="cmt-empty">No annotations yet.<br><br>'
      + 'Select any text and an <strong>annotate</strong> button appears.'
      + ' Cmd/Ctrl+Enter saves.<br><br>'
      + 'Each one records the section, the source line, the selected words and'
      + ' the text either side of them, so it can be found again after the'
      + ' document moves underneath it.</p>';
    return;
  }



  /* A resolved annotation leaves the page. It has been answered, and leaving it
     in view means reading the same objection twice — once as work to do and once
     as work already done. It is not deleted: the corpus keeps every one, and the
     count stays, so a page showing none is never mistaken for a corpus holding
     none. */
  CMT.el.list.innerHTML = live.map(card).join('')
    + (done.length ? '<p class="cmt-sep">' + done.length
        + ' resolved · kept in the annotations file, off the page</p>' : '');

  wireCards();
}

/* Rebuild, not reload. The page is a view of the document, so reloading a stale
   file shows prose the document no longer contains. The server runs the renderer
   on its own document and the page then reloads — which keeps this window, where
   a restart of the server would close it. */
(function () {
  const rb = document.getElementById('t-reload');
  const REST = 'Rebuild this page from the document';
  const fail = msg => {
    rb.classList.add('failed'); rb.title = msg;
    CMT.err = msg; render();
    setTimeout(() => { rb.classList.remove('failed'); rb.title = REST; }, 3000);
  };
  rb.onclick = async () => {
    if (CMT.list.some(c => c.editing)) return fail('finish the open edit before rebuilding');
    const pending = CMT.list.filter(c => c.unsaved).length;
    if (pending) return fail(pending + ' annotation(s) are not saved — rebuilding reloads'
                             + ' the page and they exist nowhere else');
    rb.disabled = true; rb.classList.remove('failed'); rb.title = 'rebuilding…';
    try {
      const r = await fetch('/api/render', {method: 'POST'});
      if (!r.ok) {
        let m = 'HTTP ' + r.status;
        try { m = (await r.json()).error || m; } catch (e) {}
        throw new Error(m);
      }
      location.reload();
    } catch (e) {
      rb.disabled = false;
      fail('rebuild failed: ' + String(e.message || e));
    }
  };
})();

/* The corpus is the only copy of a saved note, and this tab is the only copy of
   an unsaved one. */
addEventListener('beforeunload', e => {
  if (CMT.list.some(c => c.unsaved || c.editing)) { e.preventDefault(); e.returnValue = ''; }
});

/* Three states, and they must never print the same thing: reachable and empty,
   unreachable, and unreadable. A bare catch here would paint "No annotations
   yet." over a corpus that exists and cannot be parsed. */
/* Everything content-side is wired HERE, from one place, rather than as a run
   of top-level statements. Unframed this runs immediately and the order is what
   it always was; framed it runs once the author's document exists, because
   until then there is nothing to query, observe or listen to. */
function wireContent() {
  onBoth('mouseup', onMouseUp);
  onBoth('keydown', onKeyDown);
  wireRail();
  if (!FRAME) return;

  /* Size the frame to its content so the OUTER page scrolls and there is no
     inner scrollbar — that is what keeps the margin arithmetic and the rail as
     they were. Content height is not stable at first layout: the motivating
     document pulls three font families over the network and its text reflows
     when they land, so this is re-measured rather than measured. */
  /* Sizing the frame to its content is a FEEDBACK LOOP for a document whose
     own sizing is viewport-relative: the frame's height IS that document's
     viewport, so `100vh` grows with the frame, `scrollHeight` grows with it,
     and the next fit is taller again. Before this guard a `100vh` fixture drove
     the frame to the browser's maximum element height in under a second, and the
     document was unreadable. It did not hang, which is worse: it saturated and
     looked like a rendered page. The state is not reproducible now — this guard
     is what prevents it — so what stands in for the measurement is the test that
     fails if the guard goes:
     `pytest plugin-tests/tests/skills/annotate/test_page_in_a_browser.py -k viewport_sized`.

     Two exits. A document that settles keeps the content-sized frame and the
     outer page scrolls, which is what the margin arithmetic and the rail were
     built on. A document that does NOT settle is pinned to the viewport and
     scrolls itself; `contentRect` already handles that, because a rect taken
     inside the frame is relative to the frame's viewport and so already carries
     its internal scroll. What it costs is that the margin has to be re-laid-out
     on the frame's own scroll, which is the listener below. */
  /* The thresholds describe what a normal settle looks like: an ordinary
     document fits once, and again when its webfonts land — so two or three
     calls, with the height either unchanged or growing once. More than six
     calls, or a height that keeps growing after the third, is not a document
     settling. They are tunable; nothing depends on the exact values. */
  /* The thresholds describe what a normal settle looks like: an ordinary
     document fits once, and again when its webfonts land — so two or three
     calls, with the height either unchanged or growing once. More than six
     calls, or a height that keeps growing after the third, is not a document
     settling. They are tunable; nothing depends on the exact values. */
  let lastH = 0, fits = 0, framePins = false;
  const fit = () => {
    if (framePins) return;
    const h = CDOC.documentElement.scrollHeight;
    if (!h) {
      /* Zero is a transient layout, not a size. Skipping it silently would
         leave the frame at the browser's default ~150px looking like a
         document with nothing in it. */
      if (fits > 2) note('the document reported no height; the frame may be clipped');
      return;
    }
    fits += 1;
    if (fits > 6 || (lastH && h > lastH + 4 && fits > 2)) {
      framePins = true;
      FRAME.style.height = '100vh';
      CWIN.addEventListener('scroll', syncMargin);
      syncMargin();
      return;
    }
    if (Math.abs(h - lastH) < 2) { syncMargin(); return; }
    lastH = h;
    FRAME.style.height = h + 'px';
    syncMargin();
  };
  fit();
  if (CWIN.ResizeObserver) new CWIN.ResizeObserver(fit).observe(CDOC.documentElement);
  /* `document.fonts.ready` does not reject per spec, so this catch is a safety
     net rather than a swallowed error. Said out loud so a future reader does not
     read it as one. */
  if (CDOC.fonts && CDOC.fonts.ready) CDOC.fonts.ready.then(fit).catch(() => {});
  window.addEventListener('resize', fit);
}

(async function load() {
  try {
    const r = await fetch('/api/annotations');
    let j = null;
    try { j = await r.json(); } catch (e) { j = null; }
    if (r.ok && (!j || !Array.isArray(j.annotations))) {
      CMT.fatal = 'the server answered, but not with an annotation list — nothing is'
                + ' shown, and nothing should be written, until this is understood';
      CMT.readonly = true;
      return render();
    }
    if (!r.ok) {
      j = j || {};
      CMT.fatal = j.unreadable
        ? 'CORPUS UNREADABLE — ' + (j.error || 'HTTP ' + r.status)
          + '. Nothing is shown, and nothing should be written, until this is'
          + ' resolved by hand.'
        : 'could not load annotations: ' + (j.error || 'HTTP ' + r.status);
      CMT.readonly = true;
    } else {
      CMT.list = j.annotations || [];
      CMT.problems = j.problems || [];
    }
  } catch (e) {
    CMT.fatal = 'no server — annotations cannot be loaded or saved ('
              + (e.message || e) + ')';
    CMT.readonly = true;
  }
  onContentReady(() => { wireContent(); render(); });
})();
"""
