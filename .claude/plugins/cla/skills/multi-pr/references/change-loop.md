# change-loop — Phase 3 per-change procedure + resume mechanics (full)

Phase 3's step-by-step procedure for driving each change to done-and-merged, plus the resume mechanics for re-invoking `/cla:multi-pr` after an interruption. `SKILL.md`'s Phase 3 stub carries the load-bearing invariants (Tier A/B split, no-unresolved-issues enforcement, merge-before-dependents authorization); this file carries the recipes.

## Per-change loop

For each change in the confirmed order:

1. **Resume check.** Before invoking `/cla:spec-to-pr`, check whether this change is already done. Under the merge policies: `openspec/changes/<name>/` no longer exists (archived) AND no open PR exists for `<branch>` (`gh pr list --head <branch> --state open`). **Under the stacked policy a correctly completed change KEEPS its open PR** — there, done = archived AND its open PR's base is its parent's branch (its root's base is `<base-branch>`); an open PR is the expected end state, not unfinished work. If done, mark its task complete and skip to the next change. This makes a re-invoked `/cla:multi-pr` after an interruption resume correctly instead of re-running finished work — and on any stacked-policy resume, read the running notes for the recorded parent branches and PR numbers before starting anything.

2. **Capture a real start timestamp** — `date -u +%Y-%m-%dT%H:%M:%SZ` via Bash, a genuine wall-clock reading, not a guess — and record it against this change in the per-run running-notes file. Then **run `/cla:spec-to-pr` on this change**, passing through the Phase 1 caps: `Skill(cla:spec-to-pr, args="<name> --review-rounds N --pr-rounds N --test-rounds N")`. Let it run its full Propose → Review → Implement → Test → Ship → Revise → Archive → Handoff cycle uninterrupted — do not intervene mid-phase.

   **Inherited-obligation clause.** Before invoking, collect the `## Carried obligations` rows whose *owed by* column names THIS change — **and the `## Capability re-base` rows naming this change**, which Phase 1 writes for every change carrying a `## MODIFIED Requirements` block (`references/discover-and-gate.md` §1a). Both kinds travel the same way and for the same reason: the review that must act on them runs inside the `Skill(cla:spec-to-pr, …)` call below, hours after the row was written and from a reference file that is closed by then. **Read EVERY running-notes file, not just this run's** — `ls cla.io/retro/multi-pr-run-notes-*.md` and grep the set, because the notes file is dated and a chain resumed on a later date writes a NEW one: scoping the read to today's file makes every obligation a previous session recorded invisible, which is precisely the resume path the mechanism exists to survive. A change name is unique across `openspec/changes/`, so selecting by *owed by* cannot pick up a same-named row from an unrelated chain, and rows owed by already-finished changes are simply never selected.

   Each row becomes one `<token> — <failure>` entry, and they go into the invocation as a single argument: `Skill(cla:spec-to-pr, args="<name> --inherits '<entry>; <entry>' --review-rounds N --pr-rounds N --test-rounds N")` (`<inherits>` per `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/SKILL.md`; it composes with `--pr-base`, and a stacked child passes both — see the stacked clause's own example). No rows owed by this change → omit the flag entirely; the section reading `none` for every prior change is a legitimate and common state. **This is the only place anything reads those rows back, and reading them back is the entire mechanism** — step 4a writes them, and a row written but never turned into a flag has bought nothing over not writing it. Done is countable: the number of `;`-separated entries equals the number of rows owed by this change, and step 3 below counts the verdict lines that come back against it.

   **Stacked clause** (its example carries `--inherits` too — a stacked child is the commonest case for inheriting one, since its parent is still open and its own fix rounds are the freshest). Under the stacked policy, when this change depends on a prior change in this chain — including an archived-but-unmerged parent surfaced by the Phase 1 prerequisite check, which counts as in-chain for parenting: FIRST `git checkout <parent-branch>` (the branch the parent's step 5-alt recorded in the running notes — this is what puts HEAD where Ship's preflight expects it, including on a fresh-session resume), record the parent's tip sha alongside it (`git rev-parse <parent-branch>` — the squash-alternative landing needs it), THEN invoke with the flag appended: `Skill(cla:spec-to-pr, args="<name> --pr-base <parent-branch> --inherits '<entry>; <entry>' --review-rounds N --pr-rounds N --test-rounds N")` (drop `--inherits` when no row is owed by this change). An independent change (no parent in this chain) omits the flag — and when the previous change left HEAD on ANY feature branch (stacked or not), FIRST re-position it, or Ship's preflight fails loudly on "any other branch". In the primary clone: `git checkout <base-branch>`. In a dedicated worktree that checkout fails (the primary clone holds `<base-branch>` — see step 5's note), so cut the change's branch directly instead: `git fetch origin <base-branch>`, then `git checkout -b <branch> origin/<base-branch>` (`<branch>` per spec-to-pr's own resolution); Ship's preflight then takes its "already on `<branch>`" arm.

3. **Read the Handoff report.** Two failure tiers, handled differently:

   **Tier A — structural failure (halt the chain here).** Ship never opened a PR (branch collision, permission decline, push failure), Archive didn't reach the PR (the push-verification steps in `/cla:spec-to-pr`'s own Archive section failed), or `git_state` returned non-zero at any point and wasn't cleanly resolved. These mean the change isn't in a state later changes can safely depend on. Stop, surface the Handoff report and the specific failure to the user, and do not touch any later change in the sequence (their prerequisite isn't actually shipped). This is a real halt, not a "note and continue."

   **A halt still owes a full status enumeration.** Phase 4's cleanup pass never runs on this path, so the run's only terminal output is whatever this step prints — and "change 3 failed because X" silently leaves the reader to work out what happened to changes 1, 2, 4 and 5 from scrolled-back context. That is the failure mode where a partially-applied chain looks like a cleanly-stopped one. Before stopping, print every change in the planned sequence under exactly one of:

   - **Shipped** — PR number, and whether it merged (step 5 may or may not have run for it).
   - **Halted here** — this change, plus the specific structural failure and the branch/PR state it left behind, so the user knows what to clean up before re-invoking.
   - **Never attempted** — the changes after it, named. They are untouched: no branch, no PR, nothing to undo. Say so explicitly rather than leaving it inferable, because "untouched" is the fact that makes a re-invoked `/cla:multi-pr` safe to run.
   - **Outstanding obligations** — every `## Carried obligations` row whose owed-by change is in the "never attempted" list, reprinted here in full. A halt is exactly the state a re-invoke loses context in, and these rows are the one piece of chain state a shipped PR does not carry: the changes that owe them have not started, so nothing else names them. Reprinting costs a line each and makes the re-invoke's step 2 verifiable against the terminal output rather than only against a dated file.

   The ledger and `TaskUpdate` state already hold this; the point is that the terminal report has to carry it too, since nobody reads a task list to find out what a halted run did.

   **Tier B — content findings (fix, don't halt).** The Revise phase found Critical/Important issues and either applied or deferred them; Test needed retries; a review round exhausted its cap with residue. This is normal `/cla:spec-to-pr` operation — proceed to step 4.

   **Count the inherited-obligation verdict lines against the entries you passed.** When step 2 passed `--inherits`, the Handoff report carries one `HONOURED / VIOLATED / NOT ADDRESSED` line per entry. **Fewer lines than entries is a Tier B finding, not a pass** — it means the run did not answer for an obligation, whatever else it reported, and it is the only signal on this side that distinguishes a run that answered every obligation from one that dropped the flag on the floor. Resolve it through step 4's fix machinery: re-run the change with the same `--inherits` (the "Resume / dry-run" rule makes the checklist's Step 2b unconditional, so a re-invocation answers even when the probe skips Review), then fix each non-`HONOURED` entry. A `VIOLATED`/`NOT ADDRESSED` line that `/cla:spec-to-pr` already applied as a Critical needs nothing further here — it is the *missing* line, not the failed verdict, that this check exists for.

4. **No-unresolved-issues enforcement (only under the strict Phase 1 policy).** If the Handoff report's "Deferred Known Issues" or "Deferred to TODO.md" sections are non-empty — under the full-severity default, this includes Suggestion-level residue, not just Critical/Important — don't accept that as final:
   - For each deferred finding (any severity, under the full-severity policy), actually fix it: read the finding, make the Edit, and re-verify narrowly (re-run the specific test/check the finding was about, not the whole suite yet).
   - Stage and commit the fix on the **same feature branch** (`fix: resolve deferred findings`, following `/cla:spec-to-pr`'s own commit-message-shape convention), after the standard `git_state` check.
   - Re-run the change's full gate (this repo's own build/lint/test commands — see `cla.io/project-facts.md`, falling back to `cla.io/overlays/multi-pr.md` if absent — plus its local-infra-dependent hard gate if the change touches the tables/surfaces it covers) before considering the change done.
   - Prefer landing the fix on the still-open PR over opening a second one when the branch is still live — the original PR hasn't merged yet, so a small follow-up commit on the same branch is simpler than a retroactive fix-PR.
   - **If the change has ALREADY MERGED** by the time a deferred finding needs fixing (e.g. the policy was clarified or tightened mid-chain, after an earlier change's PR was merged under the looser default), do NOT push directly to `<base-branch>` — check for a push-to-main guard first (`.git/hooks/pre-push`, or an equivalent the repo ships), and if the repo has one (or on general principle), open a small follow-up branch + PR + merge instead (`fix/<original-change-name>-review-followups` or similar), going through the same full gate (build/lint/test + any local-infra hard gate) before merging it. This is a real, encountered scenario, not a hypothetical.
   - If a deferred finding turns out to be genuinely out of scope for this change (would require a design change, or belongs to a different change entirely), that's a legitimate exception — but it needs the same "surface to the user, don't silently accept" treatment as a Tier A failure, since the strict policy was explicitly requested. Don't unilaterally downgrade back to "deferred is fine."

4a. **Record the obligations this change creates for later changes in the chain.** Runs once per change, after step 4 and before step 5/5-alt, so it sees the change as it FINALLY is.

   **Derive from what the change became, not from what it proposed.** The proposal predates the change's own Review and step-4 fix rounds, and those rounds are exactly where these obligations get created — a chain that reads the batch as proposed is reading a snapshot that went stale the moment any prerequisite's review round touched it. Three sources, all cheap and already in hand:
   - the Critical/Important findings this change's Review and Revise rounds actually applied — any that ADDED a stored field, column, response key, or required behaviour;
   - the change's final diff, `git diff origin/<pr-base>...HEAD --stat`, read only for the files it names that this change added persisted state or a response shape to;
   - **every finding step 4 set aside as "genuinely out of scope for this change — belongs to a different change entirely".** This source is easy to omit and is the most explicit obligation the run produces: such a finding *names the downstream change by hand*, which is more than the other two sources ever give you. It is also invisible to both of them by construction — it was not applied, so it is in no findings-applied list, and it changed nothing, so it leaves no diff. A run that surfaces one of these and does not write a row here has discarded the clearest obligation it had.

   An obligation is any such addition **this change does not itself consume** — its whole justification is that a later change reads it, which is why it is invisible to every check scoped to one change. For each, append a row under a `## Carried obligations` heading in the per-run running-notes file:

   ```
   | <grep token> | created by <this change> | owed by <downstream change> | <the one-line failure if it is dropped> |
   ```

   Three rules the row has to satisfy, each because the alternative has been observed to fail:
   - **The token is a literal string a later `grep` will match** — the field name as it is spelled in code, not a description of it. The obligation's only prior home was a source comment, which no per-change check reads.
   - **Name the downstream change explicitly.** If the consumer is "whoever ships the UI", this mechanism cannot carry it: either name the change or do not write the row.
   - **Zero obligations is a real answer, and it is written as the DERIVATION, never the bare word.** `none` on its own is satisfiable by typing it, and this whole step exists because "nobody noticed" is cheap — a bare `none` just renames that failure. Write the counts the three sources produced, each with the command behind it:

     ```
     | none | <this change> | — | derived from <A> applied Critical/Important findings, <B> file(s) in `git diff origin/<pr-base>...HEAD --name-only`, <C> out-of-scope deferrals |
     ```

     `<B>` is a command's output, not an estimate, so `none` beside `<B> = 0` on a change that plainly shipped code is visibly false to the next reader — which is the whole difference between a claim and a word. A genuine `none` on a real change is normal and common: most changes add no state anyone else must read.

   Done when the running notes' `## Carried obligations` section names this change, either with ≥1 row or with a counted `none`. The rows are read back at step 2 of every later change that owes one, and reprinted in step 3's halt enumeration when the chain stops before those changes start.

5-alt. **Stack (only under the "stacked" policy — replaces step 5; steps 6-7 still run for this change).** No merge happens from the point this policy is in force. Once the change is genuinely done (same bar as step 5):
   - Record this change's feature branch name and PR number in the running notes — the NEXT dependent's step 2 reads the branch from there, and the landing checklist needs the number.
   - Do NOT invoke the next change here. The loop's own step 2 starts it, carrying `--pr-base` per its stacked clause — steps 6-7 run for THIS change first, in order.
   - Do NOT delete or rebase any branch in the stack mid-run — every later PR's base points at it. (Rebasing IS part of landing under the squash alternative below: at landing time, by the user, never mid-run.)
   - An independent change (no parent in this chain) still branches off `<base-branch>` normally — stacking is for dependency edges, not a house style, so a chain can be a forest: several stacks plus independents.
   - **Landing (the user's, at the end — Phase 4 hands over the checklist).** Parents first, retarget-first, merge commits. Per parent, two commands in this order: `gh pr edit <child> --base <base-branch>` FIRST, then `gh pr merge <#> --merge --delete-branch`. Do NOT rely on GitHub's documented auto-retargeting: `gh`'s `--delete-branch` deletion CLOSED a dependent PR before any retarget in a live landing (see the dated incident in `cla.io/overlays/multi-pr.md`; recovery took restoring the deleted base from the merge commit's second parent). Retargeting the child first makes the deletion close nothing. The merge STRATEGY matters equally: a **merge commit, never a squash** — squash-merging a stacked parent rewrites its commits, so a surviving child re-shows the parent's entire diff and its own merge conflicts, measured on a throwaway 3-deep stack. With a merge commit each child's diff collapses to its own work the moment its parent lands. If the repo requires squash-merges: after each parent lands, rebase its child before merging it — `git rebase --onto origin/<base-branch> <parent-tip-sha> <child-branch>` then `git push --force-with-lease` — using the parent tip sha step 2 recorded.

4b. **Validate the live spec set — BEFORE the merge, not after.**

   ```
   openspec validate --specs --strict
   ```

   Placement is the whole point. `/cla:spec-to-pr`'s own Archive already validated at its commit, so this exists to cover the two windows that open *after* it returns: step 4's deferred-finding fix rounds, and any hand-resolved merge conflict in a materialized spec — which is a documented occurrence in this plugin, and is exactly the hand-edit this check is about.

   Run it here, while **the branch is alive and the PR is open**. Step 5 merges with `--delete-branch`; a check placed after it would report a broken base branch and a branch that no longer exists to fix it on. Under step 5-alt (stacked) nothing has merged either way, so the same placement works for both policies.

   Reading the result — the exit code alone conflates three outcomes:

   - **`✗ spec/<cap>` in the output** → this change left the live spec set broken. **Tier A structural failure** (step 3): halt the chain. A chain is where this compounds — the next change starts from these specs, and *its* archive is what aborts, one whole change from the cause. Fix on this change's still-open branch and re-verify before step 5.
   - **Non-zero with no `✗` line** (`command not found`, `unknown option`) → the check could not run. A **tooling fault**, not a spec fault; halting a six-change chain and reporting "this change broke the live spec set" when the real fix is a `PATH` entry sends an absent user to the wrong subsystem entirely.
   - **`No items found to validate.`** → exit 0 and nothing checked. **Not a pass.** Confirm the `Totals:` line names at least one item; in a repo not using OpenSpec, say so once and skip rather than recording a vacuous success.

   This is the live set's **parse integrity after any edit**, including edits that never touch a delta — the measured instance was a hand-filled TBD `## Purpose`, with no delta involved. It is not the same check as diffing a `## MODIFIED Requirements` block against the live spec for silently dropped scenarios, which is a separate concern.

5. **Merge (only under the "merge before dependents" policy).** Once the change is genuinely done (Tier A clean, Tier B findings resolved per step 4, live spec set clean per step 4b):
   ```
   ALLOW_PR_MERGE=1 gh pr merge <#> --squash --delete-branch
   ```
   **The `ALLOW_PR_MERGE=1` prefix is required, and belongs on this command
   only.** `ask-destructive-git.py` prompts for confirmation on every
   `gh pr merge`, because a hook cannot tell an authorized merge from one the
   agent assumed — a real failure that shipped two unrequested merges. This
   chain is the legitimate exception: the user confirmed the whole plan,
   including this dependency edge, in Phase 1, and the run is unattended by
   design, so a prompt here would simply hang. Use the narrow variable, NOT
   `ALLOW_DESTRUCTIVE_GIT=1` — that one would also disarm the force-push,
   `reset --hard` and branch-force-delete checks for the same command. Do not
   export either; prefixing the single command is what keeps the exception
   scoped to it.
   **Verification branches on whether THIS worktree holds `<base-branch>`/`main`.** `gh pr merge --delete-branch` performs the remote merge first, then tries to switch the *local* checkout to the base branch and delete the local copy of the feature branch:
   - **If this worktree holds `<base-branch>`/`main`** (the primary clone, or a worktree that legitimately checked it out): the local-checkout switch succeeds. Sync it with two separate commands (not chained with `&&`, per the inherited bash-discipline rule):
     ```
     git checkout <base-branch>
     git pull
     ```
     then confirm `git log --oneline -1` shows the merged commit.
   - **If it does not** (the normal case for a chain run inside a dedicated feature-branch worktree — the usual shape this skill runs in): that second step fails with `fatal: '<base-branch>' is already used by worktree at <primary-clone-path>`. **The remote merge itself already succeeded** — don't treat this error as a failed merge, and don't attempt the `git checkout <base-branch>` / `git log -1` steps above (they don't apply in this worktree). Skip straight to the verification below.

   **Authoritative verification (either path):** `gh pr view <#> --json state,mergedAt` — state `MERGED` confirms the merge landed regardless of which branch this arrives from. In the second case above, if the remote feature branch wasn't deleted as part of that failed local-switch step, delete it explicitly: `git push origin --delete <branch>`. This repeats on every merge in a chain run from a worktree, so expect it rather than re-diagnosing each time. Only after this verification passes should the change's task be marked complete.

   **Local `<base-branch>`/`main` is never auto-updated by a sibling worktree's merge.** In a worktree that doesn't hold `<base-branch>`/`main` (the second case above), this worktree's local base-branch ref goes stale the moment ANY merge happens — including this chain's own earlier merges — since there's no `git checkout <base-branch> && git pull` step to refresh it. Any later diff-scoping command in this run (e.g. Revise's `git diff <base-branch>..HEAD` for a *subsequent* change in the chain) MUST target `origin/<base-branch>` (after an explicit `git fetch origin <base-branch>`), never the local `<base-branch>`/`main` ref — a stale local ref silently produces a diff padded with every prior change's own files. Confirmed in practice via an ad hoc file-count sanity check against the expected total, but no such check is built into this skill — treat "target `origin/<base-branch>`, always" as the actual safeguard, not the possibility of noticing the padding after the fact. **Stacked-child exception:** a stacked child's diff anchor is its `<pr-base>`, per spec-to-pr's `<pr-base>` rule — there the safeguard reads "target `origin/<pr-base>`, after `git fetch origin <pr-base>`"; anchoring a stacked child to `origin/<base-branch>` produces exactly the padded diff this rule exists to prevent.

6. **Capture a real end timestamp** — `date -u +%Y-%m-%dT%H:%M:%SZ` via Bash — closing the window opened in step 2. This spans the change's full per-change loop (the `/cla:spec-to-pr` run, any step 4 fix round, and step 5's merge or step 5-alt's bookkeeping), i.e. genuine measured wall-clock for everything this change actually cost, not just its `/cla:spec-to-pr` sub-call. Record the delta in the per-run running-notes file next to the Phase 1c prediction for this change. Mark the change's `TaskCreate` entry `completed`.

7. **Report the actual wall-clock this change took against its Phase 1c prediction, then a revised ballpark for the rest of the chain.** This is a long unattended run and the user has no other way to gauge progress or remaining time. Keep it rough — a ballpark is the goal, not a precise forecast.
   - State the measured minutes (step 6's timestamp minus step 2's) against the Phase 1c predicted minutes for this change's complexity bucket, e.g. "operator-x: 72 min actual vs ~90 min predicted (large-extend)."
   - Restate the remaining-chain estimate as a range. If the run is trending clearly faster or slower than its Phase 1c predictions across the changes done so far, nudge the remaining estimate in that direction — no need for a precise per-change ratio recomputation, just don't keep quoting an upfront number the run has visibly diverged from (e.g. "the run's been running ~20% ahead, so the last change is likely ~65–80 min rather than its ~90 min prediction"). Refresh it after each subsequent change.

Move to the next change in the sequence — **in the same message as step 7's report.**

This seam is where the chain has been measured to die. Step 7 produces a natural closing shape (a
finished change, a wall-clock figure, a revised estimate), and a well-written status report reads as
a legitimate place to stop even though nothing is blocked and nobody is waiting on input. It is not
a pause: an idle turn has no pending event to re-invoke the session, so the chain stops until a
human notices. One six-change chain lost ~4.5 hours here with 4 of 6 changes unstarted, its closing
line being "Starting change 3: …".

The hoisted turn-liveness rule in `SKILL.md` binds here, and is restated because this is exactly the
point at which that file has been closed and the orchestrator is running on the `SKILL.md` summary.
Mechanically: step 7's report and the next change's step-1 resume check go **in the same message**.
If there is no tool call to pair the report with, the change is not over. The test is whether a
**pending event** will re-invoke this session, not whether you asked the user anything — announcing
the next change **is not a mechanism**, while a backgrounded dispatch, the next
`Skill(cla:spec-to-pr, …)` call itself, or a watchdog armed before the message ends all are.

## Resume behavior

Re-invoking `/cla:multi-pr` (same arguments, or empty for auto-discover) after an interruption should pick up cleanly:
- Phase 1's discovery naturally excludes already-archived changes (they're no longer under `openspec/changes/`).
- Phase 3 step 1's resume check catches a change that's mid-flight (branch/PR exists, not yet archived) and hands it back to `/cla:spec-to-pr`, which has its own implicit-resume-via-probe behavior (see `/cla:spec-to-pr`'s "Resume / dry-run" section) — `multi-pr` doesn't need to duplicate that, just re-invoke `Skill(cla:spec-to-pr, args="<name> ...")` again and let it figure out where it left off. **Re-build `--inherits` from step 2's clause on every such re-invocation, including this one** — a resumed change is the case the obligations matter most in and the case the flag is most easily dropped from, since the invocation is being retyped from a summary rather than composed by step 2. `/cla:spec-to-pr` answers the entries even when its probe skips Review (its "Resume / dry-run" section makes the checklist's Step 2b unconditional), so passing the flag on a resume is never wasted.
- Skip Phase 1's `AskUserQuestion` gate only if this is a genuine same-session resume (the user hasn't left and come back to a fresh session) — a fresh session re-asks, since a fresh session has no way to know what the previous one decided.
