# ship — commit, push, open PR (full mechanics)

The Ship phase's step-by-step procedure. `SKILL.md`'s Ship stub carries the load-bearing invariants; this file carries the recipes. **Run inline** — the orchestrator stages, commits, pushes, and opens the PR itself via separate Bash calls (one base command per call to keep the allowlist matching). Earlier versions delegated to `commit-commands:commit-push-pr`, but that plugin re-prompted Claude with the diff and asked it to run the same shell commands anyway — pure indirection.

## 1. Branch preflight

**With `--pr-base <branch>` passed** (a stacked chain — see `SKILL.md`'s `<pr-base>` rule), every mention of `<base-branch>` in this preflight reads as `<pr-base>`. The parent branch MUST exist on the remote — by construction it carries an open PR; `git rev-parse --abbrev-ref <pr-base>@{u}` succeeding is the cheap confirmation. If it has no upstream, STOP and surface it rather than proceeding: a child branched off an unpushed parent produces a PR whose base does not resolve on the remote. The PR-open step below then passes `--base <pr-base>` explicitly.

FIRST determine the current branch — `git rev-parse --abbrev-ref HEAD` — and dispatch on it:

- **Already on `<branch>`** → the branch already exists and is checked out *on purpose* (typically a dedicated worktree for a concurrent run — see `SKILL.md` "Concurrent runs"). **SKIP the collision check and the checkout; proceed straight to staging.** Running the collision check here would read the *shared* local refs and false-positive on the very branch you are on, wrongly marking Ship (and Revise + Archive) as `skip`.
- **On `<base-branch>`** → run the collision preflight, then create the branch:
  ```
  git rev-parse --verify --quiet refs/heads/<branch>          # must be EMPTY
  git ls-remote --exit-code --heads origin <branch>           # exit 2 = absent, which is what you want
  ```
  Either one finding the branch → it already exists (and you are NOT on it); record `warn` and name `<branch>-<today's date>` as the alternative to rerun with. **All subsequent phases (Revise AND Archive) become `skip`** because no PR will be opened.
  `ls-remote` exiting anything other than 0 or 2 → the remote could not be reached (network, auth, or no `origin` at all). Do NOT create the branch on the strength of an unanswered question: record `warn` and skip the rest of Ship + Revise + Archive, same as a collision.
  Both clean → `git pull` (fast-forward local `<base-branch>` to `origin/<base-branch>` — cheap, and prevents branching off a `<base-branch>` that's gone stale since this session's own last fetch, e.g. because a chained run merged another change in the meantime) then `git checkout -b <branch>` before staging.
- **On any other branch** (non-base-branch, non-`<branch>`) → fail loudly; not the orchestrator's job to disambiguate. **One exception — a fresh `/cla:new-worktree` branch with nothing on it yet.** That skill creates its own branch name, so a run started inside such a worktree lands here through no fault of its own, with zero work at risk. Rename in place rather than failing. All three checks must pass first:
  ```
  git fetch origin <base-branch>
  git rev-list --count origin/<base-branch>..HEAD        # must be 0 — no commits to lose
  git rev-parse --verify --quiet refs/remotes/origin/<branch>   # must be EMPTY — no remote branch to collide with
  git rev-parse --verify --quiet refs/heads/<branch>            # must be EMPTY — no local branch either
  ```
  All three clean → `git branch -m <branch>`, then proceed exactly as the "already on `<branch>`" case above (skip the collision check, stage directly). Any check failing → fail loudly as normal; a non-zero commit count in particular means renaming would silently carry unrelated commits into this change's PR.

**Branch name.** Use `<branch>` directly. If the change name is verbose enough that the full branch name reads awkwardly in `git log --oneline` or `git branch -v` (typical cutoff: somewhere past 50 characters; use judgment, not a hard rule), pick a shorter form that keeps a recognizable hint of the change. Don't pause for confirmation on routine branch names; the branch name is reversible and low-stakes.

## 2. Pre-commit git-state check

Before staging anything:
```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py --expect-branch <branch>
```
Exit 0 → proceed. Exit 2 (in-progress git op) or 3 (wrong branch) → halt and surface to the user. Resolving it: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/conflict-resolution.md`. Cheap (<1s), and catches the case where an external session left a cherry-pick/rebase active or where HEAD drifted between Test's checks and now.

## 2a. Scratch-artifact hygiene check

Run `git status --porcelain` and scan the untracked (`??`) entries for a stray scratch artifact — a background-agent tool-redirect bug can write a mangled, extension-bearing filename literally into the repo root instead of the actual scratchpad directory. Recognize it by: sitting at repo root (no `/` in the path) AND containing a substring characteristic of a scratch/temp-dir path (see `cla.io/overlays/spec-to-pr.md` "Incident history" for the exact signature this repo has hit). This is tool-generated garbage, never the user's or the change's own work — read its first few lines to confirm (it's typically a `git diff` dump or similar), then delete it (`rm "<path>"`) before staging. Do NOT silently fold it into the commit via a broad add, and do NOT skip this check because Implement's delegate reported success — the two are independent (the file is a side effect of the delegate's tool use, not a task output).

## 2b. Every measurement this change asserts names the command that produced it

This stop is where the change's claims are assembled into a message, which is why the obligation is discharged here rather than while an edit is being typed — a rule that fires at the keyboard fires hundreds of tool calls before the claim is written down, and by the commit the claim already reads as settled. For each measurement the change asserts — a count, a coverage figure, "measured", "verified", "zero X", any number offered as fact, in the diff or in the message — one trailer line goes at the end of the commit message:

```
Measured-by: <the exact command, runnable as written> — <the claim it produced>
```

The command is a real invocation, not "the test suite" and not an elided one; the point of the trailer is that a reader can re-run it. You wrote the claims, so finding them needs no scanner. A claim you cannot pair with a runnable command has two exits and both are edits: **run the command now, or delete the claim** and restate it as the reasoning it actually is ("expected", "by inspection", "should"). There is no third exit in which the claim ships and the command is owed. A change asserting no measurement carries no trailer — never `Measured-by: none`, which certifies a check nobody ran while reading as evidence that one happened.

Trailers are the one deliberate exception to the subject-only default in `SKILL.md`'s message-style table, and they are not detail: they are the evidence a claim already owes. They also make the corpus queryable — `git log --grep='^Measured-by:'` returns every measurement this repo has shipped, each with the command that reproduces it.

The same obligation covers the PR body in step 4. The default one-line body already names its checks; a measurement added to it names its command the same way, or is not asserted there.

## 3. Stage, commit, push

Path-scoped staging — NEVER `git add -A` (see `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/bash-discipline.md` for why). There is no repo-root `src/` — the monorepo split moved it under each app/package, so name the specific `apps/<app>/src/` and/or `packages/<package>/src/` directories the change actually touched (determine which from `git status --porcelain` or the tasks.md file list), alongside the change directory:
```
git add openspec/changes/<change-name>/ apps/<app>/src/ packages/<package>/src/
git commit -m "feat: <change-name>"
git push -u origin <branch>
```

**Carrying the §2b trailers needs no scratch file.** A second `-m` holding every `Measured-by:` line, newline-separated, becomes the message's last paragraph, which is what makes it a trailer block:

```
git commit -m "feat: <change-name>" -m "Measured-by: <command> — <claim>
Measured-by: <command> — <claim>"
```

One `-m` per trailer would put a blank line between them and break the block into separate paragraphs, so keep them in a single `-m`. Omit the second `-m` entirely when the change asserts no measurement.
List every touched `apps/*/src/`/`packages/*/src/` path explicitly — a change scoped to one app stages just that app's `src/`; a change touching a shared package plus its consumer stages both. If your change legitimately touches other top-level paths (e.g. a per-app stylesheet, a smoke-test script, a config file, root `TODO.md`, a sub-app's own doc file, or — for a `.claude/`-meta change — the specific harness files it edited **inside this repo** (never a path in the installed plugin tree, which is outside the repo and not stageable at all) — see `cla.io/overlays/spec-to-pr.md` for this repo's worked examples), add each by name on the same `git add` line — never expand to `-A`. No commit-msg file; the change name is enough.

## 4. Open the PR

Single-line body, no Markdown headers and no `\n#` sequence (avoids the `gh pr create --body` parser bug; mid-line `#1234` issue references are fine):
```
gh pr create --title "feat: <change-name>" --body "Closes openspec/changes/<change-name>/. Checks: build + lint passed."
```

**Stacked chains only** (`--pr-base` passed) — this REPLACES the command above; run it instead, never both. An explicit base is REQUIRED: without it GitHub defaults the PR to the repo default branch and its diff silently includes the whole parent chain. Resolve the parent's PR number first, then open (two separate calls, one base command each):

```
gh pr list --head <pr-base> --state open --json number --jq ".[0].number"
```

```
gh pr create --base <pr-base> --title "feat: <change-name>" --body "Stacked on #<parent-PR-number>. Closes openspec/changes/<change-name>/. Checks: build + lint passed."
```
The body summarizes the Test outcome, listing the checks that ran (e.g. `Checks: build + lint + test passed.`, or `Checks: build + lint passed.` when no test suite is defined, or `Checks: skipped (docs-only).`). No Summary section, no Test-plan checklist.

**Post-check:** `gh pr view --json url state` returns `OPEN`. ✓ on OPEN. ⚠ on gh failure; the subsequent Revise phase is then `skip` (cannot review a PR that does not exist).
