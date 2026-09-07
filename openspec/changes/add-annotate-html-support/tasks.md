<!--
Rewritten in Review round 2. Round 1's rewrite carried a changelog whose task numbers were wrong in
three of seven bullets — the round-2 review caught it, so this one is verified by grep rather than
asserted. What round 2 added, by the task that carries it:

  1.2  opaque vs excluded are now TWO lists (math/canvas/object hold real content — round 2)
  1.6  the collision scan refuses on attributes and WARNS on style/script text (scope was ambiguous)
  2.2  the strip test subtracts the injected stylesheet as well as the attributes
  2.7  NEW — the marker stylesheet injected into the frame (design decision 1a; without it every
       highlight and superscript renders unstyled, because the shell's :root vars do not cross)
  3.1  contentRect returns OUTER VIEWPORT coords and accepts a rect, not only an element
  3.3  the rail intercept is GATED on the framed path — an unconditional preventDefault() removed
       the history entry on the Markdown path too
  3.4  the both-documents binding needs a named handler AND a CDOC !== document guard
  3.8  NEW — mergeSplitInline takes CDOC.body, not getElementById('doc'), plus a null guard
  3.6  the file: notice is GATED on HTML mode, or it regresses Markdown-over-file:
  4.3  the .sec-keyed sites move to [data-sec-id]; blocks carry it in BOTH renderers
  5.3  the import cycle is broken by a function-local import, with both orders tested
  7.7  NEW — does scrollIntoView inside a content-sized frame scroll the outer page? A browser
       question, settled before the implementation depends on it
  7.8  NEW — the Markdown rail still pushes a history entry (the regression 3.3 exists to avoid)

Nothing from the round-1 list was dropped.
-->

## 1. The parser, the block rule, and the two refusals

- [x] 1.1 Add `skills/annotate/scripts/render_html.py` with an `HTMLParser` subclass building a node tree carrying each element's tag, its `getpos()` line, and the source offsets of its start tag; verify with a test that a void element (`<br>`, `<img>`, `<hr>`) does not open a scope and a following sibling's depth is unchanged.
- [x] 1.2 Implement the block rule with its TWO tag lists — opaque (`svg`, `math`, `canvas`, `object`: one block each, never divided) and excluded (`script`, `style`, `head`, `title`, `meta`, `link`, `template`, `noscript`, `base`, `iframe`: no block, no text), matched by EXACT tag name; verify a `<math>` element is one block rather than excluded, and that no returned block contains another.
- [x] 1.3 Verify the `.wf-row` shape: an element holding text whose only non-inline descendant is EMPTY qualifies as a block. Use the markup quoted in `design.md` decision 3; assert the row is one block, neither skipped nor split. Record the measured block/word counts inline (the design's "319 blocks, 0 nested, 4,251 words" came from an uncommitted probe and stands or is corrected here). **Measured: 340 blocks, 0 nested, 4,468 words, 0 unannotatable** on the real document (`pytest plugin-tests/tests/skills/annotate/test_render_html.py -k the_real_designed_document`). The design's 4,251 came from the throwaway probe's approximate interleaving, and its 319 missed 21 passages that sat beside a block and belonged to none — 13 of them callout and section labels. PR review round 2 found those; a reading would not have.
- [x] 1.4 Verify the exact-tag-name match: `<header>` is NOT excluded by the `head` entry; assert a `<header>` block is returned.
- [x] 1.5 Implement the relative-asset check with the design's predicate — no scheme, and not beginning `#`, `//`, `data:`, `mailto:`, `tel:` or `javascript:`; verify `<img src="pic.png">` warns and a fixture carrying `#anchor`, `mailto:a@b.c`, `//cdn/x.js`, `data:` and `https://` does not.
- [x] 1.6 Implement the collision scan with its two scopes: an existing `data-blk`/`data-line`/`data-sec` **attribute** refuses the document naming the element; the same tokens in `<style>` or `<script>` **text** warn and render. Verify both fixtures, and that the attribute case writes no page.
- [x] 1.7 Implement per-block text accumulation matching the browser's `textContent` — raw character data, entities expanded, excluded subtrees contributing nothing, whitespace preserved verbatim; verify against a fixture with entities (`&minus;`, `&amp;`), nested inline markup and a `<style>` sibling, asserting the exact expected string.

## 2. Instrumentation and the reversibility property

- [x] 2.1 Splice `data-blk`/`data-line`/`data-sec` into the located start tags at their source offsets, never re-serialising a parse tree; verify the output differs from the input only inside the injected attributes.
- [x] 2.2 Add the round-trip test: strip BOTH the injected attributes and the appended marker stylesheet, and assert the result is byte-identical to the input.
- [x] 2.3 Verify the splice against a start tag spanning several source lines and one with an attribute value containing `>`; assert `data-line` still names the tag's first line and the round-trip still holds.
- [x] 2.4 Assert the only element added is the marker stylesheet, by comparing tag counts before and after.
- [x] 2.5 Derive sections from headings — `data-sec-id` on the `h1`–`h6` opening each section, and on every block; verify a document with NO headings yields an empty rail rather than an error.
- [x] 2.6 Add the fixture corpus, all synthetic. **The motivating briefing is a peer repo's document carrying real financial figures and MUST NOT be copied into this repo** — reference it by path and skip when absent. Verify no fixture contains a figure from it and the suite passes with the peer repo absent.
- [x] 2.7 Inject the marker stylesheet at the END of the instrumented document: literal values only (no `var()`, which cannot resolve across the boundary), selected by `[data-cla-mark]` rather than by class, and carrying both themes via `prefers-color-scheme`. Verify it contains no `var(` and that the painter adds `data-cla-mark` to every marker.

## 3. The page: geometry, navigation, and the serving requirement

- [ ] 3.1 Add `contentRect(target)` accepting an element OR a rect and returning OUTER VIEWPORT coordinates — the raw rect plus the frame's `getBoundingClientRect().top/left` when framed, the raw rect unchanged when not; verify the unframed path returns a value equal to the raw rect, and that a Range rect is accepted.
- [ ] 3.2 Route the two rect-computing sites through it — the annotate button (`render_doc.py:1175`–`:1177`) and the margin note's top (`:1630`); verify callers keep their `+ window.scrollY` term and no placement path calls `getBoundingClientRect()` without going through `contentRect`.
- [ ] 3.3 Gate the rail intercept on the framed path: when a frame is present the handler scrolls into `CDOC` with `{block:'center'}`; when there is none it does nothing and native fragment navigation stands. Verify the Markdown path registers no `preventDefault`.
- [ ] 3.4 Bind `mouseup` (`:1164`) and `keydown` (`:1208`) on both documents using a NAMED handler registered by the same reference, guarded by `if (CDOC !== document)`; verify the handlers are hoisted (not inline arrows at the call site) and the guard is present.
- [ ] 3.5 Feed the frame's `load`, a `ResizeObserver` on its `documentElement`, and its `fonts.ready` into the existing "geometry moved" entry point at `:1568`; verify each is wired and the unframed path registers none.
- [ ] 3.9 Gate all content-side initialisation on a readiness check that requires `contentDocument.location.href !== 'about:blank'`, not merely `readyState === 'complete'`. Measured in task 7.7: a fresh frame's `contentDocument` is `about:blank`, which is already complete, so the obvious check ran against an empty document — frame height 150, every lookup null. Verify with a test that initialisation does not run against `about:blank`.
- [ ] 3.6 Add the `file:` protocol notice, **gated on the HTML path**: under `file:` with a frame, render a one-line message naming the server command instead of an empty frame. Verify a Markdown page opened over `file:` shows no notice — it works today and must keep working.
- [ ] 3.7 Add the frame-hosting body variant to `page()`, sized to content height so the outer page scrolls; verify the generated shell sets no fixed frame height and does set it from the frame's own content.
- [ ] 3.8 Pass the content root to `mergeSplitInline` as an element (`CDOC.body`) rather than `document.getElementById('doc')` (`:1403`), and add the null guard `mergeSplitInline` lacks (`:1382`); verify the HTML path repaints without throwing.

## 4. The content root, threaded one concern at a time

- [ ] 4.1 Introduce `CDOC`/`CWIN`, resolving to the frame's document and window when a frame is present and to `document`/`window` otherwise; verify a rendered Markdown page contains the identity binding.
- [ ] 4.2 Move the block and element queries — the `[data-blk]` lookups (`:979`, `:1030`, `:1424`, `:1427`); verify each by name in the generated JS.
- [ ] 4.3 Retarget the two `.sec`-keyed sites to `[data-sec-id]`: the observer's target query (`:963`) and `paintRailCounts`'s section lookup (`:980`–`:982`, now the block's own `data-sec-id` with `closest('[data-sec-id]')` as fallback). Verify a Markdown page's rail badges still count correctly — the Markdown wrapper already carries `data-sec-id`, so this path must be unchanged.
- [ ] 4.7 Construct the scroll-spy observer in the FRAME's window (`new CWIN.IntersectionObserver(…)`), not the shell's. Measured in task 7.7: a shell-side observer reports 0 of 12 frame headings — no callbacks at all — so a selector swap alone ships a rail that never lights. Verify the generated JS constructs it through `CWIN`.
- [ ] 4.8 Give the observer a PIXEL `rootMargin` on the HTML path, computed from the outer viewport height (12% top, 70% bottom) and recomputed on resize. Percentages resolve against the root's height, and inside a content-sized frame that is the whole document — measured at 7584px against an 800px viewport, a band ~9× too tall. Verify the Markdown path still uses the percentage form unchanged.
- [ ] 4.4 Move the marker cleanup — `.cmt-sup` and `mark.cmt-hl` (`:1398`, `:1399`); verify both.
- [ ] 4.5 Move `captureSelection`'s internals — `getSelection`, `createElement`, `createTreeWalker` (`:1043`–`:1160`); verify each resolves through `CDOC`/`CWIN`.
- [ ] 4.6 Move the gutter geometry (`:1560`–`:1631`), then run the aggregate check: no bare content-side `document.querySelector('[data-blk]'`-shaped query remains anywhere in the generated JS.

## 5. Wiring the renderer to the page and the server

- [ ] 5.1 Add `render_html.build()` returning the same `(out_path, ctx, words)` 3-tuple as `render_doc.build()`, with a `ctx` that `check_anchors` accepts; verify both files exist and the shell references the frame by its written name. (Depends on 3.7.)
- [ ] 5.2 Add one target-resolution function returning doc / change / html from a path; verify `.html` and `.htm` resolve to html, `.md` to doc, a change id to change, and an unknown extension to doc-as-plain-text as before.
- [ ] 5.3 Use that resolver in `render_doc.py`'s CLI as well as the server, importing `render_html` **inside the dispatch function** so no module-level cycle forms. Verify by importing each module first in a fresh interpreter — both orders must succeed — and that `render_doc.py foo.html` and the server produce the same page.
- [ ] 5.4 Add the html branch to `_render()` beside the existing doc and change branches, reporting blocks, words and lost anchors as the doc branch does; verify a rebuild request against an HTML target returns the summary shape the page expects.
- [ ] 5.5 Verify the document path still comes from the server's own argument and never from the request, on the new branch as on the old ones.
- [ ] 5.6 Update `render_doc.py`'s argparse help ("the .md or .txt file to render") and the server's build-it-first hint (`annotate_server.py:657`), both of which name only the two old renderers; verify neither still omits HTML.
- [ ] 5.7 Reconfigure stdout to UTF-8 with a replacement error handler before any diagnostic printing block text; verify by printing a block containing `−` and `ț` under a forced cp1252 stdout and asserting no exception.

## 6. Anchors and the corpus

- [ ] 6.1 Wire `check_anchors` to the HTML renderer's `ctx`; verify an annotation written against an HTML block is found again on a rebuild of the unchanged document, and reported lost when the passage is edited out.
- [ ] 6.2 Verify `line` on an HTML annotation identifies the line of the SOURCE file holding the passage, by annotating a known block and comparing against `grep -n` on the source.

## 7. Browser-level verification — the refactor's real gate

- [ ] 7.1 Add an iframe selection case: a selection inside the frame anchors to the correct block with the correct offset and context.
- [ ] 7.2 Add the textContent-equivalence case: render an HTML fixture, read a block's Python-recorded text and the live `blockText()` result for the same block, and assert they are equal. Nothing else in the suite cross-checks this, and both halves of the anchoring machinery depend on it.
- [ ] 7.3 Add a margin-note geometry case across the frame boundary, at the wide breakpoint and with the drawer open, **and after scrolling** — the coordinate-space error decision 5 describes is invisible at scroll position zero.
- [ ] 7.4 Add a rail case: clicking a rail entry scrolls to its heading inside the frame.
- [ ] 7.5 Add a collision case: a fixture defining `.wrap`, `.bar` and `:root[data-theme="dark"]` renders with its own values while the annotate shell keeps its own — and the markers are still styled, which is what decision 1a exists for.
- [ ] 7.6 Add an `IntersectionObserver` case: an outer-window observer with a null root over frame targets lights ONE rail entry, not all of them.
- [x] 7.7 Settle whether `scrollIntoView` on a node inside a content-sized same-origin frame scrolls the OUTER page. **Measured in Chromium: YES** — outer `scrollY` 0 → 5304 while the frame's own `scrollY` stayed 0, so `focusBlock` and the rail both keep working unchanged and neither needs `contentRect`. The same probe settled two more: a shell-side `IntersectionObserver` sees **0 of 12** frame headings (→ tasks 4.7, 4.8), and a fresh frame's `contentDocument` is `about:blank` with `readyState === 'complete'` (→ task 3.9). `innerRect.top 5688 + frameRect.top -5304 = 384` confirms `contentRect`'s stated contract.
- [ ] 7.8 Add a Markdown-path regression case: a rail click still pushes a history entry and Back returns to the previous scroll position. This is the regression 3.3's gating exists to prevent, and no string check can see it.
- [ ] 7.9 Add a double-fire case: fire one `mouseup` on the Markdown path and assert the handler runs exactly once.

## 8. Documentation and the gate

- [ ] 8.1 Correct `SKILL.md` §1's "anything else renders as plain text" promise and §2's render command list to name `render_html.py`; verify no other line still claims HTML renders as plain text.
- [ ] 8.2 Correct `SKILL.md`'s frontmatter: `argument-hint` names only `.md`/`.txt`, and the `description` promises a "self-contained HTML page" which the HTML path is not. Verify both changed and the skill still loads.
- [ ] 8.3 Extend `SKILL.md` §1's precondition text with the three new reportable conditions — a non-self-contained document, one already using the instrumentation's attributes, and a page opened over `file:` — so the operator knows what to tell the user. Verify all three are named.
- [x] 8.4 Add `render_html.py` to the `CLAUDE.md` script table; verify the new row's Script column matches the form `annotate/scripts/<file>.py`, identical to the existing `render_doc.py`, `render_change.py` and `annotate_server.py` rows, with no leading `skills/`.
- [x] 8.5 Add a mutant batch at `plugin-tests/mutants/annotate/test_render_html.py` covering the block rule's disqualification condition, the void-element handling, the exact-tag-name match, the opaque/excluded split, the relative-asset predicate and the splice offsets; run `python3 plugin-tests/mutate.py plugin-tests/mutants/annotate/test_render_html.py` and record killed/survived inline, with a stated reason for any survivor. **Measured: 29 mutants, 29 killed, 0 survived** (`python3 plugin-tests/mutate.py plugin-tests/mutants/annotate/test_render_html.py`). The first run had 1 survivor — a test parametrized over `RH.OURS`, the constant the mutant shrinks, so its case list shrank with it and it could not fail; the test was fixed, not the mutant. PR review then added 10 more mutants, including two for a recursive call whose deletion had passed the entire suite.
- [ ] 8.6 **Run the browser suite and record its pass count inline — this change is not verifiable without it.** Measured during review: only `test_page_in_a_browser.py` executes JavaScript (19 of the 422 asserts in that directory, per `grep -c "assert " plugin-tests/tests/skills/annotate/*.py`), so with Playwright absent nothing executing runs over this refactor. `pip install playwright && playwright install chromium`, then `pytest plugin-tests/tests/skills/annotate/test_page_in_a_browser.py`. A skip here is a failed gate, not a pass.
- [ ] 8.7 Run `pytest plugin-tests -q -n auto --dist loadfile` and record the measured pass/skip counts inline; confirm the skip count matches a serial run of the same tree.
- [ ] 8.8 Run `node --test plugin-tests/node/mechanical-checks.test.mjs` and record the result inline — the pytest gate does not reach it.
- [ ] 8.9 Render and serve the real briefing end-to-end, open it, and confirm by observation that the design is intact and a passage can be annotated; record what was observed. This is human-work: it needs a person to judge whether the page looks right. Defer to the user if the peer repo is unavailable.
