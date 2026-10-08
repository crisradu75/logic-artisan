# ship — commit, push, open PR

The Ship phase's procedure. **Run inline**: stage, commit, push and open the PR yourself, one base command per Bash call so the allowlist matches. Why: `design-tradeoffs.md` "Ship".

## 1. Branch preflight

**With `--pr-base <branch>` passed** (a stacked chain), read every `<base-branch>` in this preflight as `<pr-base>`. The parent must exist on the remote: `git rev-parse --abbrev-ref <pr-base>@{u}` succeeding confirms it. No upstream → STOP and surface it; a child branched off an unpushed parent opens a PR whose base does not resolve. Step 4 then passes `--base <pr-base>`.

Determine the current branch — `git rev-parse --abbrev-ref HEAD` — and dispatch on it:

- **Already on `<branch>`** (typically a worktree made for a concurrent run) → **skip the collision check and the checkout; stage directly.** The collision check would false-positive on the branch you are on and wrongly `skip` Ship, Revise and Archive.
- **On `<base-branch>`** → collision preflight, then create the branch:
  ```
  git rev-parse --verify --quiet refs/heads/<branch>          # must be EMPTY
  git ls-remote --exit-code --heads origin <branch>           # exit 2 = absent, which is what you want
  ```
  Either finds the branch → it exists and you are not on it: `warn`, name `<branch>-<today's date>` as the name to rerun with, and **Ship, Revise and Archive all become `skip`** (no PR will open). `ls-remote` exiting anything other than 0 or 2 → the remote could not answer (network, auth, no `origin`): never create the branch on an unanswered question — `warn` and skip Ship, Revise and Archive the same way.
  Both clean → `git pull` (so the branch is not cut from a `<base-branch>` gone stale since this session's last fetch), then `git checkout -b <branch>`.
- **Any other branch** → fail loudly. **One exception — a fresh `/cla:new-worktree` branch with nothing on it yet:** rename it in place once all of these pass:
  ```
  git fetch origin <base-branch>
  git rev-list --count origin/<base-branch>..HEAD        # must be 0 — no commits to lose
  git rev-parse --verify --quiet refs/remotes/origin/<branch>   # must be EMPTY — no remote branch to collide with
  git rev-parse --verify --quiet refs/heads/<branch>            # must be EMPTY — no local branch either
  ```
  All clean → `git branch -m <branch>` and continue as "already on `<branch>`". Any failing → fail loudly; a non-zero count would carry unrelated commits into this PR.

**Branch name.** Use `<branch>`. A change name long enough to read awkwardly in `git log --oneline` (somewhere past 50 characters; judgment, not a rule) may be shortened to a form that keeps a recognizable hint of the change. Do not pause to confirm a branch name.

## 2. Pre-commit git-state check

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py --expect-branch <branch>
```
Exit 0 → proceed. Exit 2 (in-progress git op) or 3 (wrong branch) → halt and surface. Resolving it: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/conflict-resolution.md`.

## 2a. Pre-staging hygiene — debug tags, then scratch artifacts

**`grep -rn "\[DEBUG-" <the paths about to be staged>` must return nothing; remove any tagged line before staging.** It is `/cla:diagnose`'s instrumentation tag, which only an interrupted run leaks this far. The pattern also lives in `${CLAUDE_PLUGIN_ROOT}/skills/diagnose/SKILL.md` Phase 6; a rename must touch both, or this grep searches for a string nothing writes.

Then scan the untracked (`??`) entries of `git status --porcelain` for a stray scratch artifact: a background agent's tool-redirect bug can write a mangled, extension-bearing filename into the repo root instead of the scratchpad. It sits at the repo root (no `/` in the path) AND contains a substring characteristic of a scratch/temp-dir path (this repo's signature, if it has hit one: `cla.io/overlays/spec-to-pr.md` "Incident / offense history"). Read its first lines to confirm (typically a `git diff` dump), then `rm "<path>"` before staging. Never fold it into the commit, and never skip this because Implement's delegate reported success.

## 2b. Every measurement this change asserts names the command that produced it

For each measurement the change asserts — a count, a coverage figure, "measured", "verified", "zero X", any number offered as fact, in the diff or in the message — one trailer line goes at the end of the commit message:

