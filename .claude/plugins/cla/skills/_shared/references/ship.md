# ship — commit, push, open PR

The Ship phase's procedure. **Run inline**: stage, commit, push and open the PR yourself, one base command per Bash call so the allowlist matches. Why: `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/design-tradeoffs.md` "Ship".

## 1. Branch preflight

**With `--pr-base <branch>` passed** (a stacked chain), add `--pr-base <pr-base>` to the call below and keep `--base <base-branch>` as the repo's default branch: the script needs both, and passing `<pr-base>` as `--base` would let it approve renaming the default branch. Everywhere else in this preflight, read `<base-branch>` as `<pr-base>`. The parent must exist on the remote: a child branched off an unpushed parent opens a PR whose base does not resolve. Step 4 then passes `--base <pr-base>`.

One call checks the branch before it is made:
```
python3 "${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/ship_check.py" preflight --branch <branch> --base <base-branch>
```
It reads the current branch and names the mode on its first line. `create` (on the branch the change is cut from: `<pr-base>` when stacked, else `<base-branch>`) and `rename` (any other branch) require `<branch>` to be absent locally, as a remote-tracking ref, and on the remote by exact name. `rename` also fetches the cut-from branch: `origin/<base-branch>..HEAD` must hold 0 commits — no commits to lose — and it refuses to rename the repo's default branch or `<pr-base>` themselves. With `--pr-base`, every mode also requires `<pr-base>` to have an upstream on a remote that has that branch. Exit 0 passes, 1 is a `PROBLEM` line per failure, 2 means a check could not run. Act on it, first match wins:

