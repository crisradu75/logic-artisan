# chain-merge — how a chain merges a pull request

`/cla:multi-lite` and `/cla:multi-pr` merge pull requests during an unattended run. This file
holds the steps they share: the bootstrap before the chain starts, what the autonomy override may
not do to merging, recording the head, the pre-merge checks, the merge command, confirming the
merge, a host that refuses it, and a fix needed after a merge.

**What a skill does when a check fails stays in the skill.** Here a failed check gives a
**reason**, written beside the item's status in the run notes. `multi-lite` then leaves the PR open
or quarantines; `multi-pr` leaves an independent open and halts the chain when a later change needs
this one merged.

Names used below:

- `<pr>`, `<branch>`, `head_sha` — the PR number, branch and head commit the run notes recorded for
  this item ("Record the head" below). Never a re-derived branch name or an in-context number.
- **run notes** — the skill's `cla.io/retro/<skill>-run-notes-<date>.md`. Local, gitignored working
  state: nothing adds, commits or pushes them.
- `<base-branch>` — resolved per `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/base-branch-resolution.md`.

## Bootstrap (once, before the chain starts)

1. **Permissions.** Compare `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/required-permissions.json`
   with `.claude/settings.local.json`, as `/cla:spec-to-pr`'s "Bootstrap permissions" section does.
   Missing patterns → show them and apply on approval. This is the one ask outside the plan gate.
