# bootstrap-and-tracking — Phase 0 precheck + Phase 2 ledger setup (full mechanics)

The Phase 0 and Phase 2 step-by-step procedures. `SKILL.md`'s stubs for these phases carry the load-bearing invariants (resolve any non-zero bootstrap exit before Phase 1; the run-notes ledger is the deterministic identity source); this file carries the recipes.

## Phase 0 — Bootstrap + working-tree precheck

Run the shared bootstrap once before the chain starts — the same `/cla:multi-pr` bootstrap gate, not something `/cla:lite-pr` itself runs:

1. The permissions check from `/cla:spec-to-pr`'s own "Bootstrap permissions" section (compare `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/required-permissions.json` against `.claude/settings.local.json`). Missing patterns → surface them and apply on approval; that's the one bootstrap ask, the same carve-out the siblings make.
2. ```
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py
   ```
   Non-zero → resolve before continuing (in-progress rebase/cherry-pick, or a dirty tree with out-of-scope paths). A dirty tree at chain start poisons every subsequent candidate.

**Start from `<base-branch>`, clean (primary clone).** Check `git rev-parse --abbrev-ref HEAD`. If not on `<base-branch>`, and the current branch carries local commits unrelated to this run, leave it untouched, then sync to `<base-branch>` with the two separate commands the hoisted base-management rule requires (`git checkout <base-branch>` then `git pull` — never `&&`-chained).

Each candidate's `/cla:lite-pr` run must branch off an up-to-date `<base-branch>`. (Per the hoisted rule: `git checkout <base-branch>` is valid here because `multi-lite` runs in the primary clone; if a mid-chain guard block forces a reactive worktree pivot, base off `origin/<base-branch>` via `git worktree add … -b <branch> origin/<base-branch>` instead.)

## Phase 2 — Task tracking + the run-notes ledger

Use `TaskCreate` once to lay down the chain — one task per candidate (`"<id>: lite-pr + merge per policy"`). A multi-candidate unattended run is exactly the "recoverable across sessions / gated by external state" shape where task tracking earns its keep (unlike inside a single `/cla:lite-pr` run, where it's noise). `TaskUpdate` each candidate to `in_progress` when its `/cla:lite-pr` starts and `completed` once step 8 has either merged its PR or left it open.

**Also create a per-run notes file, `cla.io/retro/multi-lite-run-notes-<date>.md`** (same convention as `/cla:multi-pr`'s per-run notes), **unless one already belongs to this doc.** First look for an existing `cla.io/retro/multi-lite-run-notes-*.md` that names the same source doc and whose candidate ids match the ones Phase 1a derived. If one exists, it is this run's ledger whatever date it carries: reuse it, never overwrite it, and keep its ids where Phase 1a's wording differs. A resume that started a fresh file would find no `pr_number` or `head_sha`, and every PR the earlier session opened would be left open as unverifiable. A new file records the source doc's path on its first line. Open a new file with a header line `policy: <merge-each-clean | merge-dependencies-only>` carrying the policy confirmed at Phase 1c. If step 8 later stops merging because the host refused a merge, append `merging stopped: host refused merge of <id>` beneath it. For each candidate record a row with the columns `id | status | branch | pr_number | head_sha | deferred | review | merge_commit` as the chain progresses:

- `branch`, `pr_number`, `head_sha` — filled at step 6, the moment a PR opens. `head_sha` is updated only when step 7 pushes and verifies its own fix, or when step 2 finds that the commits since it touch nothing but these notes. Nothing else updates it.
- `deferred` — the count of Critical/Important findings `/cla:lite-pr` deferred, written at step 6. The findings themselves go verbatim under a `## Deferred findings` section below the table, one subsection per candidate id. Empty means step 6 never recorded them.
- `review` — `clean` or `unresolved`, written at step 7, with the reason beside `unresolved`. Empty means step 7 has not finished for this candidate.
- `merge_commit` — the merge commit's oid, written at step 8c once the merge is confirmed. Step 3 checks a dependency against it.
- `status` — `merged`, `open` (plain or with a reason), `failed` with the failing check or a reason, `failed-review` with a reason, `failed-merge` with a reason, or `blocked-by-upstream-failure`. Notes step 8 records go beside it: the shared-state derivation, `gate skipped: no source-affecting paths`, `behind base: merged tree not tested`, and `base not updated`. Every reason steps 2, 7 and 8 can write is listed in `references/phase4-and-log.md` under "Shipped & left open".

**`<notes-message>`** is `chore: multi-lite run notes for <source-doc-path>`, exactly, the path repo-relative with forward slashes, on every commit that moves this run's notes file: Phase 4's, and the one below that takes it back out. Step 2's head check and the lookup below both key on it.

**Notes an earlier run committed onto its last open PR** (Phase 4) are in the working tree only while that branch is checked out, and Phase 0 has left it. When no notes file for this doc is in the working tree, restore it from the run's own write, never from a branch tip or another doc's commit. After `git fetch --prune origin`, `git log --remotes=origin --format='%H %s' --fixed-strings --grep='<notes-message>'` lists newest first; the write is the first line whose subject is exactly `<notes-message>` and whose `git show --name-status --format= <sha>` prints one line, `A` and the notes path `<notes>`. `git branch -r --list 'origin/*' --contains <sha>` names its branch even with later commits on top. With `origin/<base-branch>` among them, take it as `<branch>` and go straight to the restore. Otherwise, one command at a time: `git checkout <branch>`, `git pull`, `gh pr view <branch> --json state`; only if the pull succeeded, the state is `OPEN` and `git ls-files -- <notes>` prints the path: `git rm --cached -q -- <notes>`, `git commit -m "<notes-message>"`, `git push`, and verify the push. Then `git checkout <base-branch>` and restore: `git show <sha>:<notes> > <notes>`. If `git log --format=%H --diff-filter=AM <sha>..origin/<branch> -- <notes>` prints anything or fails, the notes were edited on the PR after the write: blank every row's `head_sha`, `review` and `merge_commit`, so step 2 reads merged state from GitHub and merges no open PR. Forgery by someone with push access is out of scope beyond this: they can merge anyway.

Step 2's resume check reads `deferred`, `review`, `head_sha` and `status` back. A row missing `deferred` can never resume as clean. This file is committed at the end, onto the chain's last open PR (see `references/phase4-and-log.md`); mid-run it lives in the primary clone's working tree, untracked, and survives a session restart, so a resume reads it back.
