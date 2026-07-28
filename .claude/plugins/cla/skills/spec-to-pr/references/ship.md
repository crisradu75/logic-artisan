# ship — commit, push, open PR (full mechanics)

The Ship phase's step-by-step procedure. `SKILL.md`'s Ship stub carries the load-bearing invariants; this file carries the recipes. **Run inline** — the orchestrator stages, commits, pushes, and opens the PR itself via separate Bash calls (one base command per call to keep the allowlist matching). Earlier versions delegated to `commit-commands:commit-push-pr`, but that plugin re-prompted Claude with the diff and asked it to run the same shell commands anyway — pure indirection.

## 1. Branch preflight

FIRST determine the current branch — `git rev-parse --abbrev-ref HEAD` — and dispatch on it:

- **Already on `feature/<change-name>`** → the branch already exists and is checked out *on purpose* (typically a dedicated worktree for a concurrent run — see `SKILL.md` "Concurrent runs"). **SKIP the collision check and the checkout; proceed straight to staging.** Do NOT run `branch.py` here: its collision check (`git rev-parse --verify feature/<change-name>`) reads the *shared* local refs and would false-positive on the very branch you are on, wrongly marking Ship (and Revise + Archive) as `skip`.
- **On `master`** → run the collision preflight, then create the branch:
  ```
  python3 .claude/plugins/cla/skills/spec-to-pr/scripts/branch.py <change-name> --dry-run
  ```
  Exit 3 → branch already exists locally or on origin (and you are NOT on it); record `warn` with the date-suffixed alternative from stderr. **All subsequent phases (Revise AND Archive) become `skip`** because no PR will be opened.
  Exit 5 → remote could not be reached (network/auth/missing-remote); record `warn` and skip the rest of Ship + Revise + Archive (same as exit 3).
  Exit 0 → `git pull` (fast-forward local `master` to `origin/master` — cheap, and prevents branching off a `master` that's gone stale since this session's own last fetch, e.g. because a chained run merged another change in the meantime) then `git checkout -b feature/<change-name>` before staging.
- **On any other branch** (non-master, non-`feature/<change-name>`) → fail loudly; not the orchestrator's job to disambiguate. **One exception — a fresh `/cla:new-worktree` branch with nothing on it yet.** That skill creates its own branch name, so a run started inside such a worktree lands here through no fault of its own, with zero work at risk. Rename in place rather than failing. All three checks must pass first:
  ```
  git fetch origin master
  git rev-list --count origin/master..HEAD        # must be 0 — no commits to lose
  git rev-parse --verify --quiet refs/remotes/origin/feature/<change-name>   # must be EMPTY — no remote branch to collide with
  git rev-parse --verify --quiet refs/heads/feature/<change-name>            # must be EMPTY — no local branch either
  ```
  All three clean → `git branch -m feature/<change-name>`, then proceed exactly as the "already on `feature/<change-name>`" case above (skip `branch.py`, stage directly). Any check failing → fail loudly as normal; a non-zero commit count in particular means renaming would silently carry unrelated commits into this change's PR.

**Branch name.** Use `feature/<change-name>` directly. If the change name is verbose enough that the full branch name reads awkwardly in `git log --oneline` or `git branch -v` (typical cutoff: somewhere past 50 characters; use judgment, not a hard rule), pick a shorter form that keeps a recognizable hint of the change. Don't pause for confirmation on routine branch names; the branch name is reversible and low-stakes.

## 2. Pre-commit git-state check

Before staging anything:
```
python3 .claude/plugins/cla/skills/spec-to-pr/scripts/git_state.py --expect-branch feature/<change-name>
```
Exit 0 → proceed. Exit 2 (in-progress git op) or 3 (wrong branch) → halt and surface to the user. Cheap (<1s), and catches the case where an external session left a cherry-pick/rebase active or where HEAD drifted between Test's checks and now.

## 2a. Scratch-artifact hygiene check

Run `git status --porcelain` and scan the untracked (`??`) entries for a stray scratch artifact — a background-agent tool-redirect bug can write a mangled, extension-bearing filename literally into the repo root instead of the actual scratchpad directory. Recognize it by: sitting at repo root (no `/` in the path) AND containing a substring characteristic of a scratch/temp-dir path (see `references/project-context.md` "Incident history" for the exact signature this repo has hit). This is tool-generated garbage, never the user's or the change's own work — read its first few lines to confirm (it's typically a `git diff` dump or similar), then delete it (`rm "<path>"`) before staging. Do NOT silently fold it into the commit via a broad add, and do NOT skip this check because Implement's delegate reported success — the two are independent (the file is a side effect of the delegate's tool use, not a task output).

## 3. Stage, commit, push

Path-scoped staging — NEVER `git add -A` (see `references/bash-discipline.md` for why). There is no repo-root `src/` — the monorepo split moved it under each app/package, so name the specific `apps/<app>/src/` and/or `packages/<package>/src/` directories the change actually touched (determine which from `git status --porcelain` or the tasks.md file list), alongside the change directory:
```
git add openspec/changes/<change-name>/ apps/<app>/src/ packages/<package>/src/
git commit -m "feat: <change-name>"
git push -u origin feature/<change-name>
```
List every touched `apps/*/src/`/`packages/*/src/` path explicitly — a change scoped to one app stages just that app's `src/`; a change touching a shared package plus its consumer stages both. If your change legitimately touches other top-level paths (e.g. a per-app stylesheet, a smoke-test script, a config file, root `TODO.md`, a sub-app's own doc file, or — for a `.claude/`-meta change — the specific `.claude/plugins/cla/skills/<name>/` files it edited — see `references/project-context.md` for this repo's worked examples), add each by name on the same `git add` line — never expand to `-A`. No commit-msg file; the change name is enough.

## 4. Open the PR

Single-line body, no Markdown headers and no `\n#` sequence (avoids the `gh pr create --body` parser bug; mid-line `#1234` issue references are fine):
```
gh pr create --title "feat: <change-name>" --body "Closes openspec/changes/<change-name>/. Checks: build + lint passed."
```
The body summarizes the Test outcome, listing the checks that ran (e.g. `Checks: build + lint + test passed.`, or `Checks: build + lint passed.` when no test suite is defined, or `Checks: skipped (docs-only).`). No Summary section, no Test-plan checklist.

**Post-check:** `gh pr view --json url state` returns `OPEN`. ✓ on OPEN. ⚠ on gh failure; the subsequent Revise phase is then `skip` (cannot review a PR that does not exist).
