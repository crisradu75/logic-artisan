# Working-tree precheck

Run after the permissions check, before announcing the mode, so `/cla:spec-to-pr` never sweeps another scope's uncommitted work into the feature branch's first commit. Skip it entirely with `--no-tree-check` (for a re-run over a known, intentional dirty state).

**Step 1 — in-progress git operations and branch state:**
```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py
```
Exit 0 → proceed. Exit 2 → an in-progress cherry-pick / merge / rebase / revert / bisect, named on stderr; `git status --porcelain` cannot see one on another branch, and it poisons every later `git add` and commit. Resolving it: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/conflict-resolution.md`. Ask via `AskUserQuestion` with three paths: (a) abort the op (`git cherry-pick --abort` / `git rebase --abort` / …) and proceed, (b) halt `/cla:spec-to-pr` so the user finishes it, (c) inspect first (`.git/CHERRY_PICK_HEAD` etc.). Do NOT proceed until resolved.

**Step 2 — classify every dirty path:**
```
git status --porcelain
```
- **In-scope:** anything under `openspec/changes/<change-name>/`, the source directories the change affects (e.g. `apps/*/src/`, `packages/*/src/`), or a directly related file it legitimately touches — a stylesheet, a smoke-test script, a config file, its `docs/`, a sub-app's own doc file (this repo's worked examples: `cla.io/overlays/spec-to-pr.md`).
- **Out-of-scope:** everything else — typically `.claude/`, root `CLAUDE.md`, root `TODO.md`, another change's files.

Every dirty path in-scope, or a clean tree → proceed silently. (In existing-change mode the change-directory edits are in-scope; in description / explore-result mode only a clean tree is expected.)

**Any out-of-scope path → `AskUserQuestion` with three paths**, listing the out-of-scope paths in the question's `description`:

- **(a) Commit them to <base-branch> first.** Stage and commit ONLY the out-of-scope paths to <base-branch> with a one-line subject (e.g. `docs: lessons-learned log entries from prior session`), push, then continue to Propose from a clean tree.
- **(b) Include them in this PR.** Ship adds each one by name to its `git add` beside the in-scope paths — never `-A`. For changes that are deliberately part of the same unit.
- **(c) Stash and proceed.** `git stash push --include-untracked -m "spec-to-pr precheck stash for <change-name>"` before Propose; popping it later is the user's job.

Recommend (a) in its option label when every path is under `.claude/`. Do NOT proceed until the user picks.
