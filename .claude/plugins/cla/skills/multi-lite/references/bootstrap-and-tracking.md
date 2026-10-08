# bootstrap-and-tracking — Phase 0 precheck + Phase 2 ledger setup (full mechanics)

The Phase 0 and Phase 2 step-by-step procedures. `SKILL.md`'s stubs for these phases carry the load-bearing invariants (resolve any non-zero bootstrap exit before Phase 1; the run-notes ledger is the deterministic identity source); this file carries the recipes.

## Phase 0 — Bootstrap + working-tree precheck

Run the shared bootstrap once before the chain starts (`/cla:lite-pr` does not run it): `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/chain-merge.md`, "Bootstrap" — the permissions check, `git_state.py`, and a clean, current `<base-branch>` in the primary clone. This skill's run-notes check:

- From the repo root, `git check-ignore -q --no-index cla.io/retro/multi-lite-run-notes-x.md`. Non-zero → stop: "run /cla:cla-setup first (run notes would be visible to git)". Any ignore source counts here: this run only needs git to ignore the notes on this machine, while `/cla:cla-setup` checks for the repo's own `.gitignore` line.

Each candidate's `/cla:lite-pr` run must branch off an up-to-date `<base-branch>`.

## Phase 2 — Task tracking + the run-notes ledger

Use `TaskCreate` once to lay down the chain — one task per candidate (`"<id>: lite-pr + merge per policy"`). A multi-candidate unattended run is exactly the "recoverable across sessions / gated by external state" shape where task tracking earns its keep (unlike inside a single `/cla:lite-pr` run, where it's noise). `TaskUpdate` each candidate to `in_progress` when its `/cla:lite-pr` starts and `completed` once step 8 has either merged its PR or left it open.

**Also create a per-run notes file, `cla.io/retro/multi-lite-run-notes-<date>.md`** (same convention as `/cla:multi-pr`'s per-run notes), **unless one already belongs to this doc.** First look for an existing `cla.io/retro/multi-lite-run-notes-*.md` that names the same source doc and whose candidate ids match the ones Phase 1a derived. If one exists, it is this run's ledger whatever date it carries: reuse it, never overwrite it, and keep its ids where Phase 1a's wording differs. A resume that started a fresh file would find no `pr_number` or `head_sha`, and every PR the earlier session opened would be left open as unverifiable. A new file records the source doc's path on its first line. Open a new file with a header line `policy: <merge-each-clean | merge-dependencies-only>` carrying the policy confirmed at Phase 1c. If step 8 later stops merging because the host refused a merge, append `merging stopped: host refused merge of <id>` beneath it. For each candidate record a row with the columns `id | status | branch | pr_number | head_sha | deferred | review | merge_commit` as the chain progresses:

- `branch`, `pr_number`, `head_sha` — filled at step 6, the moment a PR opens. `head_sha` is updated only when step 7 pushes and verifies its own fix. Nothing else updates it.
- `deferred` — the count of Critical/Important findings `/cla:lite-pr` deferred, written at step 6. The findings themselves go verbatim under a `## Deferred findings` section below the table, one subsection per candidate id. Empty means step 6 never recorded them.
- `review` — `clean` or `unresolved`, written at step 7, with the reason beside `unresolved`. Empty means step 7 has not finished for this candidate.
- `merge_commit` — the merge commit's oid, written at step 8b once the merge is confirmed. Step 3 checks a dependency against it.
- `status` — `merged`, `open` (plain or with a reason), `failed` with the failing check or a reason, `failed-review` with a reason, `failed-merge` with a reason, or `blocked-by-upstream-failure`. Notes step 8 records go beside it: the shared-state derivation, `gate skipped: no source-affecting paths`, `behind base: merged tree not tested`, and `base not updated`. Every reason steps 2, 7 and 8 can write is listed in `references/phase4-and-log.md` under "Shipped & left open".

Step 2's resume check reads `deferred`, `review`, `head_sha` and `status` back. A row missing `deferred` can never resume as clean. The file is local working state: `.gitignore` ignores `cla.io/retro/*-run-notes-*.md` (`/cla:cla-setup` adds the line), nothing in this run adds or commits it, and it survives a session restart in the primary clone's working tree, so a resume on this machine reads it back. A resume without it (another machine, or the file deleted) falls back to GitHub state, step 2's title match.