- **Exit 2, any mode** → the remote could not answer (network, auth, no `origin`) or git could not run: never create the branch on an unanswered question — `warn`, and **Ship, Revise and Archive all become `skip`** (no PR will open).
- **Exit 1 with a `no-upstream`, `upstream-missing` or `upstream-not-remote` line** (`--pr-base` only), whatever else it lists → STOP and surface it: the parent is not on the remote.
- **`OK preflight on-branch`** (typically a worktree made for a concurrent run) → skip the checkout; stage directly. The collision check is skipped here: it would false-positive on the branch you are on and wrongly `skip` Ship, Revise and Archive.
- **`preflight create`**: exit 0 → `git pull` (so the branch is not cut from a `<base-branch>` gone stale since this session's last fetch), then `git checkout -b <branch>`. Exit 1 → the branch exists and you are not on it: `warn`, name `<branch>-<today's date>` as the name to rerun with, and Ship, Revise and Archive become `skip` the same way. If the only line is `remote-tracking`, the branch may be gone from the remote and its ref stale: say so, and name `git fetch --prune origin` as the fix before a rerun.
- **`preflight rename`**: only a fresh `/cla:new-worktree` branch with nothing on it yet may go on. Exit 0 → `git branch -m <branch>` and continue as on-branch. Exit 1 → fail loudly; a non-zero count would carry unrelated commits into this PR, and an `on-base` line means the run sits on the default branch or the parent, which is never renamed.

**Branch name.** Use `<branch>`. A change name long enough to read awkwardly in `git log --oneline` (somewhere past 50 characters; judgment, not a rule) may be shortened to a form that keeps a recognizable hint of the change. Do not pause to confirm a branch name.

## 2. Pre-commit git-state check

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py --expect-branch <branch>
```
Exit 0 → proceed. Exit 2 (in-progress git op) or 3 (wrong branch) → halt and surface. Resolving it: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/conflict-resolution.md`.

## 2a. Pre-staging hygiene — debug tags, then scratch artifacts

**`grep -rn "\[DEBUG-" <the paths about to be staged>` must return nothing; remove any tagged line before staging.** It is `/cla:diagnose`'s instrumentation tag, which only an interrupted run leaks this far. The pattern also lives in `${CLAUDE_PLUGIN_ROOT}/skills/diagnose/SKILL.md` Phase 6 and in the guard hook `${CLAUDE_PLUGIN_ROOT}/hooks/ask-staged-debug-tag.py`; a rename must touch all three, or this grep searches for a string nothing writes.

Then scan the untracked (`??`) entries of `git status --porcelain` for a stray scratch artifact: a background agent's tool-redirect bug can write a mangled, extension-bearing filename into the repo root instead of the scratchpad. It sits at the repo root (no `/` in the path) AND contains a substring characteristic of a scratch/temp-dir path. Read its first lines to confirm (typically a `git diff` dump), then `rm "<path>"` before staging. Never fold it into the commit, and never skip this because Implement's delegate reported success.

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
Add any other legitimately touched file by name on the same line — a stylesheet, a smoke script, a config file, root `TODO.md`, or for a `.claude/`-meta change the harness files it edited **inside this repo** (never a path in the installed plugin tree). Never expand to `-A`.

**Trailers go in a single second `-m`**, newline-separated, which makes them the message's last paragraph; the session-attribution lines go directly under the last `Measured-by:` line, with no blank line:

```
git commit -m "feat: <change-name>" -m "Measured-by: <command> — <claim>
Measured-by: <command> — <claim>
Co-Authored-By: <name> <<email>>
Claude-Session: <session URL>"
```

One `-m` per trailer would split them into separate paragraphs. Omit the second `-m` when the change asserts no measurement. **Git parses trailers from the last paragraph only, and every line in it must be `key: value`.** One line without that shape, or a blank line, drops every trailer — the usual offender is a bare `Closes #199`: write `Closes: #199`, or put it (and any body) in its own paragraph above the trailers.

**Check that it parsed, before you push.** The `Measured-by:` lines you wrote and the trailers git's parser sees must agree:

```
python3 "${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/ship_check.py" trailers
```

Exit 0 passes, `0` and `0` included. Exit 1 means the block is split: `git commit --amend` before pushing. Exit 2 means it could not read the commit: fix that before pushing. Nothing else reports a split block — `git log --grep` still finds it.

**Run the push with `run_in_background`, once the trailer check above agrees.** The `git push` line in the block at the top of this step is that push. A pre-push hook can run for minutes. The harness moves a foreground Bash call past 120 s to the background, and that call returns no exit code. Wait for the completion notice, then read the exit code.

**Then check the remote head**, once the push has exited 0:

```
python3 "${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/ship_check.py" pushed --branch <branch>
```

It requires the current branch to be `<branch>`, `HEAD` to equal the remote's `refs/heads/<branch>`, and the branch's configured upstream to be that branch on `origin`. The push exiting non-zero or with no exit code, or this check exiting anything but 0: report `push not verified` and STOP before step 4. Do not retry the push blindly; a rejected or half-run hook needs a look first.

## 4. Open the PR

Single-line body, no Markdown headers and no `\n#` (the `gh pr create --body` parser bug; a mid-line `#1234` is fine):
```
gh pr create --title "feat: <change-name>" --body "Closes openspec/changes/<change-name>/. Checks: build + lint passed. Risk: <level> — <reason>; reviewers: <list>."
```

**Stacked chains only** (`--pr-base` passed) — this REPLACES the command above. An explicit base is required, or GitHub opens the PR against the default branch with the whole parent chain in its diff. Two calls:

```
gh pr list --head <pr-base> --state open --json number --jq ".[0].number"
```

```
gh pr create --base <pr-base> --title "feat: <change-name>" --body "Stacked on #<parent-PR-number>. Closes openspec/changes/<change-name>/. Checks: build + lint passed. Risk: <level> — <reason>; reviewers: <list>."
```

The `Checks:` clause names the checks Test actually ran (`build + lint + test passed.`, `build + lint passed.`, `skipped (docs-only).`). The `Risk:` clause is your call from the diff: the level, the signal behind it, and the reviewers the review-sizing table gives for it. The table is "Review sizing by risk" in `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`. Unsure means high. Revise round 1 reads this clause. No Summary section, no Test-plan checklist.

**Post-check:** `gh pr view --json url state` returns `OPEN` → ✓. A gh failure → ⚠, and Revise becomes `skip` (no PR to review).
