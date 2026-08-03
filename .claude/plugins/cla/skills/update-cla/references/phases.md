# phases — full Phase 1/2/3 mechanics

The step-by-step procedure, exact script invocations, and state-file JSON shapes behind `SKILL.md`'s Workflow spine (Discover → Adapt → Apply). `SKILL.md` carries the load-bearing invariants (one rewrite per file, per-status handling, never-auto-delete); this file carries the recipes.

## Phase 1 — Discover (script call, no reasoning)

```
python3 .claude/plugins/cla/skills/update-cla/scripts/orchestrate.py discover \
    <source-repo> [<asset-path>] [--local <path>]
```

The script:
1. Resolves the source-repo positional to an absolute path (config short-name OR direct path).
2. Reads `.claude/plugins/cla/.cla-sync-lock.json` from the local repo (missing/unreadable → empty ancestor map, no crash) — this per-repo sync-provenance lockfile records, per asset, the sha256 of the content last written to local by a previous `apply`, supplying the common ancestor a real 3-way reconcile needs (`cla-sync-provenance`).
3. Walks the source's `.claude/plugins/cla/` tree (filtered by the optional asset-path positional).
4. For each file, compares source hash to local hash:
   - **identical** — skipped silently.
   - **new** — local does NOT have this file.
   - Otherwise (content differs), classifies against the lockfile ancestor:
     - **no lock entry for this asset** — `divergent` (today's 2-way fallback; the tool has no ancestor, so it cannot say more).
     - **`local == ancestor` and `source != ancestor`** — `source-advanced` (local untouched since the last sync; this is also the freshly-synced-untouched case — safe to re-adopt source).
     - **`source == ancestor` and `local != ancestor`** — `local-advanced` (source hasn't moved since the last sync; local carries a genuine refinement — source would be a regression).
     - **both differ from the ancestor and from each other** — `both-diverged` (a genuine conflict; force careful manual reconcile).
5. After the source walk, additionally walks the **local** tree (same `SCAN_DIRS`/`_is_excluded`/`_matches_filter` filters as the source walk) to find in-scope local assets the source walk did not yield. A local asset that IS in the lockfile but absent from source surfaces as a `deleted-in-source` deletion record (for manual review only — `apply.py` never auto-deletes); a local asset NOT in the lockfile is left alone (overlay or genuinely local content). A renamed source file naturally surfaces as this deletion (old path) plus a `new` record (new path) — no special rename code.
6. Writes `temp/sync-state/<RUN-ID>/divergences.json` under the local repo and prints a summary (including the deletion count, if any).

State-file shape:
```json
{
  "run_id": "20260525-143012",
  "source": {"name": "claude-plugins", "path": "/abs/path"},
  "local": {"path": "/abs/path"},
  "filter": null,
  "files": [
    {
      "asset_path": ".claude/plugins/cla/skills/codify-learnings/SKILL.md",
      "status": "source-advanced",
      "source_content": "...",
      "source_sha256": "...",
      "local_content": "...",
      "local_sha256": "..."
    },
    {
      "asset_path": ".claude/plugins/cla/skills/new-thing.md",
      "status": "new",
      "source_content": "...",
      "source_sha256": "...",
      "local_content": null,
      "local_sha256": null
    }
  ],
  "skipped": [
    {"asset_path": ".claude/plugins/cla/skills/foo/icon.png", "reason": "binary", "detail": "binary asset (size 4096)"}
  ],
  "deletions": [
    {
      "asset_path": ".claude/plugins/cla/skills/retired-thing/SKILL.md",
      "status": "deleted-in-source",
      "local_sha256": "...",
      "last_synced_sha256": "...",
      "source": "claude-plugins"
    }
  ]
}
```

`files[].status` is one of `divergent` | `new` | `source-advanced` | `local-advanced` | `both-diverged`. Binary files (non-UTF-8) appear in `skipped`, never in `files` — their content is never round-tripped through the LLM. Read-error files go in `skipped` too with `reason: source_unreadable` or `local_unreadable`. `deletions` is additive — a separate array from `files`, never auto-applied.

**Display the discovery summary verbatim.** If `total = 0` and there are no deletions, report and exit.

## Phase 2 — Adapt (you reason; one rewrite per file)

For each file in `divergences.json`:

1. **Read inputs:**
   - Source content (`source_content`).
   - Local existing version (`local_content` — `null` for `new` files).
   - Local repo context: local `CLAUDE.md` (read top-level + any plugin-local one that matches the asset's path), local file listing for the affected directory, local `plugin.json` if relevant.
   - **The file's `status`** — since `cla-sync-provenance`, this now carries the 3-way classification, not just `divergent`/`new`. Act on it:
     - `divergent` — no lockfile ancestor available (never synced, or a stale/missing lock entry); reconcile by judgment alone, same as before this change.
     - `source-advanced` — local is untouched since the last sync; adopt source freely (this is also the common freshly-synced-and-untouched case — source moved on since, or the sync just happened and diverges from raw source by construction).
     - `local-advanced` — source hasn't moved since the last sync, but local has; source would be a **regression** — keep local, don't overwrite it with the (older, in effect) source content unless source's newer diff still carries something genuinely new to cherry-pick.
     - `both-diverged` — both sides changed since the last sync; this is the real conflict case — careful manual reconcile per the non-negotiable rules (rule 1 especially), not a mechanical pick of either side.

2. **Produce adapted content** following `references/adaptation_prompt.md` and the non-negotiable rules at the top of `SKILL.md`. The most common adaptation failure is silently overwriting local content the source doesn't have — especially when local is a re-specialized fork (rule 3) and the source diff is mostly convention-reversing regression — re-read those rules before writing each file.

   For a `new` **skill**, adapt its `SKILL.md` (plus any `references/`/`scripts/`/`tests/`) and route it through `adaptations.json` like every other file — do NOT `Write` it directly, so Phase 3's `apply` script performs the git-safety checks (and, in `--mode pr`, the commit/push); a direct `Write` could leave the file uncommitted in `--mode pr`. Note: cla is **skills-only** — a new skill needs no companion command-wrapper (the old two-part command+skill convention was retired in the extract-cla-plugin migration).

3. **Print a one-line `[i/N] <asset> — <summary>`** to the user so they see what changed (e.g., `[2/5] codify-learnings/SKILL.md — ported source's new "Phase 3" section, kept local's "Linear ticket" reference`).

4. **Write `adaptations.json`** to the same state directory:
   ```json
   {
     "run_id": "20260525-143012",
     "adaptations": [
       {
         "asset_path": ".claude/plugins/cla/skills/codify-learnings/SKILL.md",
         "adapted_content": "<full final file content>",
         "change_summary": "Ported source's Phase 3; kept local Linear-ticket reference."
       }
     ]
   }
   ```

5. **Review `deletions` (if any).** For each `deleted-in-source` record, decide by hand whether the local asset should be removed, kept, or is a rename (paired with a `new` record for the file it moved to — recreate the reference under the new path if so). **Never auto-delete** — `apply.py` has no delete path; if removal is the right call, `Write`/delete the file yourself as a separate, deliberate step outside this skill's apply flow, and say so to the user.

Then trigger Phase 3.

## Phase 3 — Apply (script call, no reasoning)

```
python3 .claude/plugins/cla/skills/update-cla/scripts/orchestrate.py apply \
    --run <RUN-ID> [--mode worktree|pr] [--local <path>]
```

Two modes, selected by `--mode`:

- **`worktree`** (default) — write adapted files directly into the local working tree. Per-file safety: refuses to overwrite a file that has un-committed local edits (the script checks `git status --porcelain -- <asset_path>` per file; if non-empty, that file is skipped with status `skipped_dirty_worktree`). If `git status` itself fails (git missing, not a git repo), the file is **not** overwritten — it goes to `failure` instead. Other files in the same run proceed.
- **`pr`** — fail if the working tree is dirty (whole-tree check). Create branch `sync/from-<source-name>-<YYYYMMDD-HHMMSS>`. Write adapted files. Commit via `git commit -F <abs-path>`. Push and open PR via `gh pr create --body-file <abs-path>` (the PR body is rendered by the script from `references/pr_template.md`). Any mid-flow failure (commit, push, gh) rolls back via `git checkout <default-branch>` so the user is not left stranded on the sync branch. The PR is opened for review only — this mode never runs `gh pr merge`; merging is always a manual, separate step by the user.

Either mode refuses to write a file whose `adapted_content` looks like the binary-placeholder string (`<binary file, N bytes>`); such a file is reported as `skipped_binary`. This is a defense-in-depth — discover already refuses to surface binary content to the LLM, but if a manually edited adaptations.json contained a placeholder, apply would still refuse.

Every `adapted_content` is also normalized (CRLF/CR → LF) before being written — this is where a prior sync's silent corruption actually happened (every `\r\n` became `\n\n`, doubling blank lines across 19 of 37 files with byte counts unchanged, so nothing caught it). After normalization, apply refuses to write content whose newline count is still ~2x its non-empty line count — the fingerprint of that exact corruption, and never a legitimate adaptation. Such a file is reported as `skipped_malformed` and left on disk as-is; its prior lock entry (if any) is unchanged, same as `skipped_binary`.

**Every `wrote` outcome also updates `.claude/plugins/cla/.cla-sync-lock.json`** (`cla-sync-provenance`) — see `references/lockfile.md`. This happens inside `apply.py` itself (both modes), not as a separate step: it's the only place with the exact adapted bytes just written, and (in `pr` mode) the only place that can get the lockfile staged/committed/pushed in the same PR. The lock write is best-effort — a failure prints to stderr but never fails the run, commit, or PR.

**Display the apply summary verbatim.** Per-file write failures isolate — a single bad-permission or read-only path fails just that file and the rest proceed; the final summary lists per-file outcomes.
