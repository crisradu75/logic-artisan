## Context

See `proposal.md` — Why. The constraints that shape the approach, all verified against the current tree rather than recalled:

- `render_doc.build()` (`render_doc.py:2209`) splits on extension: `.md`/`.markdown`/`.mdown` → Markdown, everything else → `plain_text=True`. There is no third branch.
- The page's block model is `Ctx` (`render_doc.py:176`): an ordinal `b<N>` per block, the block's plain text kept for `check_anchors`, and a `sections` list the rail is built from. `ctx.blocks` maps id → text and is consumed by `check_anchors` (`:2154`) and the word count.
- The page JS reads a block's characters with `blockText()` (`:1043`) — a `cloneNode` with the injected markers removed, then `.textContent`. `plain()` on the Python side (`:165`) exists specifically so the two agree; its docstring says so.
- `captureSelection()` (`:1106`) anchors to `closest('[data-blk]')`, records an offset counted over the block's text nodes, and 60 characters of context each side.
- `annotate_server.py` is a `SimpleHTTPRequestHandler` rooted at the page directory, so any file written there is already served. `_render()` (`:338`) branches on `is_change` and rebuilds on the reader's click.

## Goals / Non-Goals

**Goals**

- An HTML document is read and annotated in the presentation its author gave it.
- The Markdown path is provably unchanged — not "believed unchanged".
- The instrumented copy is a reversible function of the source, checkable as a property.
- Stdlib only. `html.parser` ships with Python; nothing enters the install path.

