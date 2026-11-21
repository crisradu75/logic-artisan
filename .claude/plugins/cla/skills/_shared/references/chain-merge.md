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

**`chain_check.py` makes the head and state comparisons below.** They used to be read by eye, and a
missed one merges commits nobody tested. Each subcommand reads `<pr>`, `<branch>` and `head_sha`
from the item's row itself, so it takes the notes path and the item's id, not a number or a branch:

```
python3 "${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/chain_check.py" <subcommand> --notes <run notes> --id <id>
```

`--notes` takes one file: this run's notes, whatever date its name carries. A resume keeps writing
to the file the run started; the skill's own file says how to find it. An older chain's file can
hold a row for the same id, so the script reads no other file and expands no glob. A relative path
is read from the primary clone. The run notes stay in the primary clone and are never written
inside a worktree. In a worktree pivot, run the command from the worktree holding `<branch>`, or
pass `--root <worktree>`: the git checks look at that checkout, and the notes path stays the same.

- Exit 0 → the check passed. The first line says what holds.
- Exit 1 → do not take the step it guards. The first line is `FAIL <subcommand>: <reason>`;
  `<reason>` is the item's reason, written exactly as printed.
- Exit 2 → it could not check: `gh` missing or failing, the remote not answering, or a run-notes
  row it cannot read. This is not a pass. Do not take the step; the reason is
  `chain check could not run: <first line>`. Do not run it again hoping for 0. Any other exit code
  (the script not found, say) counts as 2.

## Bootstrap (once, before the chain starts)

1. **Permissions.** Compare `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/required-permissions.json`
   with `.claude/settings.local.json`, as `/cla:spec-to-pr`'s "Bootstrap permissions" section does.
   Missing patterns → show them and apply on approval. This is the one ask outside the plan gate.
