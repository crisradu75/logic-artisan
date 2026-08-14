# Concurrent runs — worktree per session (full recipe)

Read when running two or more `/cla:spec-to-pr` flows at once in one repo. A single run needs none of this.

A single `/cla:spec-to-pr` run needs no special setup — it creates `<branch>` in place and nothing arbitrates two sessions in one clone — the hook that used to is gone, so the discipline below is the whole protection.

To run **two or more `/cla:spec-to-pr` flows at once** in the same repo, give each session its own `git worktree` (own directory + own HEAD; the primary clone stays on `<base-branch>`). This is required because a run's file edits (Review/Implement/Revise) go to the *session's* working directory via Edit/Write — you cannot edit in one clone and commit from another, so the session itself must live in the worktree (`git -C <worktree>` does NOT solve this). See `cla.io/project-facts.md` ("Worktree convention") for this repo's worktree-directory convention (run `/cla:sync-context` to populate it; falls back to `cla.io/overlays/spec-to-pr.md` if absent). Per-session setup, from the primary clone:

```
git fetch origin <base-branch>
git worktree add <worktrees-dir>/<change> -b <branch> origin/<base-branch>
# then launch Claude in <worktrees-dir>/<change> and run: /cla:spec-to-pr <change>
```

**Branch off `origin/<base-branch>` explicitly, never bare `git worktree add ... -b <branch>`.** Omitting the base branches off whatever the primary clone's *local* `<base-branch>` ref happens to point to, which drifts stale the moment any other change in a chain squash-merges (squash rewrites history, so a local `<base-branch>` that hasn't been fetched/pulled since diverges from `origin/<base-branch>` even with zero local commits of its own). A branch cut from that stale base produces a PR `gh` reports as not-cleanly-mergeable — recoverable (a cherry-pick-onto-a-fresh-branch-plus-force-push repair; see `cla.io/overlays/spec-to-pr.md` for a real recovery precedent), but avoidable for a one-line fix. `git fetch origin <base-branch>` first makes `origin/<base-branch>` current without touching the primary clone's checked-out branch, so this is safe even while another session holds the primary clone.

- The worktree is created **on `<branch>`**, so Ship's branch preflight takes the "already on `<branch>`" path (skips collision-check + checkout) — see the Ship stub's branch-preflight invariant (full recipe in `references/ship.md`).
- **existing-change mode:** the change dir must already be committed (so `git worktree add` from `<base-branch>` includes it). **description / explore-result mode:** the artifacts are created inside the worktree during Propose — fine.
- The two runs are fully isolated: different worktrees, different HEADs, different change dirs. Shared-file merge conflicts are limited to append-only `cla.io/retro/spec-to-pr-runs.jsonl` and `TODO.md` (trivial "keep both lines" resolutions if both PRs touch them).
- **Cleanup:** the worktree persists after the run (the session lives in it). After the PR merges, remove it from the primary clone: `git worktree remove <worktrees-dir>/<change>` (the branch is already deleted by `gh pr merge --delete-branch`).

