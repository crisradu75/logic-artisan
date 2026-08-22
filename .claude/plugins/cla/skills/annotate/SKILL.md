---
name: annotate
description: "Put a Markdown or plain-text document — or a whole OpenSpec change — in front of the user to be read and marked up. Renders it as a self-contained HTML page, opens it in a chrome-less browser window, and serves it locally so any passage can be selected and commented on, each comment paired with the passage it is about and appended to a file this session reads back and works through. A change opens as one page with its proposal, design, tasks and spec deltas in tabs, the passages that answer each other shown side by side, and a derived coverage view of what nothing implements. Never writes to what is being annotated. Triggers on /cla:annotate or natural language like 'let me annotate this', 'open this doc so I can comment on it', 'let me review change X as a block', 'I want to mark up the spec', 'read my annotations', 'work through my comments on X'. Not for reviewing a change against this repo's standards; that is review-change."
argument-hint: "<path to a .md or .txt file, or an OpenSpec change id>"
allowed-tools: Bash, Read, Grep, Glob, Edit
---

# annotate

Put a document in front of the user to be read *and written on*, and bring what
they wrote back into the session.

**The user's attention is the scarce input this skill spends.** Everything below
exists to spend it on the document rather than on the tool: the page opens
without browser furniture, the annotations save themselves, and the report is
four lines.

**This skill runs its scripts and interprets what comes back. It does not
reimplement them.** [scripts/render_doc.py](scripts/render_doc.py) builds a
document's page, [scripts/render_change.py](scripts/render_change.py) builds a
whole change's, and [scripts/annotate_server.py](scripts/annotate_server.py)
serves either and records annotations. **The corpus's format — the kinds of line and the merge
rule — is [scripts/annotations_store.py](scripts/annotations_store.py) and is
read there, never restated.**

**The document is never written to.** Not by the render, not by the server, not
by this skill while annotations are being collected. Annotating is a *read* of
the source; a tool that edited the thing under review would move the text out
from under the reader's next selection. Editing happens later, deliberately, in
§4 — and only once the user has seen what is being changed.

## Where things go, and why they go there

- **Annotations** land in `cla.io/annotations/<the document's path>.jsonl` —
  committed. An annotation on its own calibrates nothing: *"too vague"* teaches
  the next document only if the file also holds what was vague and what replaced
  it. The document keeps the winning wording and git keeps the diff without the
  reason, so the pair is recorded here or nowhere.
- **The page** goes to a temp directory, never into the repo. It is a working
  view of a document rather than something the repo keeps, and writing it into
  the tree would need a `.gitignore` entry in every consuming repo.

---

## 1. Establish the document

Take a path if one is given. Otherwise infer it from the conversation, say so in
one line, and proceed:

> Opening **docs/spec.md** — the document we have been discussing. Correct me if
> you meant another.

**One precondition, and it reports rather than gates:** the file has to exist and
be UTF-8. `.md` renders as Markdown; anything else renders as plain text, with no
markup interpretation at all. Both scripts say so themselves rather than failing
oddly, so pass the path through and read what comes back.

### Or a whole OpenSpec change

A change id, a change directory, or "review change X as a block" means the whole
change rather than one file. **Take it as one target**: one page, one corpus, one
pass. Its files are only worth reading together because a claim in one is
answered in another, and splitting them into four sessions is what this exists to
stop.

An archived change is annotatable too, and is found by its bare id even though
the directory carries a date prefix. Both scripts take the id, the directory, or
a path — pass what the user said and read what comes back.

## 2. Render, then serve

```bash
# one document
python3 "$CLAUDE_PLUGIN_ROOT/skills/annotate/scripts/render_doc.py" <path>
python3 "$CLAUDE_PLUGIN_ROOT/skills/annotate/scripts/annotate_server.py" <path>

# a whole change — the server takes the same target and works out which it is
python3 "$CLAUDE_PLUGIN_ROOT/skills/annotate/scripts/render_change.py" <change>
python3 "$CLAUDE_PLUGIN_ROOT/skills/annotate/scripts/annotate_server.py" <change>
```

**Always re-render before serving.** The page is a view of the document, so a
stale page is worse than no page: it shows prose the document no longer contains,
and an annotation written against it anchors to text that is already gone.
Rendering is cheap.

**Run the server in the background**, or the turn blocks on a process that does
not exit. It opens the page itself on start; pass `--no-open` only when a window
is already showing it.

**Read the port back from the server's own output rather than assuming it.**
`8741` is the default and it is often already taken by an earlier run — the
server reports the collision and suggests the next port instead of failing
silently. If a server for this document is already up, say so and reuse it rather
than starting a second one.

### When annotations already exist, say what state they are in

**There is no fresh-start option.** The render reports what it found: how many are
open, how many resolved, which open ones no longer find their text, and any line
it could not read at all. **Report the lost ones by name** — they are the only
ones the user cannot see in place on the page.

## 3. Then stop

**Say nothing about what the page can do.** No note that selecting text opens a
comment box, no tour of the drawer, no list of the keyboard shortcuts. Explaining
a page's buttons back to the person about to use it is noise sitting between them
and the document.

The whole report is four lines: what was built (blocks and words), the URL, where
annotations land, and how to stop the server. **Then stop talking and let them
read.**

An affordance that genuinely cannot be discovered belongs on the page, in
`render_doc.py`, not in the reply.

## 4. Reading the annotations back, and acting on them