2. **Working tree.** Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py`.
   An in-progress op (exit 2) → resolve it per
   `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/conflict-resolution.md`. Any other non-zero
   exit halts. The script does not look at uncommitted files, so also run `git status --porcelain`:
   a dirty tree with paths outside this run → Step 2 of
   `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/precheck.md`. A dirty tree at the start
   poisons every later item.
3. **Run notes are ignored.** The skill's Phase 0 runs `git check-ignore` on its own notes file
   name. Non-zero → stop.
4. **Start on a clean, current `<base-branch>`, in the primary clone.** If HEAD is on another
   branch that carries local commits unrelated to this run, leave that branch alone. Then
   `git checkout <base-branch>`, then `git pull`. A failed pull halts
   the run: every item would branch off a stale base.

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

Whenever the skill the chain runs hands back an open PR, read its head with
`gh pr view <pr> --json headRefOid`. Write `branch`, `pr_number` and `head_sha` to the item's row
in the run notes. That is the first hand-back, and every later call to that skill on the same item,
since the skill may have pushed.

**Before calling the skill again on an item that already has a `head_sha`** (a resume), run
`python3 "${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/chain_check.py" resume --notes <run notes> --id <id> --base <base-branch>` first. Only `OK resume open` (exit 0, the PR
open on the recorded head) lets the skill run again. A different head means someone else pushed: do
not call the skill, and the reason is `head moved since review`, as exit 1 prints it. Its other
outcomes (`OK resume merged`, `PR closed without merging`, `recorded PR not found`, `not opened by
this chain`, `wrong base (<base>)`, `merged at a head this run did not check`, exit 2) also stop
the call; the skill's own resume step says what each means.

`head_sha` is the commit the item's review and full test gate must cover. **Between hand-backs,
nothing updates it except a fix the orchestrator itself commits to `<branch>`,** and only once all
three checks below pass. After the push, run
`python3 "${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/chain_check.py" fix-pushed --notes <run notes> --id <id>`, which makes them:

- `git rev-parse HEAD` must differ from the row's current `head_sha`. The same value means no commit was made (a hook rejected it, or nothing was staged).
- `git status --porcelain -- . ':(exclude)cla.io/retro'` must be empty. Anything listed is part of
  the fix that is not in the commit, which every later test would still see on disk.
- `git rev-parse HEAD` must equal `git ls-remote origin <branch>`.

The first two failing → the reason is `fix not committed`. The third failing → `push not verified`.
Exit 1 prints that reason; exit 2 is `chain check could not run: <first line>`. All three pass (exit 0) → write
the commit its first line names as the new `head_sha`.

A commit anyone else pushes — the user, a bot, another session — leaves `head_sha` behind, so the
pre-merge checks refuse that PR as `head moved`. **A resume never merges a moved head:** a PR whose
head differs from its recorded `head_sha` is left open as `head moved since review`, and one with no
recorded `head_sha` (the run notes were lost) as `head unverifiable (ledger lost)`. Both are the
user's to review and merge by hand.

## Pre-merge checks (every merge)

Run them in this order. The local gate runs before GitHub's merge state is read, because the gate
takes minutes and remote checks are usually still running right after a push. So a PR that turns
out `DIRTY` at step 5 has run the gate once already, and runs it again on the resolved tree; that
costs less than reading a merge state before the remote checks have settled. A skill may run checks
of its own before these.

1. **The PR is this chain's and open on the recorded head, and so is the checkout.** Run
   `python3 "${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/chain_check.py" before-merge --notes <run notes> --id <id> --base <base-branch>`. Exit 0 →
   continue. Exit 1 → do not merge; the reason is the one its first line prints. Exit 2 → do not
   merge; the reason is `chain check could not run: <first line>`. It checks, and names the first that fails:
   - The row records a `head_sha`. None → `head unverifiable (ledger lost)`.
   - The PR's head branch is `<branch>` on this repository, not a fork, since the chain only
     merges a PR it opened and recorded: otherwise `not opened by this chain`. Its base is
     `<base-branch>`: otherwise `wrong base (<base>)`.
     Known limitation: in a fork workflow (`gh` resolves PRs on an `upstream` remote while the
     branch is pushed to a fork), every PR reads as from a fork, so every merge stops as `not
     opened by this chain`. The chain does not support that layout; its PRs are left open for the
     user to merge by hand.
   - `state` must be `OPEN`, or the reason is `not open (state <state>)`. `headRefOid` must equal `head_sha`; a different head means commits nobody tested
     or reviewed here, so do not merge, and the reason is `head moved`. The remote's
     `refs/heads/<branch>` (`git ls-remote`) must equal `head_sha` too, for the same reason.
   - `git rev-parse HEAD` must equal `head_sha`, or the reason is `local head mismatch`.
   - `git status --porcelain -- . ':(exclude)cla.io/retro'` must be empty; anything listed would be tested by the gate below without being part of the merge, so do not merge; the reason is `uncommitted changes`.
2. **A local head mismatch gets one more try.** When the only `PROBLEM` line is `local-head`, run
   `git checkout <branch>`, then `git pull`, then step 1's command once more. Still not exit 0 → do
   not merge, with the reason it prints.
3. **The full Test gate is green on `head_sha`.** Every merge needs this, because review fixes are
   committed after the item's own Test phase. Run the full gate the skill names, from
   `cla.io/project-facts.md`. A green run this session on exactly `head_sha`, with the tree
   unchanged since, counts. Under `Full gate: final-commit-only` in `cla.io/project-facts.md`, the
   item's own Test phase ran smoke and touched tests only and then one full gate after Archive, and
   its Handoff Test row names that run's commit `<gated>` (`full gate: green|red on <gated>`), which
   change-loop step 3 recorded as `gated_sha` with its result in the item's run-notes row; read
   them from the notes, not from context. A missing record runs the gate. That run is reused, not
   repeated, when either holds:
   - `<gated>` equals `head_sha`; or
   - `git log --format=%s <gated>..<head_sha>` lists only `docs: TODO.md` and `chore: spec-to-pr run log`, each at most once, and `git diff --name-only <gated>..<head_sha>` names only `TODO.md` and the run-log path Handoff stages (`cla.io/retro/spec-to-pr-runs.jsonl`).

   The allowance for those two commits is void when the full gate may read `TODO.md` or the run log: a gate command in `cla.io/project-facts.md` that names `TODO.md`, a Markdown linter or a `*.md` glob, or a wrapper whose contents this step does not read (a `make` target, a script). Unknown means run the gate. A recorded red result means do not merge, and do not run the gate again. A non-zero exit from the `git log` or `git diff` above runs the gate. Any other case runs the gate here.
   - Green → continue.
   - Red → do not merge; the reason is `full gate red: <failing check>`. Do not re-run it hoping
     for green. A flaky gate is a finding for the user, not a retry.
   - `cla.io/project-facts.md` names no test commands and the PR changes source-affecting paths (as `/cla:lite-pr`'s Test phase defines them) → do not merge; the reason is `full gate unavailable`. A merge cannot treat this as a warning, because nothing would have tested the merged code.
   - The PR changes no source-affecting paths → nothing to gate. Record
     `gate skipped: no source-affecting paths` beside the status and continue.
4. **Remote checks have finished.** Run `gh pr checks <pr> --json name,bucket` and read the result
   in context:
   - JSON output → each check's `bucket` is `pass`, `fail`, `pending`, `skipping`, or `cancel`.
     - Any `pending` → in one message, start `gh pr checks <pr> --watch --interval 60` as
       `Bash(run_in_background: true)` and arm a 15-minute watchdog, `Bash(command: "python3 -c
       \"import time; time.sleep(900)\"", run_in_background: true)` (covered by the
       wildcards `Bash(gh *)` and `Bash(python3 *)` in `required-permissions.json`;
       `multi-lite/SKILL.md` "Never end a turn with nothing in flight" says why `python3`). Do
       not poll or loop: a completion notification wakes the session. When the watch's
       notification arrives first, read its exit code before anything else; the exit code only
       says the watch ended (it exits non-zero for a failing or still-pending check), so it is not
       `checks not readable` by itself. Query the JSON once more and take the arms here; still
       `pending` → the reason is `checks still pending`. When the watchdog's arrives first, stop
       waiting: the reason is `checks still pending`. The 15 minutes is the watchdog's, not the
       watch's: the watch has no deadline of its own. Ignore the other task's later notification
       (or stop it with `TaskStop`).
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
   - `CLEAN`, `HAS_HOOKS`, or `BEHIND` → proceed. `BEHIND` means the base gained commits after this branch was cut, so the merged tree was never tested as a whole. Squash applies onto the current base, so GitHub can still merge it; branch protection that requires an up-to-date branch reports `BLOCKED` instead. Record `behind base: merged tree not tested` beside the status so the skill's final report names it.
   - `DIRTY` → the reason is `conflicts`. Never rebase or force-push to clear it: that rewrites the
     code that was tested and reviewed. Whether to resolve it with a merge commit is the skill's
     call; its own file says.
   - `UNSTABLE` → the reason is `checks not green`.
   - `BLOCKED` → the reason is `blocked by branch protection`.
   - `DRAFT` → the reason is `draft`.
   - `UNKNOWN` → GitHub has not computed it yet. Wait once with
     `python3 -c "import time; time.sleep(15)"`, then query again. Still `UNKNOWN` → the reason is
     `mergeability unknown`.

## Merge, then confirm it landed

Each time a skill asks the user whether to merge a PR, the question names the base branch and the PR title.

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

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/chain_check.py" after-merge --notes <run notes> --id <id> --base <base-branch>`, which reads `gh pr view <pr>`. `state` must be `MERGED` (exit 0), into `<base-branch>` at `head_sha`: a merge of any other head or into any other base is not this run's merge, and exit 1 names it (`merged at a head this run did not check`, `wrong base (<base>)`). A merged PR with no merge commit exits 2. Otherwise:
   - `autoMergeRequest` is set (exit 1 prints this reason), or `gh pr merge` said it added the PR to a merge queue → the reason is `queued: merges later outside this run`. It is not merged now, so it does not count as merged; the skill's final report says plainly that it will merge on its own. Do not disable it: the repo chose it.
   - Anything else → the reason is `merge not confirmed (state <state>)`, as exit 1 prints it. Exit 2 → `chain check could not run: <first line>`, and the item does not count as merged.
