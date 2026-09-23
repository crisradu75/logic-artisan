# One checkout, two writers — the worktree recipe, and the orchestrator vs. its own delegate

Read when running two or more `/cla:spec-to-pr` flows at once in one repo. A single run needs none of the worktree recipe — but it does need the last section, which is about one session sharing a checkout with its own delegate.

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
- **Cleanup:** the worktree persists after the run (the session lives in it). After the PR merges, remove it from the primary clone: `git worktree remove <worktrees-dir>/<change>` (the branch is already deleted by `gh pr merge --delete-branch`). Then confirm the folder is gone, following `${CLAUDE_PLUGIN_ROOT}/skills/multi-pr/references/cleanup.md` step 3. Read `<worktrees-dir>` there in place of `.claude/worktrees`.

## The orchestrator vs. its own live delegate

Everything above separates two *sessions*. A single session has the same problem with itself, and needs no worktree to hit it: while an Implement or fix delegate is working, the orchestrator is sharing that delegate's checkout, and git's HEAD is per-clone.

**While a delegate is live, the orchestrator runs no repository-state command and no test suite in that checkout.** Not `git checkout`, `switch`, `commit`, `push`, `branch`, or `stash`; not the verify/test command; not killing node or other build processes. A `git checkout` mid-suite moves the files under a running test process and manufactures failures — failures that are indistinguishable, from the output alone, from a real regression the delegate just introduced.

**Read a delegate's interference report as "my delegate is live", not as a third party.** A delegate that detects concurrent mutation cannot tell whose it is, so it names an external session by default, and that report is the orchestrator's own commands coming back at it. Treating it as a genuine third party is the expensive branch: one real run spent roughly 40 minutes investigating manufactured test failures as a possible regression before finding its own `git checkout` was the cause. If you need repository state to settle down, wait for the delegate's terminal return — that is what the return is for.

**The agent-side half of this already ships and does not cover the orchestrator.** `references/subagent-brief.md` slot 3 carries the forbidden-verb list and a paste-ready sentence, but a brief binds only the party receiving it. Nothing the orchestrator writes into a brief constrains the orchestrator, which is why this rule lives here instead.

**Why both cases share one file.** Two sessions in one clone and one session with its own delegate are the same invariant — two writers, one checkout — reached by different routes. Splitting one invariant across two documents is how the two halves drift: a later edit tightens the case its author had in mind and leaves the other stating the old rule, with nothing to notice the divergence. They are also not equally likely to be read. The worktree recipe is opened deliberately, when someone knows they are starting a second run; the delegate case is hit by a single run that had no reason to open this file at all, which is why its one load-bearing rule is lifted into `SKILL.md`'s stub as well.

