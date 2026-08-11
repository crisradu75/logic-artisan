# bootstrap-and-tracking — Phase 0 precheck + Phase 2 ledger setup (full mechanics)

The Phase 0 and Phase 2 step-by-step procedures. `SKILL.md`'s stubs for these phases carry the load-bearing invariants (resolve any non-zero bootstrap exit before Phase 1; the run-notes ledger is the deterministic identity source); this file carries the recipes.

## Phase 0 — Bootstrap + working-tree precheck

Run the shared bootstrap once before the chain starts — the same `/cla:multi-pr` bootstrap gate, not something `/cla:lite-pr` itself runs:

1. The permissions check from `/cla:spec-to-pr`'s own "Bootstrap permissions" section (compare `spec-to-pr/references/required-permissions.json` against `.claude/settings.local.json`). Missing patterns → surface them and apply on approval; that's the one bootstrap ask, the same carve-out the siblings make.
2. ```
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/scripts/git_state.py
   ```
   Non-zero → resolve before continuing (in-progress rebase/cherry-pick, or a dirty tree with out-of-scope paths). A dirty tree at chain start poisons every subsequent candidate.

**Start from `<base-branch>`, clean (primary clone).** Check `git rev-parse --abbrev-ref HEAD`. If not on `<base-branch>`, and the current branch carries local commits unrelated to this run, leave it untouched, then sync to `<base-branch>` with the two separate commands the hoisted base-management rule requires (`git checkout <base-branch>` then `git pull` — never `&&`-chained).

Each candidate's `/cla:lite-pr` run must branch off an up-to-date `<base-branch>`. (Per the hoisted rule: `git checkout <base-branch>` is valid here because `multi-lite` runs in the primary clone; if a mid-chain guard block forces a reactive worktree pivot, base off `origin/<base-branch>` via `git worktree add … -b <branch> origin/<base-branch>` instead.)

## Phase 2 — Task tracking + the run-notes ledger

Use `TaskCreate` once to lay down the chain — one task per candidate (`"<id>: lite-pr (+ merge if a dependency)"`). A multi-candidate unattended run is exactly the "recoverable across sessions / gated by external state" shape where task tracking earns its keep (unlike inside a single `/cla:lite-pr` run, where it's noise). `TaskUpdate` each candidate to `in_progress` when its `/cla:lite-pr` starts and `completed` when its PR is opened (or, for a dependency, merged).

**Also create a per-run notes file, `cla.io/retro/multi-lite-run-notes-<date>.md`** (same convention as `/cla:multi-pr`'s per-run notes). For each candidate record a row `id | status | branch | pr_number` as the chain progresses (Phase 3 fills `branch`/`pr_number` the moment a PR opens). `multi-lite` cannot predict a candidate's branch name the way `/cla:multi-pr` keys off `/cla:spec-to-pr`'s resolved `<branch>` (the configured prefix plus the change name) — `/cla:lite-pr` delegates branch naming to `commit-push-pr`, which derives it from the change content — so the branch/PR must be captured after the fact and written here, not guessed. This file is committed at the end (see `references/phase4-and-log.md`); mid-run it lives in the primary clone's working tree and survives a session restart, so a resume reads it back.