**Non-Goals** (design-level, beyond the proposal's scope section)

- Rendering an HTML file that the author's own scripts rewrite on load. The instrumentation is static; a page that regenerates its DOM at runtime will have blocks that no longer correspond to its markup. Detecting that is a separate problem and this change does not attempt it.
- Any support for XML/XHTML strictness. `html.parser` parses HTML as browsers do — leniently — and that is the correct behaviour here, because the browser rendering the frame will parse it the same way.

## Decisions

### 1. A same-origin iframe, not shadow DOM and not direct injection

**Direct injection is ruled out by measurement, not by caution.** Three names collide between annotate's own layer and the motivating document, and each is the obvious name for what it does on both sides:

| Name | annotate uses it for | the document uses it for |
|---|---|---|
| `.wrap` | the two-column reading grid (`render_doc.py:803`) | its own page container, `max-width:62rem` |
| `.bar` | the top bar (CSS at `render_doc.py:603`, markup in `page()`) | its waterfall chart bars, `height:.7rem` |
| `:root[data-theme]` | the theme toggle writes it (`render_doc.py:929`) | its own dark-mode palette keys off it |

Renaming annotate's three removes today's three collisions and leaves the next document's to be found by the reader, mid-read. The isolation has to be structural.

**Shadow DOM isolates the CSS and breaks more than the queries.** `document.querySelector('[data-blk]')` does not pierce a shadow root, so every content-side query needs rewriting — and it is a LARGER change than the iframe, not an equal one: a `ShadowRoot` has `querySelector` and `getElementById` but no `createTreeWalker`, `createRange`, `createElement` or `body`, all four of which this page's JS uses (`:1054`, `:1474`, `:1498`, `:1003`). Those calls would each need a different host, not a different root. On top of that, `getSelection()` across a shadow boundary returns the host element rather than the inner node in several browsers, and `captureSelection()` is built on walking real text nodes and comparing offsets. Same cost, worse selection.

**The iframe is same-origin** — the frame and the shell are both served by `annotate_server.py` off `127.0.0.1` — so the outer JS reaches `frame.contentDocument` with no restriction. CSS isolation is separate and stronger: an iframe isolates styles by construction, whatever the origin.

**Same-origin is a SERVING property, not a structural one, and it is DETECTED rather than assumed.** Detected, not enforced: nothing prevents a reader opening the printed path over `file:` — `render_doc.py`'s CLI still prints it — so the honest claim is that the condition is named and caught at runtime, not that it cannot arise. This is the half the first draft of this design missed. It rejected the mixed `file://`-frame-under-`http://`-shell pair and overlooked the case the tooling actually produces: `render_doc.py <path>` writes a page and prints its path, and a reader who opens that path directly gets `file://` for BOTH documents. Chrome gives `file://` documents opaque origins, so `frame.contentDocument` throws and the page renders with no annotation layer at all — silently, looking merely empty.

Two exits, and the second is chosen:

- **`srcdoc`** inherits the parent origin, closing the hole with no serving requirement. It costs the author's own `#fragment` links: a `srcdoc` document inherits the PARENT's base URL, so a fragment resolves against the shell's URL and navigates the frame to the shell rather than scrolling within the document. They break — not for want of a base URL, but because the inherited one is the wrong document. Same trade this change already refused for `<base>`, refused here for the same reason. It also forces a 65 KB document through attribute escaping. Rejected.
- **Always serve, and refuse to pretend otherwise.** The frame is a real file in the page directory, served like the page. The shell reads `location.protocol` on load: under `file:` it renders a one-line notice naming the server command instead of an empty frame. **The notice is gated on the HTML path.** Ungated it would be a regression on a path that works today — a Markdown page opened over `file:` has no frame, needs no origin, and has always rendered fine; showing it a server notice would break a documented read path to fix a problem it does not have. **The trigger condition is named AND detected**, which is what the spec's "say so rather than degrade quietly" clause requires of precisely this situation.

### 1a. The markers need the one stylesheet that must cross the boundary

Isolating the author's CSS from the shell's also isolates the shell's CSS from the annotation markers, which are painted INTO the content — and on this path the content is the frame. `.cmt-hl` (`render_doc.py:736`) and `.cmt-sup`/`.cmt-num`/`.cmt-x` (`:738`-`:748`) live in the shell's stylesheet, and every one of them resolves `var(--mark)` / `var(--mark-wash)`, custom properties defined on the shell's `:root` (`:562` light, `:589` dark). Custom properties do not inherit across a frame boundary. Left alone, every highlight and every numbered superscript renders unstyled inside the frame — the layer is present, functional and invisible.

So exactly one stylesheet is injected into the instrumented document, and three constraints shape it:

- **It carries literal values, never `var()`.** The shell's custom properties are not reachable, so a `var()` reference resolves to nothing and fails the same way silently.
- **It is selected by `[data-cla-mark]`, an attribute the painter adds to each marker, not by the class.** The class names stay (the JS's `NON_SOURCE` logic keys off them), but an author may plausibly have defined `.cmt-sup`; nobody has defined `data-cla-mark`. This is decision 1's collision argument applied to the one thing that has to cross.
- **It carries both themes itself, via `prefers-color-scheme`.** The shell's `:root[data-theme]` does not cross either, so the frame cannot follow the reader's toggle. This is a real and accepted limitation: markers follow the system theme while the shell follows the toggle, and the two can disagree.

**This narrows decision 2's reversibility property and the spec's wording has to match.** The instrumented document is the original bytes plus the injected attributes plus this one appended `<style>` element — and the strip test removes both before comparing. The element is appended at the very END of the document so it shifts no `data-line`.

### 2. Attribute splicing at source offsets, not parse-and-re-serialise

`render_html.py` uses `HTMLParser` to *locate* start tags and then edits the original text at those offsets. It never rebuilds the document from a parse tree.

Re-serialising is the obvious implementation and it is wrong here: it normalises attribute quoting, drops the author's whitespace and comment placement, closes tags the author left implicit, and re-encodes entities. Every one of those changes the artifact under review into a different artifact, silently, while looking fine.

The splice makes reversibility a **property that can be measured**: remove the injected attributes from the output and the bytes equal the input. That test is worth more than any number of "looks right" assertions, and it is the design's answer to the spec's reversibility requirement.

It also bounds the damage from malformed markup. `HTMLParser` is lenient and will mis-nest an unclosed tag; the worst that does is put a `data-blk` on a surprising element. It cannot corrupt the document, because nothing outside the injected attribute is ever written.

### 3. A block is the innermost element holding text with no block beneath it

**Measured on the motivating document: 340 blocks, 0 nested, 4,468 words, 0 unannotatable.** The command is `pytest plugin-tests/tests/skills/annotate/test_render_html.py -k the_real_designed_document`, which asserts those figures and skips where the peer repo is absent.

**Neither number is what the design probe said, and the history is kept because it is the argument for not trusting an uncommitted probe.** The probe reported 319 blocks and 4,251 words. The word count was wrong because its own docstring admitted it interleaved element and text children approximately. The BLOCK count was wrong for a reason no reading would have found: 21 passages sat beside a block and belonged to none — including 13 callout and section labels, the headings a reader is most likely to argue with. Both were found by review, not by the probe, and the test above is now the only thing this figure rests on.

The formulation matters and the obvious phrasing is wrong. "Innermost non-inline element with no non-inline descendant" fails on this markup:

```html
<div class="wf-row is-out"><span class="lbl">Comision card</span><div class="bar" style="width:2%"></div><span class="amt">&minus;0,99</span></div>
```

The `.wf-row` *does* contain a non-inline descendant — the empty `div.bar` that draws the chart bar. Under the wrong phrasing the row is disqualified and the whole waterfall becomes unannotatable, which is the exact failure the structural rule exists to prevent. Candidacy requires **holding text**, and disqualification is by a descendant that is itself a **block**. `div.bar` holds no text, so it is not a block, so the row qualifies. Measured: all **ten** `.wf-row` elements — two waterfalls, at source lines 166-170 and 177-181 — come through as one block each.

The probe also caught the recursion getting this backwards — returning "I am a block" to the parent instead of "my subtree contains one" — which produced 349 blocks of which 348 nested. The disjointness assertion is what found it, which is why it is a spec scenario and not a code comment.

`<svg>` is opaque: a block, never descended into. Both figures come through as one block each, with their labels as the block's text. Splitting a chart into its own axis labels produces blocks nobody has an opinion about.

There are **two** lists, and an earlier draft wrongly merged them.

**Opaque — one block each, never divided:** `svg`, `math`, `canvas`, `object`. These hold genuine reader-facing content: MathML *is* the equation, `<canvas>` fallback content between the tags is standard practice, and `<object>` can embed a whole document. An earlier draft excluded all three outright while claiming "nothing reader-facing is reachable only through the excluded set" — a blanket claim that was checked against two of the twelve entries and was false for three others. They belong with `<svg>`, which is already opaque for the same reason: a reader has one opinion about a figure, not one per label.

**Excluded — no block, and no text:** `script`, `style`, `head`, `title`, `meta`, `link`, `template`, `noscript`, `base`, `iframe`. Each is verified rather than assumed: `<title>` is the tab label, `<noscript>` renders only with scripting off (which the annotation layer requires anyway), `<template>` is inert by definition, `<iframe>` has no text of its own, and the rest carry no reader-facing content at all.

**The match is on the exact tag name, never a prefix** — the motivating document's first content element is `<header class="masthead">` (line 127), and a prefix match on `head` would silently swallow the entire masthead. The document's top-level `<style>` is a non-inline element holding 111 lines of CSS (source lines 13-123); without the exclusion it is one of the largest blocks on the page and the reader is offered the document's stylesheet as a passage to comment on.

**Void elements** (`br`, `img`, `hr`, `input`, …) never open a scope. `HTMLParser` reports them through `handle_starttag` without a matching `handle_endtag`, so a tree builder that pushes them corrupts every subsequent nesting decision.

### 4. Sections are derived from headings; no wrappers are injected

`render_doc.py` wraps content in `<section class="sec" data-sec-id>` and the rail's `IntersectionObserver` observes those. Injecting them here would restyle the document — it defines bare `section { margin-top:3.5rem }`, and eight `<section>` elements of its own.

So headings carry the section identity instead (`data-sec-id` on the `h1`–`h6` that opens each section), and the observer observes headings. Depth is measured against the shallowest heading present, exactly as `rail()` (`:512`) already does.

**The rail's navigation does NOT survive unchanged, and the first draft of this design said it did.** `rail()` emits `<a class="rail-item" href="#%s">` targeting the section slug (`render_doc.py:534`). With the headings inside the frame, the shell document holds no element with that id, so every rail click navigates nowhere — the whole rail goes dead, silently, with the links still looking like links.

**The rail scrolls through the content root ONLY on the HTML path.** The click handler intercepts and scrolls into `CDOC` when a frame is present, and does nothing at all when there is not — the Markdown path keeps native fragment navigation, untouched.

An earlier wording intercepted on both paths "since `CDOC === document` makes the destination identical", weighing only the loss of the URL hash. **The destination is identical and the navigation is not.** `rail()` emits a plain `<a href="#slug">` with no listener (`:512`-`:541`), so today a rail click is native fragment navigation: it pushes a history entry and sets `location.hash`. A `preventDefault()` removes that history entry unconditionally, so Back after a rail click would stop returning to the previous position — on the Markdown path too, where nothing was wrong. This design's own first Goal is that the Markdown path is *provably* unchanged, and an unconditional intercept quietly trades that away for a path that does not need it. Gating on the frame costs one condition and keeps the goal true.

The `href` stays on the element on both paths, so it keeps its link semantics for keyboard and assistive technology.

A document's OWN internal `#fragment` links need nothing: inside the frame they resolve within the frame, which is where their targets are.

**The scroll-spy observer cannot be built in the outer window at all, and a selector swap does not save it.** An `IntersectionObserver` constructed in the SHELL, with a null root, observing headings inside the frame, reported **0 of 12** — not a wrong entry, no callbacks whatever, at rest and after scrolling. An earlier draft of this decision assumed the observer would keep working once its selector moved off `.sec`; it would have shipped a rail that never lights.

**The observer is constructed in the FRAME's window** — `new CWIN.IntersectionObserver(…)` — observing the frame's own headings. Measured in both frame-sizing modes: it lit exactly one heading, the correct one.

**Its `rootMargin` must be given in pixels, not percentages.** The band is currently `-12% 0px -70% 0px`, and percentages resolve against the ROOT's height. Inside a frame sized to its content that root is the whole document — 7584 px in the measurement, against an 800 px viewport — so the band came out roughly nine times too tall. It happened to admit one heading on that fixture and would admit several on a denser document. On the HTML path the insets are computed from the OUTER viewport height and reapplied on resize, which reproduces what the percentages mean on the Markdown path rather than what they resolve to here.

**Two more sites key off the `.sec` wrapper, and neither is a `document.*` call the content-root refactor would catch.** `document.querySelectorAll('.sec').forEach(s => io.observe(s))` (`:963`) selects nothing when no wrappers are injected, so the scroll-spy observes zero targets; and `paintRailCounts` resolves a block's section with `el.closest('.sec')` and `sec.dataset.secId` (`:980`-`:982`), which returns null for every block, so every rail badge reads zero — the exact failure that function's own comment says the derivation exists to prevent. Swapping the root would leave both silently dead.

**Both resolve through `[data-sec-id]` instead of `.sec`, and the two paths converge rather than diverge.** The Markdown wrapper already carries `data-sec-id`, so the observer's selector changes from `.sec` to `[data-sec-id]` and keeps working unchanged there. For the count, every block carries `data-sec-id` in BOTH renderers, and the lookup becomes the block's own value with `closest('[data-sec-id]')` as the fallback. Converging is deliberate: a rule that holds on one path only is a rule nobody will remember to check on the other.

**`scrollIntoView` propagates to the outer page. Measured, not assumed.** A node inside a content-sized same-origin frame, scrolled into view, moved the OUTER page from 0 to 5304 px while the frame's own `scrollY` stayed 0. So `focusBlock()` (`:1029`-`:1035`), the drawer's "go to passage" (`:1892`-`:1895`) and the rail all keep working through the same call, and none of them needs `contentRect()`. This was written as an open question and settled in a browser before anything was built against it, because the failure mode — both controls silently not moving the page — is invisible to every string check.

**The scroll uses `{block:'center'}`**, matching the two programmatic scrolls already in the page (`:1023`, `:1033`). `.sec{scroll-margin-top:4rem}` (`:675`) exists because the top bar is sticky, and a heading inside the frame inherits no such rule — a default `block:'start'` would land it under the bar.

**Middle-click and Ctrl/Cmd-click do not fire `click`**, so they follow the surviving `href="#slug"` and open a second shell tab whose fragment targets nothing. Accepted rather than fixed: the page is a single-session working view in a temp directory, opening a second copy of it is not a use anyone has, and removing the `href` would cost the element its link semantics for keyboard and screen-reader users, which is the larger loss.

Trade-off, stated because it is a real regression on this path: observing a heading rather than a region means the scroll-spy lights a section when its *heading* crosses the band, not while its body is in view. The `rootMargin` band already in use (`-12% 0px -70% 0px`) makes this close to equivalent in practice, but it is not identical, and it is a difference the Markdown path does not have.

### 5. One content root, and its identity on the Markdown path is the safety property

`CDOC`/`CWIN` resolve to the frame's document/window in HTML mode and to `document`/`window` otherwise. Every content-side call moves; the shell's own calls (`getElementById('cmt-pop')`, the drawer, the undo bar) do not.

The Markdown path's correctness rests entirely on `CDOC === document` there. That is exactly the kind of claim that reads as obviously true, so it is asserted directly rather than argued — a rendered Markdown page must contain the identity binding, and its existing tests must pass unchanged.

The frame is sized to its content height, so the outer page scrolls and there is no inner scrollbar. A frame with its own scrollbar would need a second scroll offset in every geometry calculation and a scroll listener on the frame.

**The geometry is NOT unchanged, and the range the first draft named was wrong.** Three sites compute a rect from an element that will live inside the frame, and only one of them is in `:1560`–`:1631`:

| Site | What it places | Currently |
|---|---|---|
| `:1175`–`:1177` | the "+ annotate" button | `getSelection().getRangeAt(0).getBoundingClientRect()` + `window.scrollX/Y` |
| `:1182`–`:1187` | the comment popover | derived from the button's own computed position |
| `:1630` | a margin note's top | `c.mark.getBoundingClientRect().top + window.scrollY` |

A rect taken inside the frame is in the FRAME's viewport, so each needs the frame's own offset added. One helper does it: `contentRect(target)`.

**Its coordinate space is OUTER VIEWPORT, and saying so precisely is the whole point.** An earlier wording said "outer PAGE coordinates when framed, the raw rect when not" — which is two different spaces on the two branches, because a raw `getBoundingClientRect()` is viewport-relative. They differ by exactly the scroll offset, so whichever branch was wrong would produce a margin note whose error grows as you scroll: the `top:-135.78px` class this repo already paid for. The contract is therefore: **return the raw rect plus the frame's own `getBoundingClientRect().top/left` when framed, and the raw rect unchanged when not — both viewport-relative.** Callers keep their existing `+ window.scrollY` / `+ window.scrollX` terms, which are already correct against the outer viewport.

**It accepts an element OR a rect, because one of its sites has no element.** `:1175` measures `getSelection().getRangeAt(0).getBoundingClientRect()` — a Range, not an element. A helper typed to elements could not cover the first site it is listed for, and the one-function equivalence property would then be a claim about two of three sites.

**Two sites compute a rect, not three.** `:1182`-`:1187` places the popover from the button's already-computed `style.left`/`style.top`, so it inherits the correction rather than needing one. The table above lists it because it is cross-boundary reasoning, not because it calls `getBoundingClientRect`.

**`#doc` does not exist on the HTML path and one call dereferences it unguarded.** `clearMarks()` calls `mergeSplitInline(document.getElementById('doc'))` (`:1403`), and `mergeSplitInline` goes straight to `root.querySelectorAll(...)` with no null check (`:1382`). `id="doc"` is emitted only by the Markdown body variant (`:2075`), and decision 2 forbids adding any element to the instrumented document — so on the HTML path the id exists in neither document and the first repaint throws, taking the annotation layer down with it. The content root is passed as an ELEMENT (`CDOC.body`), not looked up by a shared id, and `mergeSplitInline` gets a guard. An id shared between two documents was always the wrong handle here; the refactor just makes it fatal.

**Input listeners need a third bucket that decision 5's two-way split does not have.** `document.addEventListener('mouseup', …)` (`:1164`) is the entire selection-to-button trigger and `document.addEventListener('keydown', …)` (`:1208`) carries Escape and the shortcuts. Neither ever fires for an event inside a frame. So the partition is three-way, not two: shell-only calls stay on `document`, content-only calls move to `CDOC`, and **these listeners bind on BOTH**.

**Binding on both DOES double-fire on the Markdown path unless the mechanism is stated, and an earlier draft asserted it did not.** `addEventListener` de-duplicates only an identical `(type, callback, capture)` triple, and both handlers are inline anonymous arrow literals today (`:1164`, `:1208`) — a `[document, CDOC].forEach(d => d.addEventListener(...))` creates two distinct closures and registers both. Two requirements, not one: the handler is **hoisted to a named function and registered by the same reference**, AND the second binding is guarded by `if (CDOC !== document)`. Either alone would do; both are cheap, and a double-fire here is silent — neither handler is meaningfully non-idempotent — so nothing would report it.

**A frame's `contentDocument` is `about:blank` before its real document arrives, and `about:blank` is already `readyState === 'complete'`.** So the obvious readiness test passes against an empty document: measured, the frame reported height 150 and `getElementById` returned null for content that was plainly in the file. The check must also require `contentDocument.location.href !== 'about:blank'`, and otherwise wait for the frame's `load`. Nothing content-side may run before that point, which is why the content-side initialisation is a function called from one place rather than a run of top-level statements.

**The frame's height has to be re-measured, not measured once.** Content height is the load-bearing premise for all of the above, and it changes after first layout — the motivating document pulls three font families from Google Fonts (its lines 9–11), and text reflows when they arrive. `render_doc.py:1568` is already the one entry point for "the geometry moved"; the frame's `load`, a `ResizeObserver` on the frame's `documentElement`, and the frame document's `fonts.ready` all feed it.

### 6. One dispatch, shared by the CLI and the server

One resolution function decides doc / change / html from the target. **`render_doc.py`'s own CLI uses it too**, which the first draft left out: `SKILL.md` §2 documents `render_doc.py <path>` as step one, so scoping the dispatch to the server alone would leave two documented commands producing different pages for the same file — the CLI still emitting escaped markup while the server emits the frame. `render_doc.py foo.html` delegates to `render_html.build()`. It is used by both `build`-time and `_render()`.

**That closes an import cycle, and this repo has never had one.** `render_html` needs `page()` from `render_doc`; `render_doc`'s CLI now needs `build()` from `render_html`. Every existing module here imports one-directionally — `render_change.py:34` imports `render_doc` and nothing imports `render_change` back except `annotate_server.py:36`. A bare top-level `import render_html` in `render_doc` fails outright, because `render_html`'s own module-level `import render_doc` runs while `render_doc` is still initialising and `page()` is not yet defined.

**`render_doc` imports `render_html` inside the dispatch function, not at module level.** `render_html` keeps its ordinary top-level import. Nothing is needed at import time in that direction, so the lazy import is not a workaround for a design smell — it matches when the dependency actually exists.

**One consequence is stated because it is invisible and would otherwise be found by debugging:** running `python render_doc.py foo.html` makes `render_doc` the `__main__` module, so `render_html`'s `import render_doc` loads a SECOND copy of it — two module objects, two `Ctx` classes. It is harmless here only because nothing does an `isinstance` check across the seam: `page()` is a pure function of its arguments and `check_anchors` reads `ctx.blocks` structurally. **Anything added later that type-checks a `Ctx` breaks on this path and on no other**, which is why it is written down rather than left to be discovered.

**`render_html.build()` returns the same `(out_path, ctx, words)` 3-tuple** as `render_doc.build()`, with a `ctx` that `check_anchors` accepts — both callers unpack it and both then call `check_anchors` (`render_doc.main()`, and `annotate_server.py:381`/`:397`). `_render()` gains an html branch beside the two it has; its existing contract — the document path comes from the server's own argument and never from the request — is unchanged and matters as much here.

### 7. An author's own `data-blk` is refused, not overwritten

HTML parsers keep the FIRST occurrence of a duplicated attribute. So splicing `data-blk` into a start tag that already carries one is a silent no-op for that element, and every later `querySelector('[data-blk="bN"]')` (`:979`, `:1030`, `:1427`) then binds to the AUTHOR's value — an annotation anchors to whatever their attribute happened to name.

**The scan is over start-tag ATTRIBUTES, and that scope is chosen rather than assumed.** The hazard is precisely a splice onto an element that already carries the attribute, so attributes are what must be refused. The same tokens appearing inside the author's own `<style>` selector or `<script>` — which `HTMLParser` reports as character data, not attributes — are a different and milder problem: their rules could style our markers or their queries could pick them up, but no annotation mis-anchors. **That case warns; only the attribute case refuses.** Refusing on any occurrence anywhere would be broader than the hazard, and a refusal that fires on a document nothing is wrong with is how a guard gets switched off.

The instrumenter scans before writing anything and **refuses the document with a message naming the offending element** rather than producing a page whose anchors are quietly wrong. Refusing is right rather than harsh: the failure it prevents is undetectable from the page, and a reader would have no reason to doubt it.

The motivating document contains none of the three, so **the corpus cannot exercise this branch** — it needs its own fixture, which is why it is a task rather than a note.

### 8. The relative-asset check needs a predicate, and it warns rather than refuses

"Detects relative `src`/`href` references" is not implementable as written, and the naive version is worse than nothing: in-page `href="#…"` anchors, `mailto:`, `tel:`, `data:` and protocol-relative `//host/path` are all non-absolute and all universal in designed documents, so a literal test fires on almost every real file. The predicate is: a reference with no scheme, not beginning `#`, `//`, `data:`, `mailto:`, `tel:` or `javascript:`.

It **warns and renders**, where the duplicate-attribute case above refuses. The difference is what the reader loses: a missing image is visible in the page, so a warning is enough for them to judge it; a mis-anchored annotation is invisible, so nothing short of refusing is safe.

The motivating document has zero relative references (only three `https://fonts.*` links), so again the corpus exercises only the false branch and a fixture is required.

### 9. Stdout encoding, not just file encoding

`SKILL.md` already requires an explicit encoding on every file open. The design probe hit the other half of the same trap: on Windows `sys.stdout` is cp1252, so printing a block's text — which for this document contains `−`, `ă`, `ț` — raises `UnicodeEncodeError` and takes the whole run down. Any diagnostic output naming block text must reconfigure stdout or transliterate. This is a Windows-only failure, invisible on POSIX, in a repo with no CI.

## Risks / Trade-offs

- **Cross-frame selection behaves differently from same-document selection** → the opt-in Playwright suite is where this is proven. A string grep over generated HTML cannot answer whether a selection inside the frame anchors to the right block or whether its offset is right. This is precisely the exception `CLAUDE.md` grants that suite, and iframe cases are in scope for this change.
- **The margin note beside a block in a frame is geometry across a boundary** → same mitigation, and it is the specific defect class that shipped last time this page's layout changed (a note drawn at `top:-135.78px` beside nothing).
- **A document whose own JS rewrites the DOM** → out of scope, stated above. The blocks are instrumented statically and would no longer match. Not detected by this change.
- **A document with relative assets** → out of scope. It must **report** rather than render a broken page silently: the renderer detects relative `src`/`href` references and says the document is not self-contained, naming what it found. A silent half-rendered page is the failure mode the spec's "say so rather than degrade quietly" clause exists to forbid.
- **`HTMLParser` mis-nests badly malformed markup** → bounded by decision 2: the output is still byte-identical outside the injected attributes, so the worst case is a block boundary in an odd place, never a corrupted document.
- **The refactor touches working code that has no CI, and the existing suite CANNOT guard it** → measured with `grep -ln "playwright\|page\.evaluate\|goto(" plugin-tests/tests/skills/annotate/*.py`: exactly one of the seven files there executes JavaScript. `test_page_in_a_browser.py` holds 19 of the 422 asserts in that directory (`grep -c "assert " plugin-tests/tests/skills/annotate/*.py`, summed — the earlier figure of 441 was an arithmetic error and reproduced by no command) and `importorskip`s away when Playwright is absent; the other six hold the remaining 403 and are string greps over generated HTML that cannot run a line of the code being rewired. Calling the existing suite the guard for a JS refactor — as the first draft did — would let this change be accepted on a machine where nothing executing ever ran over it, and with no CI that is the DEFAULT machine. **So the browser suite is a required gate for this change specifically**, with its pass count recorded, and a run that skipped it has not verified the refactor. That obligation is a task, not a note.

- **The motivating document must never be copied into this repo.** It is a peer repo's business briefing and carries real financial figures. Every checked-in fixture is synthetic and reproduces only the SHAPES that matter — a `.wf-row`-style container whose sole non-inline child is empty, an inline `<svg>` with text labels, a top-level `<style>`, a table, a `<header>` whose tag name is a prefix of an excluded one. The real file is referenced by path and skipped when absent, so no test depends on it and no run leaks it.

## Migration Plan

None needed. The change is additive on the extension dispatch; existing corpora, page names and annotations are untouched. A previously-annotated `.html` file — annotated as plain text, therefore anchored to markup — would find its anchors lost on the first render under the new path. That is the correct report (the text those annotations were written against genuinely is not on the page any more) and it is what "a lost anchor is a finding, not a fault" already covers.
