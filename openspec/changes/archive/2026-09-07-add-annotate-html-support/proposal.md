## Why

`annotate` can put a Markdown document in front of a reader and take their comments back. It cannot do that for an HTML document. `render_doc.build()` treats every extension other than `.md`/`.markdown`/`.mdown` as plain text, so an `.html` file renders as its own escaped markup — a page of `<div class="wf-row">` where the content should be. The skill reports success and produces something nobody can read.

That gap matters because a designed HTML document is increasingly the artifact under review, not a stepping stone to one. The motivating case is a 65 KB self-contained business briefing in a peer repo: styled tables, inline SVG waterfall charts, its own dark-mode palette. Its layout is part of what the reader is being asked to judge, so extracting the words and discarding the design would throw away half the thing under review.

## What Changes

- **New renderer** `skills/annotate/scripts/render_html.py`. It instruments the author's own HTML — splicing `data-blk` / `data-line` / `data-sec` into existing start tags at their exact source offsets — and changes nothing else about the file.
- **The annotation layer wraps the author's page rather than replacing it.** The page `render_doc.py` already builds becomes the outer shell (top bar, navigation rail, margin, drawer); the instrumented document is served inside a same-origin iframe. The reader sees the document as its author designed it.
- **The page JS gains one content root.** Roughly twenty content-side `document.*` calls become `CDOC`/`CWIN` calls. On the Markdown path `CDOC === document`, so that path's behaviour is unchanged — the equivalence is the refactor's safety property and is asserted directly.
- **`annotate_server.py` dispatches `.html`/`.htm`** to the new renderer, in `build`-time and in its `/api/render` rebuild endpoint. It already serves the whole page directory, so the frame needs no new route.
- **`SKILL.md` §1 is corrected.** It currently promises that "anything else renders as plain text, with no markup interpretation at all", which stops being true for HTML.
- Tests under `plugin-tests/tests/skills/annotate/`, a mutant batch under `plugin-tests/mutants/annotate/`, and iframe cases added to the Playwright suite. **That suite is a required gate for this change rather than an optional one**: measured during review, it is the only one of the seven annotate test files that executes JavaScript, so with it skipped nothing executing runs over a refactor that rewires roughly twenty call sites.

- **Two new refusals/warnings the skill did not have**: a document already carrying `data-blk`/`data-line`/`data-sec` is refused rather than instrumented (the collision is invisible on the page and would silently mis-anchor every annotation in that element), and a document with relative asset references warns and renders.

Not breaking. A Markdown or plain-text target keeps its existing rendering, its existing corpus, and its existing anchors.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `cla-plugin`: the annotate skill gains a stated contract for HTML targets — that the author's document is presented as authored, that instrumentation is additive and reversible, and that a block is chosen by a rule general enough to reach content that is not a paragraph.

## Impact

- `.claude/plugins/cla/skills/annotate/scripts/render_html.py` — new.
- `.claude/plugins/cla/skills/annotate/scripts/render_doc.py` — the `JS` blob's content-side queries and its geometry; `page()` gains a frame-hosting body variant; **and its own CLI takes the shared extension dispatch**, so `render_doc.py foo.html` and the server cannot produce different pages for one file.
- `.claude/plugins/cla/skills/annotate/scripts/annotate_server.py` — extension dispatch in the server's target resolution and in `_render()`.
- `.claude/plugins/cla/skills/annotate/SKILL.md` — §1's rendering promise and its precondition list, §2's render command list, **and the frontmatter**: `argument-hint` names only `.md`/`.txt`, and the `description` promises a "self-contained HTML page", which the HTML path is not.
- `plugin-tests/tests/skills/annotate/` and `plugin-tests/mutants/annotate/`.
- No dependency change. `html.parser` is stdlib, so the shipped tree stays stdlib-only.
- No change to where annotations land: `store.repo_root` resolves from the document path, so a peer repo's file writes to that repo's own `cla.io/annotations/` tree. Confirmed with the user as correct and deliberately unchanged.

### Out of scope, deliberately

- **SUPPORTING an HTML file with relative assets** — a local image, a separate stylesheet. The motivating file is self-contained. A `<base>` tag would fix asset resolution and break the author's own `#fragment` links in the same stroke, so it is a decision of its own rather than a cheap add-on. **Detecting one and warning is IN scope** (design decision 8) — what is excluded is making it render correctly, not telling the reader it will not.
- Extracting HTML into annotate's own shell. Offered, and rejected by the user in favour of preserving the design.
- Rendering an HTML file that is part of an OpenSpec change. `render_change.py` composes Markdown panes; mixing a frame into a tabbed multi-file page is a separate problem.
