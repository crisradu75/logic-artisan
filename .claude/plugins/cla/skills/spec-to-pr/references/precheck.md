# Working-tree precheck (full procedure)

The Precheck phase's mechanics. `SKILL.md` carries the invariant (run it after permissions, before Propose; an out-of-scope dirty path is an ask, not a halt); this file carries the recipe and the three explicit paths.

`/cla:spec-to-pr` should NOT pick up uncommitted changes that belong to a different scope and sweep them into the feature branch's first commit. **The precheck must also detect in-progress git ops on other branches** — an in-progress cherry-pick/rebase/merge on another branch's HEAD is invisible to `git status --porcelain` on the current branch, so relying on `git status` alone lets it sweep unrelated untracked files into a later commit. See step 1 below. (Dated incident: `cla.io/overlays/spec-to-pr.md`.)

Run after the permissions check, before announcing the mode:

**Step 1 — Check for in-progress git operations and verify branch state:**
```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py
```
Exit 0 → proceed. Exit 2 → in-progress cherry-pick / merge / rebase / revert / bisect detected (the stderr names which one). Resolving it: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/conflict-resolution.md`. Surface to the user via `AskUserQuestion` with three explicit paths: (a) abort the in-progress op (`git cherry-pick --abort` / `git rebase --abort` / etc.) and proceed, (b) halt /cla:spec-to-pr and let the user finish the op manually, (c) inspect first (read `.git/CHERRY_PICK_HEAD` etc.) before deciding. Do NOT proceed until resolved — a stale in-progress op poisons every subsequent `git add` and commit.

**Step 2 — Inspect the working-tree dirty paths:**
```
git status --porcelain
```

Classify every output line by path:
- **In-scope:** anything under `openspec/changes/<change-name>/`, the affected app/package's source under `apps/*/src/` or `packages/*/src/`, or a directly-related repo file the change legitimately touches (e.g. a per-app stylesheet, a smoke-test script, a config file, `docs/` for the change, or a sub-app's own doc file for a sub-app-scoped change — see `cla.io/overlays/spec-to-pr.md` for this repo's worked examples).
- **Out-of-scope:** everything else — typically `.claude/`, root `CLAUDE.md`, root `TODO.md`, files belonging to an unrelated change, etc.

**If every dirty path is in-scope OR the working tree is clean:** proceed silently. (In existing-change mode, the change-directory edits are obviously in-scope; in description / explore-result mode, only a clean tree is expected — non-in-scope dirty paths still trigger the prompt.)

**If any path is out-of-scope:** surface to the user via `AskUserQuestion` with **three explicit paths** (the same shape used by the investigation-first detector):

- **(a) Commit out-of-scope changes to <base-branch> first.** Stage and commit ONLY the out-of-scope paths to <base-branch> with a one-line subject (e.g. `docs: lessons-learned log entries from prior session`), push, then return to clean working tree and proceed with Propose.
- **(b) Include out-of-scope changes in this PR.** Stage them along with the feature work in Ship by adding each out-of-scope path to the `git add` call alongside the in-scope `apps/*/src/`/`packages/*/src/` paths. The orchestrator never runs `git add -A`; out-of-scope paths must be enumerated explicitly. Use when the changes are intentionally part of the same logical unit and the user is consciously overriding the commit-to-base-branch convention.
- **(c) Stash and proceed.** `git stash push --include-untracked -m "spec-to-pr precheck stash for <change-name>"` before Propose; the stash is the user's responsibility to pop later. Use when uncertain — keeps the tree clean for this PR without losing work.

Print the list of out-of-scope paths in the question's `description` field so the user sees exactly what's at stake. Default to (a) when the paths are all under `.claude/` (per the memory rule); default to (a) is also presented as a recommendation in the option label when applicable. Do NOT proceed until the user picks.

This precheck is the only check between Bootstrap permissions and Propose. Skip entirely with `--no-tree-check` (escape hatch — useful when re-running mid-flow after a known intentional dirty state).

