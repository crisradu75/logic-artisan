# upstream-proposals — recording fixes that belong in the canonical source

A sync is the one moment when someone is looking at the *same* asset in two repos at
once. That is exactly when it becomes visible that a local file is not merely adapted
but genuinely **better** — it fixes a defect in the portable harness, or covers a case
the source misses. That observation is worth more than the sync itself, and until now
it evaporated when the run ended.

Phase 2.5 captures it: while adapting, when you conclude that a local divergence is a
**generic** improvement, append a proposal to `cla-upstream.md` at the destination repo
root. The canonical source reads those files when it wants to collect carry-backs.

This is the reverse channel. It moves *prose*, never code — nothing here writes to the
source repo, and nothing here is automatic.

## The admission test

One question decides every candidate:

> If the canonical source adopted this change, would **every** repo running the plugin
> be better off?

- **Yes → it belongs here.** A guard hook that no-ops on a platform. A script that
  mishandles a line ending. A launcher whose safety assert can never fire. A skill step
  that is wrong everywhere, not just here.
- **No → it does not.** It is this repo's adaptation, and adaptation is not a defect.

Repo-local content already has homes: each skill's `references/project-context.md`
overlay and the repo's own `cla.io/` state. Neither is synced, so neither needs a
carry-back. Routing an adaptation here produces an item the source can only reject.

## What this file is NOT

**Not an inventory of divergences.** Most `local-advanced` and `both-diverged` assets
differ for entirely legitimate local reasons. Listing them all would bury the handful of
real defects under noise, and a file that is 90% noise stops being read — which costs
more than never having written it. Discovery's own summary already reports the counts;
this file carries only what passed the test above.

**Not a changelog, and not a to-do list for this repo.** Every item is work owed to a
*different* repo. A fix this repo still needs locally is ordinary work — track it
wherever this repo tracks work.

## Never overwrite what a human wrote

`cla-upstream.md` is frequently hand-authored, and those entries are often long-form
analysis worth far more than anything a sync generates. Treat the file as append-only:

- **Read it first.** If it exists, read the whole file before writing.
- **Append** new items at the end of the item list. Never reorder, reword, renumber, or
  delete an existing item — including ones marked as ported.
- **Do not restructure** the file to match the shape below. The shape is for items *you*
  add; a file with its own established conventions keeps them, and your item adopts
  those conventions instead.
- **Absent file** → create it with the header shown below, then add the first item.

Applying an item is the *source* repo's job, and marking one ported is a human's. A sync
run never ticks a box.

## Dedup

Before appending, check whether the divergence is already recorded. The same defect
surfaces on every sync until the source actually fixes it, so an un-deduped file grows a
new copy of the same item each run.

- **Already present and still unfixed** → add nothing. Optionally note the current sync's
  source revision on the existing item so it shows the defect was re-confirmed, not
  merely inherited.
- **Present but the source has since fixed it** → the divergence is gone, so there is
  nothing to append anyway. Leave the item alone; ticking it is a human's call.

## Item shape

Number items sequentially from the highest number already in the file. Keep the prose
tight — the reader is a session in another repo with none of this context.

```markdown
## <N>. <one-line statement of the defect, not of the fix>

**Upstream location:** `<path in the plugin>` · **Status:** unfixed upstream
**Severity:** <why it matters, in a few words>

### What happens

<The defect, concretely. What breaks, under what conditions, and who notices. Name the
platform or configuration if it only bites on some.>

### Why it belongs upstream

<The admission test, answered explicitly. What makes this generic rather than local.>

### The fix

<What this repo did, at the level of detail another session needs to port it — a diff, a
symbol name, or a precise description. Say if the local fix is partial.>
```

State a claim about the source only if you checked the source tree during this run. The
recurring failure in hand-maintained versions of this file is an item asserting "unfixed
upstream" that was fixed months ago, or a ported tick based on reading an adjacent
symbol rather than the one the item names.

## Header for a new file

```markdown
# cla — fixes to port upstream

Defects found in this repo's copy of the plugin that originate in the **synced core**,
not in this repo's overlay — so they exist in every repo running the plugin, and the fix
belongs in the canonical source rather than staying a local divergence.

Repo-local adaptation is out of scope: it lives in each skill's
`references/project-context.md` overlay and in `cla.io/`.

Status legend: `[ ]` not yet upstream · `[x]` ported.
```