2. `MERGED` is the fact. Write `status: merged` and `merge_commit: <the commit the first line names>` to the row now.
3. Bring the local base up to date. In the primary clone: `git checkout <base-branch>`, then
   `git pull`, then confirm `git log --oneline -1` shows `merge_commit`. In a worktree, which cannot
   check out `<base-branch>`: `git fetch origin <base-branch>`, then
   `git log --oneline -1 origin/<base-branch>`. A failure here is not a merge failure: record
   `base not updated` beside the merged status and continue. The next item pulls again before it
   starts, and **a pull that fails there halts the run**, since every later item would branch off a
   stale base.

**In a worktree, the local `<base-branch>` ref goes stale after every merge.** Compare and diff
against `origin/<base-branch>`, after a fetch, never the local ref; a stale ref silently pads a diff
with every earlier item's files.

**Leave the local feature branch.** No force or history-rewriting git mid-chain (`git branch -D`,
`git push --force`, `git reset --hard`): `ask-destructive-git.py` prompts on each, and an unattended
prompt stalls the chain until a human returns. `ALLOW_PR_MERGE=1` does not cover `branch -D`, by
design. Never set `ALLOW_DESTRUCTIVE_GIT=1` to get one through.

### If `gh pr merge` exits non-zero

Check the PR before reading the error: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/chain_check.py" after-merge --notes <run notes> --id <id> --base <base-branch>`.
Exit 1 with `merged at a head this run did not check`, `wrong base (<base>)` or `head unverifiable
(ledger lost)` → the PR merged, but not as this run checked it: that is the reason, and the arms
below do not apply. Exit 0 (`MERGED`)
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