2. **Working tree.** Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py`.
   An in-progress op (exit 2) → resolve it per
   `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/conflict-resolution.md`. Any other non-zero
   exit halts. The script does not look at uncommitted files, so also run `git status --porcelain`:
   a dirty tree with paths outside this run → Step 2 of
   `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/precheck.md`. A dirty tree at the start
   poisons every later item.
3. **Run notes are ignored.** The skill's Phase 0 runs `git check-ignore` on its own notes file
   name. Non-zero → stop.
4. **Start on a clean, current `<base-branch>`, in the primary clone.** If HEAD is on another
   branch that carries local commits unrelated to this run, leave that branch alone. Then
   `git checkout <base-branch>`, then `git pull` — two commands, never `&&`.

**Primary clone by default.** A linked worktree cannot check out `<base-branch>`, because the
primary clone holds it. If another live session contends for the primary clone, pivot to a
dedicated worktree: `git fetch origin <base-branch>`, then
`git worktree add .claude/worktrees/<id> -b <branch> origin/<base-branch>`. From then on, cut each
item's branch from `origin/<base-branch>` after a fetch.

## The autonomy override and merging

An invocation that says "operate autonomously", "don't ask, just run" or the like pre-confirms the
plan gate. The skill applies its recommended plan and states it, with every default it applied, as
its first output, so the user can still reply and override. Two limits bind merging:

- **It never widens merging.** It applies only a merge policy the invocation names, or else the
  skill's narrowest one. A pre-confirmed plan is not an authorization to merge more than the
  invocation asked for.
- **The shared-state answer is never pre-answered.** Whether each item moves shared environment
  state (a migration, seeded data, a provisioning step) is worked out from its artifacts exactly
  as in an attended run, and the first output shows each answer with what it rests on. A "no"
  with nothing behind it is an exemption, not a check.

The skill's own file says what else the override skips and what it never skips.

## Record the head

The moment an item's PR opens, read its head with `gh pr view <pr> --json headRefOid`. Write
`branch`, `pr_number` and `head_sha` to the item's row in the run notes.

`head_sha` is the commit the item's review and full test gate must cover. **Nothing updates it
except a fix the orchestrator itself commits to `<branch>`,** and only once all three checks below
pass, each value compared in context (not piped through `grep`/`awk`):

- `git rev-parse HEAD` must differ from the row's current `head_sha`. The same value means no commit was made (a hook rejected it, or nothing was staged).
- `git status --porcelain -- . ':(exclude)cla.io/retro'` must be empty. Anything listed is part of
  the fix that is not in the commit, which every later test would still see on disk.
- `git rev-parse HEAD` must equal `git ls-remote origin <branch>`.

The first two failing → the reason is `fix not committed`. The third failing → `push not verified`.
All three pass → write the pushed commit as the new `head_sha`.

A commit anyone else pushes — the user, a bot, another session — leaves `head_sha` behind, so the
pre-merge checks refuse that PR as `head moved`. **A resume never merges a moved head:** a PR whose
head differs from its recorded `head_sha` is left open as `head moved since review`, and one with no
recorded `head_sha` (the run notes were lost) as `head unverifiable (ledger lost)`. Both are the
user's to review and merge by hand.

## Pre-merge checks (every merge)

Run them in this order. The local gate runs before GitHub's merge state is read, because the gate
takes minutes and remote checks are usually still running right after a push. A skill may run checks
of its own before these.

1. **The PR is open on the recorded head.** Run `gh pr view <pr> --json state,headRefOid`. `state`
   must be `OPEN`. `headRefOid` must equal `head_sha`; a different head means commits nobody tested
   or reviewed here, so do not merge, and the reason is `head moved`.
2. **The local checkout is exactly that head.** `git rev-parse HEAD` must equal `head_sha`. If it
   does not, run `git checkout <branch>` then `git pull`, and compare again. Still different → do
   not merge; the reason is `local head mismatch`.
   Then `git status --porcelain -- . ':(exclude)cla.io/retro'` must be empty; anything listed would be tested by the gate below without being part of the merge, so do not merge; the reason is `uncommitted changes`.
3. **The full Test gate is green on `head_sha`.** Every merge needs this, because review fixes are
   committed after the item's own Test phase. Run the full gate the skill names, from
   `cla.io/project-facts.md`. A green run this session on exactly `head_sha`, with the tree
   unchanged since, counts.
   - Green → continue.
   - Red → do not merge; the reason is `full gate red: <failing check>`. Do not re-run it hoping
     for green. A flaky gate is a finding for the user, not a retry.
   - `cla.io/project-facts.md` names no test commands and the PR changes source-affecting paths (as `/cla:lite-pr`'s Test phase defines them) → do not merge; the reason is `full gate unavailable`. A merge cannot treat this as a warning, because nothing would have tested the merged code.
   - The PR changes no source-affecting paths → nothing to gate. Record
     `gate skipped: no source-affecting paths` beside the status and continue.
4. **Remote checks have finished.** Run `gh pr checks <pr> --json name,bucket` and read the result
   in context:
   - JSON output → each check's `bucket` is `pass`, `fail`, `pending`, `skipping`, or `cancel`.
     - Any `pending` → wait with `python3 -c "import time; time.sleep(60)"` and query again, at
       most 15 queries (about 15 minutes). Still pending → the reason is `checks still pending`.
     - Any `fail` or `cancel` → the reason is `checks not green`.
     - Only `pass` and `skipping` → continue.
   - The output says `no checks reported` → checks may not have registered for a head pushed
     moments ago. Wait once with `python3 -c "import time; time.sleep(60)"` and query again. Still
     none → the repo has no remote checks for this PR; continue. (GitHub starts no CI run for a
     conflicting PR, so this is also how a conflict reaches step 5 instead of an endless wait.)
   - Any other output with a non-zero exit (an auth, network, or rate-limit error) → do not merge;
     the reason is `checks not readable`. `gh pr checks` exits 1 both for no checks and for a
     failure, so only the message tells them apart.
5. **`mergeStateStatus` allows the merge.** Run `gh pr view <pr> --json mergeStateStatus`.
   - `CLEAN`, `HAS_HOOKS`, or `BEHIND` → proceed. `BEHIND` means the base gained commits after this branch was cut, so the merged tree was never tested as a whole; record `behind base: merged tree not tested` beside the status so the final report names it.
   - `DIRTY` → the reason is `conflicts`. Never rebase or force-push to clear it: that changes the
     code that was tested and reviewed.
   - `UNSTABLE` → the reason is `checks not green`.
   - `BLOCKED` → the reason is `blocked by branch protection`.
   - `DRAFT` → the reason is `draft`.
   - `UNKNOWN` → GitHub has not computed it yet. Wait once with
     `python3 -c "import time; time.sleep(15)"`, then query again. Still `UNKNOWN` → the reason is
     `mergeability unknown`.

## Merge, then confirm it landed

Pass the checked head to the merge, so GitHub refuses it if the branch moved after the checks:

```
ALLOW_PR_MERGE=1 gh pr merge <pr> --squash --delete-branch --match-head-commit <head_sha>
```

**The `ALLOW_PR_MERGE=1` prefix is required, and belongs on the merge command only.**
`ask-destructive-git.py` prompts on every `gh pr merge`, because a hook cannot tell an authorized
merge from one the agent assumed — a real failure that shipped two unrequested merges. A chain is
the legitimate exception: the user confirmed the plan that authorizes this merge at the start, and
the run is unattended, so a prompt here would hang. Use the narrow variable, NOT
`ALLOW_DESTRUCTIVE_GIT=1`, which would also disarm the force-push, `reset --hard` and
branch-force-delete checks. Export neither; prefixing this one command keeps the exception scoped.

**An exit code of 0 does not prove a merge.** On a branch that requires a merge queue, `gh pr merge` exits 0 after only adding the PR to the queue, or after turning on auto-merge while required checks are pending. Confirm it:

1. Run `gh pr view <pr> --json state,mergeCommit,autoMergeRequest`. `state` must be `MERGED`. Otherwise:
   - `autoMergeRequest` is set, or the PR is in a merge queue → the reason is `queued: merges later outside this run`. It is not merged now, so it does not count as merged; the final report says plainly that it will merge on its own. Do not disable it: the repo chose it.
   - Anything else → the reason is `merge not confirmed (state <state>)`.
2. `MERGED` is the fact. Write `status: merged` and `merge_commit: <mergeCommit.oid>` to the row now.
3. Bring the local base up to date. In the primary clone: `git checkout <base-branch>`, then
   `git pull`. In a worktree, which cannot check out `<base-branch>`: `git fetch origin <base-branch>`.
   A failure here is not a merge failure: record `base not updated` beside the merged status and
   continue; the next item's own base step pulls again.

**In a worktree, the local `<base-branch>` ref goes stale after every merge.** Compare and diff
against `origin/<base-branch>`, after a fetch, never the local ref; a stale ref silently pads a diff
with every earlier item's files.

**Leave the local feature branch.** No force or history-rewriting git mid-chain (`git branch -D`,
`git push --force`, `git reset --hard`): `ask-destructive-git.py` prompts on each, and an unattended
prompt stalls the chain until a human returns. Never set `ALLOW_DESTRUCTIVE_GIT=1` to get one
through.

### If `gh pr merge` exits non-zero

Check the PR before reading the error: `gh pr view <pr> --json state,mergeCommit`. A `MERGED` state
means the merge happened and only a later part failed — `--delete-branch` fails this way when
`<base-branch>` is checked out in another worktree. Take the confirmation steps above; if the remote
branch survived, delete it with `git push origin --delete <branch>`. Otherwise, take the first arm
that matches:

- **The host runtime refused to run the command at all** → a tool-permission denial from the host, with no output from `gh` itself. This is the answer for the whole run. Do NOT hunt for a flag spelling that gets through; that is working around a safety gate, not configuring one. Append `merging stopped: host refused merge of <id>` to the run notes header. The reason for this item is `merge refused`; every later merge this run is skipped without an attempt, with the reason `merge refused earlier in the run`. A fresh session drops that header line, because a refusal is a fact about the session that met it. Probing for this up front is not worth it: a probe that succeeds has merged something.
- **Any other error from `gh`** → the reason is `merge error: <first line of the error>`. That covers the `--match-head-commit` refusal (the branch moved after the checks), a conflict, a failing required check, branch protection, an auth or rate-limit error, and a disallowed merge method. It does **not** set `merging stopped`: an error `gh` returned is about this PR or this moment, not a refusal by the host.

## A fix needed after a merge

Never push a fix to `<base-branch>`. The `pre-push` hook refuses it where installed, and a chain does
not rely on that. Open a small follow-up branch and PR (`fix/<item>-review-followups` or similar),
record its head, and merge it through the same checks above.