Annotations land in `cla.io/annotations/<path>.jsonl`. **Read it with `cat`.**

Each record carries `sec`, `blk`, `line`, `off`, the selected `text` verbatim,
sixty characters `before` and `after`, and the `note`.

**Two fields do the locating, and they fail differently.** `line` is the source
line the passage came from — use it first, because it points into the *file*,
which is where an edit has to land. `text` is what was on **screen**, so inline
markers are absent from it: a passage the file spells `the **fact/procedure**
split` is recorded as `the fact/procedure split`. Search the source for a
distinctive substring rather than for the whole recorded string.

**On a change, every record also carries `file`** — which of the change's files
the passage came from. Group by it before working through them: an objection to
the proposal and one to a task are different kinds of work.

**A lost anchor is a finding, not a fault.** It means the text an annotation was
written against has changed since. Say which are in that state before working
through them, because their notes may already be answered — and read those first.

### The coverage view is a reading aid, never a verdict

The change page derives a coverage view — which promises a task implements, and
which nothing does. **Report it as what it is: what the detector found.** Four
groups, and only the first is a finding:

- **Uncovered** — the bullet names a file or an identifier and no task names it
  back. Worth raising.
- **Not checkable** — the bullet names neither, so there was nothing to match on.
  **51% of proposal bullets land here** — design and product bullets are prose,
  and prose is not a link. Never present these as gaps.
- **Covered** — a task names the same file, or cites the bullet outright (22%).
- **Not done** — a task whose box is unticked. Its own group, never added to
  Uncovered: an unstarted change has every task open, and reporting that as
  "18 uncovered" is the overclaim the whole tab exists to prevent.

Those percentages come from `scripts/sweep_changes.py` over 355 real changes.
**In a repo whose proposals are written differently the split will differ** — run
that command before relying on the tab, and say what it reported.

**A page reporting `Nothing to check` means no `## What Changes` bullets were
parsed**, not that the change is clean. Say which it is.

**Never restate a coverage row as a defect in the change.** Say "no task names
this bullet's file", which is what was measured, rather than "this is not
implemented", which was not. The page states the same distinction; the reply must
not quietly upgrade it.

**Group them by section and by kind** — a factual challenge, a wording objection,
a missing point — rather than walking the file in timestamp order.

### Closing the loop: record what answered each one

When an annotation has been acted on, append a resolution naming both halves:

```bash
python3 - <<'EOF'
import sys; sys.path.insert(0, "<plugin>/skills/annotate/scripts")
import annotations_store as store
store.append(store.path_for("<document path>"),
             {"id": "<the annotation's id>", "resolved": True,
              "was": "<the passage objected to>", "now": "<what replaced it>"})
EOF
```

**Write the pair only from an edit that actually happened**, and only after the
user has seen it. A wrong pair is worse than a missing one: it enters the file as
evidence and teaches the next pass a lesson the user never gave. If nothing
replaced the passage — it was cut — record the resolution without `now` rather
than inventing one.

A resolved annotation leaves the page and stays in the file. **The count stays
too**, so a page showing none is never mistaken for a file holding none.

## 5. Stopping

The server holds the port until it is stopped. **Say how**, and stop it when the
user says they are done rather than leaving it running into the next session.

**A restart closes the window they are reading in. Say so before doing it.** The
page is a file on disk and survives; the window does not, and a reader loses
their place. Use the page's own rebuild button instead, which re-renders in place
and keeps the window.

## What this skill must not do

- **Never let a link be a guess.** A claim binds to the block holding its text
  only when exactly one block holds it; a coverage row that cannot be placed
  renders as plain text rather than as a link. A link that scrolls somewhere
  arbitrary is worse than no link, because it is believed.
- **Never write to the document being annotated** — not to reformat it, not to
  fix a typo an annotation points at, not "while we are in there". While a page
  is open the file is the reader's fixed reference; changing it moves the text
  out from under the next selection and silently orphans anchors written minutes
  earlier. Edits happen in §4, after the reading pass, and are named before they
  are made. `render_doc.py` opens the document read-only and
  `annotate_server.py` never opens it for writing at all; **that is the
  guarantee, and it is pinned by a test that hashes the file across a full
  annotate-and-rebuild cycle** — not a habit to be re-argued per change.
- **Never rewrite the page by hand.** A defect in the rendering is a defect in
  `render_doc.py`, and fixing it there is what makes the next document right too.
  The same holds for the server.
- **Never bind the server to anything but `127.0.0.1`.** It has no authentication
  because it does not need any, and that stays true only while it is local.
- **Never commit a rendered page.** It is working state and lives in a temp
  directory for that reason. **The annotations file is the opposite and is
  committed** — it is the record of what was objected to and what satisfied it,
  which is the material any later pass has to read.
- **Never delete, archive or rewrite an annotations file.** Retraction is a
  tombstone and resolution is an added line; the raw file keeps everything. A
  pass that "starts clean" destroys the only copy of the evidence. This is also
  why the file only ever grows: a delete that rewrote it would put the corpus one
  interrupted write away from gone.
- **Never invent a resolution to tidy the list.** An annotation with nothing
  recorded against it is open, and open is the honest state.
- **Open every file with an explicit encoding.** Python's default is the locale
  codepage, so on Windows a UTF-8 document decodes as cp1252 and every non-ASCII
  character arrives mangled — silently, while POSIX is fine throughout, which is
  precisely what makes it dangerous in a repo with no CI.
