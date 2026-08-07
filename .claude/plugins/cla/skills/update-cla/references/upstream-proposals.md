# upstream-proposals — recording fixes that belong in the canonical source

Phase 4 of a sync. A sync is the one moment the same asset is in view in two repos at
once, so it is when a local file can reveal itself as not merely *adapted* but genuinely
**better**. Without this phase that observation dies with the run, and the same defect
gets rediagnosed independently in every repo running the plugin.

Output is a `cla-upstream.md` at the root of the local repo (the `--local` path, else CWD).
The canonical source collects from those files **by hand** — nothing in the plugin reads
them, and no sync can carry one, since the file sits outside `SCAN_DIRS` and `SCAN_FILES`.
This channel moves *prose*, never code.

**Runs after `apply`, never before** — see `references/phases.md` (Phase 4) for why the
ordering is load-bearing and how to commit the file without it riding along in the sync.

## The admission test

> If the canonical source adopted this change, would **every** repo running the plugin be
> better off?

- **Yes → record it.** A guard hook that no-ops on a platform. A script that mishandles a
  line ending. A launcher whose safety assert can never fire. A skill step that is wrong
  everywhere, not just here.
- **No → record nothing, and change nothing.** It is legitimate local adaptation. Leave it
  exactly where it is — in the synced file, kept per non-negotiable rule 1. Do **not**
  relocate it into a `project-context.md` overlay to "tidy" it: overlays are excluded from
  the sync scan, so content moved there drops out of every future 3-way reconcile.

Consider divergences with status `local-advanced`, `both-diverged`, or `divergent`.
(`divergent` is the no-ancestor fallback — it covers every asset in a repo that has never
synced or lost its lockfile, which is exactly where an unshared local fix is most likely.)
`source-advanced` has nothing to propose: local matches the ancestor, so local added
nothing.

A **filtered** run (`/cla:update-cla <src> hooks/`) only ever sees its slice. Say so when
reporting, so "nothing to record" is not mistaken for "the whole tree is clean."

## What this file is NOT

**Not an inventory of divergences.** Most divergences are legitimate local adaptation.
Listing them all buries the few real defects, and a file that is mostly noise stops being
read — which costs more than never having written it. Discovery's summary already reports
the counts.

**Not a to-do list for this repo.** Every item is work owed to a *different* repo.

## Never overwrite what a human wrote

These files are frequently hand-authored, and those entries are often long-form analysis
worth more than anything a sync generates. The file is **append-only**:

- **Read it first**, in full, if it exists.
- **Append** new items after the last existing item. Never reorder, reword, renumber, or
  delete an existing item — including its status line, and including items already ported.
- **Do not restructure** the file to match the shape below. A file with its own
  established conventions keeps them, and your item adopts *those* conventions — including
  its numbering scheme, or its absence.
- **Absent file** → create it with the header below, then add the first item.

Marking an item ported is a human's job. A sync run never does it.

## Dedup

The same defect resurfaces on every sync until source actually fixes it, so an un-deduped
file grows a fresh copy each run. Before appending, check whether the divergence is
already recorded — **if it is, append nothing and move on.**

## What this flow will not do

Say these plainly rather than letting a reader assume otherwise:

- **Nothing retires a stale item.** Once source fixes a defect, the two sides match, so
  discovery skips the asset silently and Phase 4 never sees it again. An item claiming
  "unfixed upstream" can therefore outlive its fix indefinitely. Pruning is a human's job.
- **A local-only asset cannot be proposed.** A file that exists only in this repo never
  reaches Phase 2 — the local walk yields it as a `deleted-in-source` record, if anything.
  A whole new hook this repo wrote is often the *best* carry-back, and this flow is blind
  to it. Record it by hand.

## Item shape

Number sequentially from the highest number already in the file. Keep it tight — the
reader is a session in another repo with none of this context.

```markdown
## <N>. <one line: what is wrong, or what is missing>

**Upstream location:** `<path in the plugin, or "none — new file">` · **Status:** unfixed upstream
**Severity:** <why it matters, in a few words>

### What happens

<Concretely: what breaks or is missing, under what conditions, and who notices. Name the
platform or configuration if it only bites on some. For a gap rather than a defect, say
what the source does not cover and what that costs.>

### Why it belongs upstream

<The admission test, answered explicitly. What makes this generic rather than local.>

### The fix

<What this repo did, in enough detail for another session to port it — a diff, a symbol
name, or a precise description. Say so if the local fix is partial.>
```

State a claim about source only if you checked the source tree during **this** run. The
recurring failure in hand-maintained versions of this file is an item asserting "unfixed
upstream" that was fixed long ago.

## Header for a new file

```markdown
# cla — fixes to port upstream

Defects and gaps found in this repo's copy of the plugin that originate in the **synced
core**, not in this repo's overlay — so they exist in every repo running the plugin, and
the fix belongs in the canonical source rather than staying a local divergence.

Repo-local adaptation is out of scope: it stays in the synced file where it already lives,
or in this repo's own `cla.io/` state.

Items are appended by `/cla:update-cla` (Phase 4) and by hand. Nothing removes them
automatically — a fixed item stays until a human prunes it.
```
