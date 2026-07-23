# lockfile — sync-provenance lockfile (full mechanics)

Since `cla-sync-provenance`, a per-repo lockfile at **`.claude/plugins/cla/.cla-sync-lock.json`** records, per synced asset, the common ancestor the next `discover` run needs for a real 3-way reconcile:

```json
{
  ".claude/plugins/cla/skills/codify-learnings/SKILL.md": {
    "last_synced_sha256": "<sha256 of the adapted content actually written to local>",
    "source": "claude-plugins"
  }
}
```

- **Auto-maintained on `apply`** — every `wrote` outcome (in both `worktree` and `pr` mode) read-merge-writes an entry for that asset; non-`wrote` outcomes (`skipped_dirty_worktree`, `skipped_binary`, `failure`) leave their prior entry untouched. You never hand-edit it.
- **`last_synced_sha256` is the sha256 of the WRITTEN adapted content, not the raw source hash.** This is deliberate: the next `discover` hashes what's actually on disk, so a cleanly-synced, untouched file must have `local_sha256 == ancestor` — pinning the raw source hash instead would mislabel every adapted file `local-advanced` the instant it was written.
- **Per-asset `source`, not per-repo** — the mechanism is source-agnostic. Asset X can canonically come from repo A and asset Y from repo B; an improvement made in *any* repo is pullable everywhere by running `update-cla` against that repo for that asset. No canonical hub is hard-coded. That said, a **soft, non-enforced convention**: prefer treating one designated "hub" repo as the canonical source for generic core assets when there's no reason to prefer otherwise — this is guidance for newcomers, not a constraint the tooling checks.
- **Committed, one per destination repo**, at the plugin root (not inside a skill) — a plain JSON file, so multi-branch lock conflicts resolve like any JSON merge conflict (the keyed-by-asset-path shape minimizes the conflict surface to the touched assets).
- **Excluded from the sync scan itself** — it's a dotfile living outside `SCAN_DIRS`, so it never appears in `divergences.json` and is never a sync candidate, doubly (both rules would exclude it independently).
- **First run after adopting the lockfile (or a never-synced asset) has no entry** — that asset classifies via today's 2-way `divergent` fallback until the first `apply` seeds it. Expected and self-healing, not a bug.
- **The ancestor is the ADAPTED (local) content, not the raw source — so a genuinely adapted file carries some label noise by design.** Because `last_synced_sha256` is the written-to-local bytes (see above), a file whose adaptation deliberately diverged from source (rule 3's "re-specialized fork" case) can read `source-advanced`/`both-diverged` on the next run even though nothing further actually changed on either side beyond that original, intentional adaptation — the label is comparing raw source against the adapted ancestor, and those two were never identical to begin with. This is harmless: `apply` writes the SAME way regardless of label (no auto-merge happens off the classification), so treat the status as informational context for Phase 2's judgment call, not as a load-bearing signal.