```
Measured-by: <the exact command, runnable as written> — <the claim it produced>
```

The command is a real invocation a reader can re-run, not "the test suite". A claim you cannot pair with a runnable command has two exits and both are edits: **run the command now, or delete the claim** and restate it as the reasoning it is ("expected", "by inspection"). There is no third exit in which the claim ships and the command is owed. A change asserting no measurement carries no trailer — never `Measured-by: none`, which certifies a check nobody ran.

**A measurement is evidence about the tree and conditions that produced it, and nothing else.** Three shapes break that, and each reads as settled fact. A pair asserting sameness — "unchanged", "same counts", "no regression" — must come from one tree, and the trailer must name it; measured on two, it asserts a third claim, that conditions matched, with no command behind it. A number measured earlier and restated as current is the same defect with one run missing. A number true on one platform, shell or edition is not true generally until someone runs the others. Three exits, all edits: run the comparison now, restate the numbers as two independent observations, or name the conditions. A before/after delta is allowed — two trees by construction, so name both.

**The trigger is a claim this change asserts, not a check that ran.** The standing pre-PR gates (the suite, the linters, the conformance scripts) earn no trailer; their outcome goes in the PR body's `Checks:` line. Trailers are the one exception to the subject-only message style. The PR body follows the same rule: a measurement added to it names its command, or is not asserted there.

## 3. Stage, commit, push

Path-scoped staging — NEVER `git add -A` (`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/bash-discipline.md`). Name the change directory and each source directory the change touched (from `git status --porcelain` or the tasks.md file list), e.g. in a monorepo:
```
git add openspec/changes/<change-name>/ apps/<app>/src/ packages/<package>/src/
git commit -m "feat: <change-name>"
git push -u origin <branch>
```
Add any other legitimately touched file by name on the same line — a stylesheet, a smoke script, a config file, root `TODO.md`, or for a `.claude/`-meta change the harness files it edited **inside this repo** (never a path in the installed plugin tree; this repo's worked examples: `cla.io/overlays/spec-to-pr.md`). Never expand to `-A`.

**Trailers go in a single second `-m`**, newline-separated, which makes them the message's last paragraph; the session-attribution lines go directly under the last `Measured-by:` line, with no blank line:

```
git commit -m "feat: <change-name>" -m "Measured-by: <command> — <claim>
Measured-by: <command> — <claim>
Co-Authored-By: <name> <<email>>
Claude-Session: <session URL>"
```

One `-m` per trailer would split them into separate paragraphs. Omit the second `-m` when the change asserts no measurement. **Git parses trailers from the last paragraph only, and every line in it must be `key: value`.** One line without that shape, or a blank line, drops every trailer — the usual offender is a bare `Closes #199`: write `Closes: #199`, or put it (and any body) in its own paragraph above the trailers.

**Check that it parsed, before you push.** These must agree:

```
git log -1 --format=%B | grep -c '^Measured-by:'
git log -1 --format='%(trailers:key=Measured-by,valueonly=true,unfold=true)' | grep -c .
```

The first counts what you wrote, the second what git's parser sees. Equal passes, `0` and `0` included. Different means the block is split: `git commit --amend` before pushing. Nothing else reports it — `git log --grep` still finds a broken block.

## 4. Open the PR

Single-line body, no Markdown headers and no `\n#` (the `gh pr create --body` parser bug; a mid-line `#1234` is fine):
```
gh pr create --title "feat: <change-name>" --body "Closes openspec/changes/<change-name>/. Checks: build + lint passed."
```

**Stacked chains only** (`--pr-base` passed) — this REPLACES the command above. An explicit base is required, or GitHub opens the PR against the default branch with the whole parent chain in its diff. Two calls:

```
gh pr list --head <pr-base> --state open --json number --jq ".[0].number"
```

```
gh pr create --base <pr-base> --title "feat: <change-name>" --body "Stacked on #<parent-PR-number>. Closes openspec/changes/<change-name>/. Checks: build + lint passed."
```

The `Checks:` clause names the checks Test actually ran (`build + lint + test passed.`, `build + lint passed.`, `skipped (docs-only).`). No Summary section, no Test-plan checklist.

**Post-check:** `gh pr view --json url state` returns `OPEN` → ✓. A gh failure → ⚠, and Revise becomes `skip` (no PR to review).
