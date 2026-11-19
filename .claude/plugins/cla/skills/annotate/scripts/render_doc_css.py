"""The stylesheet and favicon of the annotation page `render_doc.py` builds.

Page text only: two string constants, read by `render_doc.py` and
`render_change.py`. Not a command.
"""


FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
    # The two accents, spelled out rather than read from the stylesheet: this
    # SVG is base64'd into a data URI and never sees a CSS variable. `.b` is
    # --mark and moves with it — it was left at the old #C8622F when --mark was
    # darkened for contrast, which put a differently-coloured bar on the tab.
    '<style>.a{fill:#2F5C57}.b{fill:#9E4718}'
    '@media (prefers-color-scheme:dark){.a{fill:#84B8B0}.b{fill:#E0915E}}</style>'
    '<path class="a" d="M3.4 1h5.3l3.9 3.9V15H3.4z"/>'
    '<path class="a" opacity=".55" d="M8.7 1l3.9 3.9H8.7z"/>'
    '<path class="b" d="M1.5 8.7h11v3h-11z"/></svg>'
)

CSS = """
:root{
 --paper:#F2F2EE;--ground:#E5E6E1;--sunk:#DCDDD7;
 --ink:#1A1D1F;--ink-2:#3E4447;--muted:#585E62;--rule:#C9CBC5;--hair:#DBDCD6;
 --accent:#2F5C57;--accent-2:#4C837C;--accent-wash:#DCE7E3;
 --mark:#9E4718;--mark-wash:#F1DFD4;
}
/* --muted carries nearly every label on this page and --mark carries the whole
   annotation layer, so both are read as text and both answer to WCAG AA (4.5:1)
   on all three light surfaces, not just on --paper. They did not: --muted was
   4.22 / 3.78 / 3.47 and --mark 3.57 / 3.19 / 2.93. They now measure 5.86 /
   5.24 / 4.81 and 5.55 / 4.97 / 4.56, so the worst pair on the page is 4.56 —
   --mark on --sunk, which is the drawer's own ground and the pair nobody looks
   at. Changing either value re-derives every one of those six numbers, and the
   command that produces them is the test:

     python3 -m pytest plugin-tests/tests/skills/annotate/test_render_doc.py -k wcag

   It reads the palette out of the rendered page and fails below 4.5:1, so it
   goes red on a value this comment has not been updated for. The old hex codes
   are deliberately not repeated here: dead colours in prose are a grep magnet
   that nothing fails on. */
/* Light is the default outright, and there is deliberately no
   `prefers-color-scheme` rule: this page is a reading surface for a working
   document, and it opens the same way on every machine rather than tracking a
   system setting the reader did not choose for it. The emitted HTML carries
   data-theme="light" on the root, so dark applies only once the toggle has
   asked for it — which also means no flash of the other palette on load. */
:root[data-theme="dark"]{
 --paper:#16191B;--ground:#101314;--sunk:#1C2022;
 --ink:#DCDEDA;--ink-2:#B0B5B3;--muted:#8E9491;--rule:#2B3033;--hair:#23282A;
 --accent:#84B8B0;--accent-2:#5E938C;--accent-wash:#172523;
 --mark:#E0915E;--mark-wash:#291A11;
}
*{box-sizing:border-box}
/* No declaration on this page goes below .69rem. `rem` resolves against the
   ROOT, which is 16px — `body{font-size:17px}` below does not move it — so
   .69rem is 11.04px and anything under it was 9–10px type carrying locators,
   counts and failure states. 21 declarations were below that floor. */
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--ground);color:var(--ink);font-size:17px;line-height:1.65;
 font-family:ui-serif,Charter,"Iowan Old Style",Georgia,Cambria,"Times New Roman",serif}
.mono,code,pre,kbd{font-family:ui-monospace,SFMono-Regular,"Cascadia Mono","Segoe UI Mono",
 Menlo,Consolas,"Liberation Mono",monospace}
:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:2px}

.bar{position:sticky;top:0;z-index:60;background:var(--paper);border-bottom:1px solid var(--rule);
 display:flex;align-items:center;gap:.85rem;padding:.55rem 1.1rem;
 font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.72rem}
.bar-doc{color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:46vw}
.bar-stat{color:var(--muted);letter-spacing:.06em;text-transform:uppercase;
 font-variant-numeric:tabular-nums;white-space:nowrap}
.bar-sp{flex:1}
.bar-tools{display:flex;align-items:center;gap:.15rem;flex:none}
.bar-ico{width:1.7rem;height:1.7rem;flex:none;display:inline-flex;align-items:center;
 justify-content:center;border:0;border-radius:3px;background:none;cursor:pointer;
 color:var(--muted);font-size:.95rem;line-height:1;padding:0}
.bar-ico:hover{color:var(--ink);background:var(--sunk)}
.bar-ico[disabled]{cursor:progress;color:var(--ink);animation:spin .9s linear infinite}
.bar-ico.failed{color:var(--mark)}
@keyframes spin{from{transform:rotate(0)}to{transform:rotate(360deg)}}
.ico-svg{width:.95rem;height:.95rem;display:block;flex:none}
.opener{font:inherit;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
 font-size:.72rem;cursor:pointer;display:flex;align-items:center;gap:.5rem;background:transparent;
 border:1px solid var(--mark);border-radius:3px;padding:.36rem .55rem .36rem .7rem;color:var(--mark);
 letter-spacing:.07em;text-transform:uppercase;box-shadow:inset 3px 0 0 var(--mark)}
.opener:hover{background:var(--mark-wash)}
.opener[aria-expanded="true"]{background:var(--mark);border-color:var(--mark);color:var(--paper);
 box-shadow:inset 3px 0 0 var(--paper)}
/* The one always-visible surface, so it carries any state the drawer would
   otherwise hold off-screen — an unreadable corpus, a dead server, an unsaved
   note. Not a colour alone: the dot is what survives a reader who cannot tell
   these two oranges apart. */
.opener.failing{border-color:var(--mark);background:var(--mark);color:var(--paper);
 box-shadow:inset 3px 0 0 var(--paper)}
.opener.failing::after{content:"!";font-weight:700;margin-left:.15rem}
.opener.failing .cmt-n{background:var(--paper);color:var(--mark)}
.cmt-n{font-variant-numeric:tabular-nums;background:var(--mark-wash);color:var(--mark);
 border-radius:999px;padding:.05rem .42rem;font-size:0.69rem;min-width:1.35rem;text-align:center}
.opener[aria-expanded="true"] .cmt-n{background:var(--paper);color:var(--mark)}

.shell{display:grid;grid-template-columns:clamp(13rem,18vw,17rem) minmax(0,1fr);
 align-items:start}
.rail{position:sticky;top:2.9rem;height:calc(100vh - 2.9rem);overflow-y:auto;
 padding:1.3rem .8rem 3rem 1.1rem;border-right:1px solid var(--rule);background:var(--paper)}
.rail-h{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;letter-spacing:.16em;
 text-transform:uppercase;color:var(--muted);margin:0 0 .8rem .1rem}
.rail-item{display:grid;grid-template-columns:1fr auto;gap:.5rem;align-items:center;
 text-decoration:none;color:var(--ink-2);padding:.42rem .45rem;border-radius:2px;
 border-left:2px solid transparent}
.rail-item:hover{background:var(--sunk);color:var(--ink)}
.rail-item.on{border-left-color:var(--accent);background:var(--accent-wash);color:var(--ink)}
.rail-item[data-depth="1"]{padding-left:1.2rem}
.rail-item[data-depth="2"]{padding-left:2rem}
.rail-item[data-depth="3"]{padding-left:2.8rem}
.rail-item[data-depth="4"]{padding-left:3.6rem}
.rail-main{display:flex;flex-direction:column;gap:.3rem;min-width:0}
.rail-title{font-size:.9rem;line-height:1.25}
.rail-item[data-depth="0"] .rail-title{font-weight:600}
.rail-item[data-depth="2"] .rail-title,.rail-item[data-depth="3"] .rail-title,
.rail-item[data-depth="4"] .rail-title{font-size:.8rem}
.rail-bar{display:block;height:3px;background:var(--hair);border-radius:2px;overflow:hidden}
.rail-bar i{display:block;height:100%;background:var(--accent-2);opacity:.5}
.rail-item.on .rail-bar i{opacity:1}
.rail-meta{display:flex;align-items:center;gap:.3rem;flex:none}
.rail-n{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;
 font-variant-numeric:tabular-nums;color:var(--muted);text-align:right}
.rail-item.on .rail-n{color:var(--accent)}
/* The annotation count is the reason to look at the rail once a pass is under
   way: it says which sections were argued with, which is not the same question
   as which are long. */
.rail-c{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;
 font-variant-numeric:tabular-nums;background:var(--mark);color:var(--paper);
 border-radius:999px;padding:.02rem .34rem;min-width:1.1rem;text-align:center}
.rail-c[hidden]{display:none}
.rail-foot{margin-top:1.1rem;padding-top:.9rem;border-top:1px solid var(--hair);
 font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;line-height:1.7;
 color:var(--muted)}
.sec{scroll-margin-top:4rem}

.page{background:var(--paper);min-height:100vh;padding:0 1.5rem 10rem}
/* No height here on purpose. `fit()` in the JS owns the frame's height and
   carries the reasoning; this is the one place that defers to it rather than
   restating it. */
#cla-frame{display:block;width:100%;border:0;background:var(--paper)}
.frame-warn{margin:2rem 0;padding:.8rem 1rem;border:1px solid var(--mark);
 border-radius:3px;background:var(--mark-wash);color:var(--mark);
 font-size:.92rem;line-height:1.5}
.col{max-width:44rem;margin:0 auto;padding-top:2.4rem}
h1,h2,h3,h4,h5,h6{font-weight:600;line-height:1.25;text-wrap:balance;scroll-margin-top:4rem}
h1{font-size:2rem;margin:0 0 1.4rem;letter-spacing:-.012em}
h2{font-size:1.4rem;margin:2.6rem 0 .9rem;padding-bottom:.35rem;border-bottom:1px solid var(--hair)}
h3{font-size:1.13rem;margin:2rem 0 .7rem}
h4,h5,h6{font-size:1rem;margin:1.6rem 0 .6rem;color:var(--ink-2)}
p{margin:0 0 1.1rem}
a{color:var(--accent);text-underline-offset:2px}
strong{font-weight:650}
del{color:var(--muted)}
hr{border:0;border-top:1px solid var(--rule);margin:2.4rem 0}
ul,ol{margin:0 0 1.1rem;padding-left:1.5rem}
li{margin:.3rem 0}
li>ul,li>ol{margin:.3rem 0}
blockquote{margin:1.4rem 0;padding:.1rem 0 .1rem 1.1rem;border-left:2px solid var(--accent-2);
 color:var(--ink-2)}
blockquote p:last-child{margin-bottom:0}
code{font-size:.86em;background:var(--sunk);border-radius:2px;padding:.1em .32em}
pre{background:var(--sunk);border:1px solid var(--hair);border-radius:3px;
 padding:.75rem .9rem;overflow-x:auto;margin:0 0 1.2rem;font-size:.82rem;line-height:1.6}
pre code{background:none;padding:0;font-size:inherit}
img{max-width:100%;height:auto;border-radius:2px}
.imglink{font-style:italic}
.fm{margin:0 0 2rem;border:1px dashed var(--rule);border-radius:3px;padding:.5rem .7rem;
 background:var(--ground)}
.fm-t{display:block;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;
 letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin-bottom:.4rem}
.fm pre{margin:0;background:none;border:0;padding:0}
.pt{white-space:pre-wrap}
.tw{overflow-x:auto;margin:0 0 1.2rem}
table{border-collapse:collapse;font-size:.88rem;min-width:100%}
th,td{border:1px solid var(--hair);padding:.4rem .6rem;text-align:left;vertical-align:top}
th{background:var(--sunk);font-weight:600}

.sel-btn{position:absolute;z-index:90;cursor:pointer;background:var(--mark);color:var(--paper);
 font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;letter-spacing:.1em;
 text-transform:uppercase;border-radius:3px;padding:.34rem .6rem;
 box-shadow:0 2px 10px rgba(0,0,0,.22);user-select:none}
.sel-btn span{margin-right:.25rem}
.cmt-pop{position:absolute;z-index:95;width:min(25rem,90vw);background:var(--paper);
 border:1px solid var(--mark);border-radius:3px;box-shadow:0 8px 30px rgba(0,0,0,.24);padding:.75rem}
.cmt-anchor{margin:0 0 .5rem;font-size:.84rem;line-height:1.45;color:var(--ink-2);
 border-left:2px solid var(--mark);padding-left:.6rem;max-height:5.2rem;overflow:auto}
.cmt-pop textarea,.cmt-ta{width:100%;font:inherit;font-size:.9rem;line-height:1.5;padding:.5rem;
 background:var(--sunk);color:var(--ink);border:1px solid var(--rule);border-radius:2px;
 resize:vertical}
.cmt-actions,.cmt-erow{display:flex;align-items:center;gap:.35rem;margin-top:.5rem}
.cmt-where{flex:1;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;
 color:var(--muted);letter-spacing:.06em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cmt-hint{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;color:var(--muted)}
.cmt-ico{width:1.5rem;height:1.5rem;display:inline-flex;align-items:center;justify-content:center;
 border:1px solid var(--rule);border-radius:2px;background:transparent;color:var(--ink-2);
 cursor:pointer;font-size:.82rem;line-height:1;padding:0}
.cmt-ico:hover{border-color:var(--mark);color:var(--mark);background:var(--mark-wash)}
.cmt-ico.is-on{border-color:var(--mark);color:var(--paper);background:var(--mark)}
.cmt-ok{border-color:var(--mark);color:var(--paper);background:var(--mark)}
.cmt-ok:hover{filter:brightness(1.08);color:var(--paper)}

.cmt-hl{background:var(--mark-wash);box-shadow:0 0 0 2px var(--mark-wash);border-radius:1px;
 border-bottom:1px solid var(--mark);color:inherit}
.cmt-sup{display:inline-flex;align-items:center;gap:0;vertical-align:baseline;
 margin:0 .12rem 0 .18rem;white-space:nowrap}
.cmt-num,.cmt-x{font-family:ui-monospace,Menlo,Consolas,monospace;cursor:pointer;
 border:1px solid var(--mark);background:var(--mark-wash);color:var(--mark);
 font-variant-numeric:tabular-nums;line-height:1;padding:0;display:inline-flex;
 align-items:center;justify-content:center;height:1.2rem}
.cmt-num{font-size:0.69rem;min-width:1.25rem;border-radius:2px}
.cmt-x{font-size:.8rem;width:0;min-width:0;opacity:0;overflow:hidden;border-left:0;
 border-radius:0 2px 2px 0;transition:opacity .12s ease,width .12s ease}
.cmt-sup:hover .cmt-num,.cmt-sup:focus-within .cmt-num{border-radius:2px 0 0 2px}
.cmt-sup:hover .cmt-x,.cmt-sup:focus-within .cmt-x{opacity:1;width:1.2rem}
.cmt-num:hover,.cmt-num:focus-visible,.cmt-x:hover,.cmt-x:focus-visible{
 background:var(--mark);color:var(--paper)}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
@media (hover:none){.cmt-x{opacity:1;width:1.2rem}}

.scrim{position:fixed;inset:0;background:rgba(0,0,0,.32);opacity:0;pointer-events:none;
 transition:opacity .2s ease;z-index:80}
.drawer{position:fixed;top:0;right:0;height:100vh;width:min(27rem,92vw);z-index:85;
 background:var(--paper);border-left:2px solid var(--mark);transform:translateX(101%);
 transition:transform .22s ease;display:flex;flex-direction:column}
body.cmt .drawer{transform:none}
body.cmt .scrim{opacity:1;pointer-events:auto}
.dr-top{display:flex;align-items:baseline;gap:.6rem;padding:.8rem 1rem;
 border-bottom:1px solid var(--mark);flex:none}
.dr-title{font-weight:600}
.dr-sub{flex:1;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;
 letter-spacing:.07em;text-transform:uppercase;color:var(--muted);overflow:hidden;
 text-overflow:ellipsis;white-space:nowrap}
.dr-x{display:inline-flex;align-items:center;justify-content:center;width:1.6rem;height:1.6rem;
 padding:0;border:0;background:none;color:var(--muted);cursor:pointer}
.dr-x:hover{color:var(--ink)}
.dr-body{overflow-y:auto;padding:0 1rem 3rem}
.cmt-card{padding:.9rem 0;border-bottom:1px solid var(--hair)}
.cmt-head{display:flex;gap:.55rem;align-items:baseline;margin-bottom:.35rem}
.cmt-idx{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;color:var(--mark);flex:none}
.cmt-loc{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;color:var(--muted);
 letter-spacing:.04em;cursor:pointer;background:none;border:0;padding:0;text-align:left}
.cmt-loc:hover{color:var(--mark);text-decoration:underline}
.cmt-acts{margin-left:auto;display:flex;gap:.15rem;flex:none;align-items:center}
/* A destructive action says what it does and is big enough to mean it. This was
   a 24px unlabelled ✕ beside an identical ✎, which is two glyphs and one
   irreversible outcome. Same control as the margin's, same words. */
.cmt-act{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;letter-spacing:.08em;
 text-transform:uppercase;color:var(--muted);background:none;border:0;cursor:pointer;
 padding:.28rem .4rem;border-radius:2px;min-height:26px}
.cmt-act:hover{color:var(--mark);background:var(--mark-wash)}
.cmt-quote{margin:0 0 .4rem;font-size:.84rem;line-height:1.45;color:var(--ink-2);
 border-left:2px solid var(--mark);padding-left:.6rem}
.cmt-note{margin:0;font-size:.9rem;line-height:1.5;cursor:text;white-space:pre-wrap}
.cmt-empty{color:var(--muted);font-size:.86rem;line-height:1.6;padding:1.4rem 0}
.cmt-fatal{color:var(--mark)}
.cmt-sep{margin:1.1rem 0 .5rem;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;
 letter-spacing:.12em;text-transform:uppercase;color:var(--muted);border-top:1px solid var(--rule);
 padding-top:.6rem}

/* ---------- the comment margin ---------- */
/* The reading column sat centred with ~214px of dead paper either side at
   1440px, and the drawer — the one surface that describes the prose — was laid
   ON TOP of it. An annotation and the sentence it names could not be read at
   once, which is the whole reason this page exists. The right-hand dead paper is
   the margin now, and the column moves off centre to pay for it: 40rem here
   against the 44rem it had, so the measure is 64px narrower when the margin is
   up. Below 1000px the margin folds away and the inline markers carry every
   annotation, so nothing is ever unreachable. */
.wrap{display:grid;grid-template-columns:minmax(0,40rem) minmax(11rem,19rem);
 gap:clamp(1rem,2.5vw,3rem);justify-content:center;align-items:start;padding-top:2.4rem}
.wrap>.col{max-width:none;min-width:0;margin:0;padding-top:0}
.gutter{position:relative}
@media (max-width:999px){
 .wrap{display:block;max-width:44rem;margin:0 auto}
 .gutter{display:none}
}
/* The drawer is a fixed overlay 27rem wide, so on anything narrower than the
   rail plus the column plus the margin plus the drawer, an open drawer lands ON
   the margin — notes rendered, hoverable, and covered. The margin folds away
   instead while the drawer is open. Nothing is lost by that: the two surfaces
   hold the same records, and the drawer is the one the reader just opened.
   Above 1600px they fit side by side, and there the drawer stops being modal —
   the scrim would sit over the margin and swallow every click on it. */
@media (max-width:1599px){
 body.cmt .wrap{display:block;max-width:44rem;margin:0 auto}
 body.cmt .gutter{display:none}
}
@media (min-width:1600px){
 body.cmt .page{padding-right:27rem}
 body.cmt .scrim{opacity:0;pointer-events:none}
}
/* A note stands beside the block it names. Two notes on one block stack: the
   second is pushed below the first and switches to a dashed rule, so a displaced
   note never pretends to be level with its own line. */
.mnote{position:absolute;left:0;width:100%;cursor:pointer;
 padding:.5rem .6rem .55rem .7rem;border-left:2px solid var(--mark);
 background:transparent;border-radius:0 2px 2px 0;
 transition:background .15s ease,top .18s cubic-bezier(.4,0,.2,1)}
.mnote:hover,.mnote.lit{background:var(--mark-wash)}
.mnote.stacked{border-left-style:dashed}
/* Not anchored to a block, so it does not pretend to be: no tie, no number, and
   it sits under the last note rather than beside anything. */
.mnote.mn-lost{border-left-style:dotted;cursor:default}
.mnote.mn-lost:hover{background:transparent}
/* A button centres its own text, and this one wraps to two lines — so the
   sentence sat centred while every other note in the margin is ragged-right. */
.mn-lost .mn-act{padding-left:0;text-transform:none;letter-spacing:.02em;
 font-size:.78rem;color:var(--mark);text-align:left;line-height:1.45}
.mn-lost .mn-act:hover{background:transparent;text-decoration:underline}
.mn-head{display:flex;align-items:baseline;gap:.45rem;margin-bottom:.2rem}
.mn-i{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;
 color:var(--mark);flex:none;font-variant-numeric:tabular-nums}
.mn-note{margin:0;font-size:.88rem;line-height:1.5;color:var(--ink-2);white-space:pre-wrap}
.mnote.lit .mn-note{color:var(--ink)}
.mn-acts{margin-left:auto;display:flex;gap:.1rem;opacity:0;transition:opacity .12s ease}
.mnote:hover .mn-acts,.mnote:focus-within .mn-acts{opacity:1}
@media (hover:none){.mn-acts{opacity:1}}
/* A destructive action says what it does and is big enough to mean it. The
   drawer's delete is a 24px unlabelled glyph beside an identical edit glyph. */
.mn-act{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;letter-spacing:.08em;
 text-transform:uppercase;color:var(--muted);background:none;border:0;cursor:pointer;
 padding:.28rem .4rem;border-radius:2px;min-height:26px}
.mn-act:hover{color:var(--mark);background:var(--paper)}
.mn-tie{position:absolute;left:-2.5rem;top:.85rem;width:2.5rem;height:1px;background:var(--hair)}
.mnote.lit .mn-tie{background:var(--mark)}
.mn-ta{width:100%;font:inherit;font-size:.88rem;line-height:1.5;padding:.4rem .45rem;
 border:1px solid var(--mark);border-radius:3px;background:var(--sunk);color:var(--ink);
 resize:vertical}
.mn-erow{display:flex;gap:.15rem;margin-top:.35rem;align-items:center}
/* Hovering either end lights both. */
.cmt-hl.lit{background:var(--mark);color:var(--paper);box-shadow:0 0 0 2px var(--mark)}
.cmt-card.lit{background:var(--mark-wash)}

/* ---------- state, as a badge rather than a caption ---------- */
/* `unsaved`, `DELETE FAILED` and `EDIT NOT SAVED` were appended to the locator
   line in 10px --muted — the same size and weight as the routine locator they
   were bolted onto, for four states of which three mean the reader's work did
   not reach the file. */
.badge{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.69rem;letter-spacing:.09em;
 text-transform:uppercase;padding:.1rem .35rem;border-radius:2px;flex:none;white-space:nowrap}
.b-fail{background:var(--mark);color:var(--paper);font-weight:600}
.b-warn{border:1px solid var(--mark);color:var(--mark);font-weight:600}
.b-info{border:1px solid var(--rule);color:var(--muted)}

/* ---------- undo ---------- */
/* The corpus is append-only, so a deleted record is still on disk. That makes an
   undo cheap, and a delete with no way back inexcusable. */
.undo{position:fixed;left:50%;bottom:1.4rem;transform:translateX(-50%) translateY(1.5rem);
 z-index:120;display:flex;align-items:center;gap:.9rem;opacity:0;pointer-events:none;
 background:var(--ink);color:var(--paper);border-radius:4px;padding:.55rem .75rem .55rem 1rem;
 box-shadow:0 6px 26px rgba(0,0,0,.3);font-family:ui-monospace,Menlo,Consolas,monospace;
 font-size:.75rem;line-height:1.5;max-width:min(34rem,92vw);
 transition:opacity .16s ease,transform .16s ease}
.undo.on{opacity:1;pointer-events:auto;transform:translateX(-50%) translateY(0)}
.undo-b{font:inherit;background:none;border:1px solid var(--paper);border-radius:3px;
 color:var(--paper);cursor:pointer;padding:.2rem .6rem;letter-spacing:.08em;
 text-transform:uppercase;flex:none;min-height:26px}
.undo-b:hover{background:var(--paper);color:var(--ink)}
@media (max-width:900px){
 .col{max-width:none}
 .shell{grid-template-columns:1fr}
 /* The rail stops being a sticky column and becomes a band across the top: a
    13rem column on a narrow screen leaves the document too little to read in,
    which is the one thing this page exists for. */
 .rail{position:static;height:auto;max-height:40vh;border-right:0;
  border-bottom:1px solid var(--rule);display:grid;
  grid-template-columns:repeat(auto-fill,minmax(11rem,1fr));gap:.15rem;padding:.9rem}
 .rail-h,.rail-foot{grid-column:1/-1}
 .rail-item[data-depth]{padding-left:.45rem}
 .bar{flex-wrap:wrap;gap:.5rem}
 .bar-stat{order:9}
}
"""
