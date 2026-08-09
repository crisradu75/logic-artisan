# lockfile — sync-provenance lockfile (full mechanics)

Since `cla-sync-provenance`, a per-repo lockfile at **`.claude/plugins/cla/.cla-sync-lock.json`** records, per synced asset, the common ancestor the next `discover` run needs for a real 3-way reconcile:

```json
{
  ".claude/plugins/cla/skills/codify-learnings/SKILL.md": {
    "last_synced_sha256": "<sha256 of the adapted content actually written to local>",
    "source_sha256": "<sha256 of the RAW SOURCE those bytes were adapted from>",
    "source": "claude-plugins"
  }
}
```

- **Auto-maintained on `apply`** — every `wrote` outcome (in both `worktree` and `pr` mode) read-merge-writes an entry for that asset; non-`wrote` outcomes (`skipped_dirty_worktree`, `skipped_binary`, `failure`) leave their prior entry untouched — except `skipped_kept_local`, which updates its entry deliberately (see below). You never hand-edit it.
- **`last_synced_sha256` is the sha256 of the WRITTEN adapted content, not the raw source hash.** This is deliberate: the next `discover` hashes what's actually on disk, so a cleanly-synced, untouched file must have `local_sha256 == ancestor` — pinning the raw source hash *instead* would mislabel every adapted file `local-advanced` the instant it was written. Which is why both are recorded, not one in place of the other.
- **Per-asset `source`, not per-repo** — the mechanism is source-agnostic. Asset X can canonically come from repo A and asset Y from repo B; an improvement made in *any* repo is pullable everywhere by running `update-cla` against that repo for that asset. No canonical hub is hard-coded. That said, a **soft, non-enforced convention**: prefer treating one designated "hub" repo as the canonical source for generic core assets when there's no reason to prefer otherwise — this is guidance for newcomers, not a constraint the tooling checks.
- **Committed, one per destination repo**, at the plugin root (not inside a skill) — a plain JSON file, so multi-branch lock conflicts resolve like any JSON merge conflict (the keyed-by-asset-path shape minimizes the conflict surface to the touched assets).
- **Excluded from the sync scan itself** — it's a dotfile living outside `SCAN_DIRS`, so it never appears in `divergences.json` and is never a sync candidate, doubly (both rules would exclude it independently).
- **First run after adopting the lockfile (or a never-synced asset) has no entry** — that asset classifies via today's 2-way `divergent` fallback until the first `apply` seeds it. Expected and self-healing, not a bug.
- **TWO ancestors are recorded, and the pair is what makes the label mean anything.** `last_synced_sha256` is the adapted bytes written to local; `source_sha256` is the raw source they were adapted FROM. Each side is then compared against its own baseline (`local != last_synced` = local moved; `source != source_sha256` = source moved), which is what the four labels report.

  With only the first hash — the original design — both sides shared one baseline, and for any file the adaptation changed, `source_sha256 != ancestor` held permanently. `local-advanced` was therefore **unreachable** for exactly the files where divergence was deliberate, and `keep_local`, the escape hatch built to protect them, hung off a label they could never receive. Worse, a fix introduced DURING the adapt phase lands inside the ancestor bytes, so the next run read `local == ancestor, source != ancestor` and reported `source-advanced` — which `phases.md` defines as "adopt source freely". Two consuming repos reported the resulting silent revert independently.

  So the status **is** load-bearing for Phase 2's choice, and this bullet used to say the opposite ("informational context … not a load-bearing signal"). That was an accurate description of a label that could not be trusted, not a design; the fix makes `phases.md`'s intent true rather than aspirational. `apply` still writes the same way regardless of label — the classification guides the human/LLM decision, it does not auto-merge.

- **A lockfile predating `source_sha256` degrades precisely, not approximately.** A missing (or non-string) value defaults to `last_synced_sha256`, which collapses the four-way table back to the exact three labels the old code produced, and makes `adapted` structurally impossible for such an entry. Entries self-heal on the first `apply` that writes or keeps that file. Mapping the missing field to `both-diverged` instead would have mislabeled every legacy entry at once, on the first run after upgrade.

- **A `keep_local` outcome now DOES update its entry** (this is the one exception to the "only `wrote` outcomes touch the lock" rule above). It records `keep_local: true`, re-hashes `last_synced_sha256` from the file on disk, and advances `source_sha256` to the source the decision was made against. Without the advance the next run re-labels the file and asks again; without the marker, the reasoning dies with the session. `discover` surfaces it as `kept_local_previously` on the file record.
