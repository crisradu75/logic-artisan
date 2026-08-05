# change-loop — Phase 3 per-change procedure + resume mechanics (full)

Phase 3's step-by-step procedure for driving each change to done-and-merged, plus the resume mechanics for re-invoking `/cla:multi-pr` after an interruption. `SKILL.md`'s Phase 3 stub carries the load-bearing invariants (Tier A/B split, no-unresolved-issues enforcement, merge-before-dependents authorization); this file carries the recipes.

## Per-change loop

For each change in the confirmed order:

1. **Resume check.** Before invoking `/cla:spec-to-pr`, check whether this change is already done: `openspec/changes/<name>/` no longer exists (archived) AND no open PR exists for `feature/<name>` (`gh pr list --head feature/<name> --state open`). If both hold, treat as already complete — mark its task done and skip to the next change. This makes a re-invoked `/cla:multi-pr` after an interruption resume correctly instead of re-running finished work.

2. **Capture a real start timestamp** — `date -u +%Y-%m-%dT%H:%M:%SZ` via Bash, a genuine wall-clock reading, not a guess — and record it against this change in the per-run running-notes file. Then **run `/cla:spec-to-pr` on this change**, passing through the Phase 1 caps: `Skill(cla:spec-to-pr, args="<name> --review-rounds N --pr-rounds N --test-rounds N")`. Let it run its full Propose → Review → Implement → Test → Ship → Revise → Archive → Handoff cycle uninterrupted — do not intervene mid-phase.

3. **Read the Handoff report.** Two failure tiers, handled differently:

   **Tier A — structural failure (halt the chain here).** Ship never opened a PR (branch collision, permission decline, push failure), Archive didn't reach the PR (the push-verification steps in `/cla:spec-to-pr`'s own Archive section failed), or `git_state` returned non-zero at any point and wasn't cleanly resolved. These mean the change isn't in a state later changes can safely depend on. Stop, surface the Handoff report and the specific failure to the user, and do not touch any later change in the sequence (their prerequisite isn't actually shipped). This is a real halt, not a "note and continue."

   **A halt still owes a full status enumeration.** Phase 4's cleanup pass never runs on this path, so the run's only terminal output is whatever this step prints — and "change 3 failed because X" silently leaves the reader to work out what happened to changes 1, 2, 4 and 5 from scrolled-back context. That is the failure mode where a partially-applied chain looks like a cleanly-stopped one. Before stopping, print every change in the planned sequence under exactly one of:

   - **Shipped** — PR number, and whether it merged (step 5 may or may not have run for it).
   - **Halted here** — this change, plus the specific structural failure and the branch/PR state it left behind, so the user knows what to clean up before re-invoking.
   - **Never attempted** — the changes after it, named. They are untouched: no branch, no PR, nothing to undo. Say so explicitly rather than leaving it inferable, because "untouched" is the fact that makes a re-invoked `/cla:multi-pr` safe to run.

   The ledger and `TaskUpdate` state already hold this; the point is that the terminal report has to carry it too, since nobody reads a task list to find out what a halted run did.

   **Tier B — content findings (fix, don't halt).** The Revise phase found Critical/Important issues and either applied or deferred them; Test needed retries; a review round exhausted its cap with residue. This is normal `/cla:spec-to-pr` operation — proceed to step 4.

4. **No-unresolved-issues enforcement (only under the strict Phase 1 policy).** If the Handoff report's "Deferred Known Issues" or "Deferred to TODO.md" sections are non-empty — under the full-severity default, this includes Suggestion-level residue, not just Critical/Important — don't accept that as final:
   - For each deferred finding (any severity, under the full-severity policy), actually fix it: read the finding, make the Edit, and re-verify narrowly (re-run the specific test/check the finding was about, not the whole suite yet).
   - Stage and commit the fix on the **same feature branch** (`fix: resolve deferred findings`, following `/cla:spec-to-pr`'s own commit-message-shape convention), after the standard `git_state` check.
   - Re-run the change's full gate (this repo's own build/lint/test commands — see `cla.io/project-facts.md`, falling back to `references/project-context.md` if absent — plus its local-infra-dependent hard gate if the change touches the tables/surfaces it covers) before considering the change done.
   - Prefer landing the fix on the still-open PR over opening a second one when the branch is still live — the original PR hasn't merged yet, so a small follow-up commit on the same branch is simpler than a retroactive fix-PR.
   - **If the change has ALREADY MERGED** by the time a deferred finding needs fixing (e.g. the policy was clarified or tightened mid-chain, after an earlier change's PR was merged under the looser default), do NOT push directly to `<base-branch>` — check for a `block-direct-push-to-main.py`-style hook first, and if the repo has one (or on general principle), open a small follow-up branch + PR + merge instead (`fix/<original-change-name>-review-followups` or similar), going through the same full gate (build/lint/test + any local-infra hard gate) before merging it. This is a real, encountered scenario, not a hypothetical.
   - If a deferred finding turns out to be genuinely out of scope for this change (would require a design change, or belongs to a different change entirely), that's a legitimate exception — but it needs the same "surface to the user, don't silently accept" treatment as a Tier A failure, since the strict policy was explicitly requested. Don't unilaterally downgrade back to "deferred is fine."

5. **Merge (only under the "merge before dependents" policy).** Once the change is genuinely done (Tier A clean, Tier B findings resolved per step 4):
   ```
   gh pr merge <#> --squash --delete-branch
   ```
   **Verification branches on whether THIS worktree holds `<base-branch>`/`main`.** `gh pr merge --delete-branch` performs the remote merge first, then tries to switch the *local* checkout to the base branch and delete the local copy of the feature branch:
   - **If this worktree holds `<base-branch>`/`main`** (the primary clone, or a worktree that legitimately checked it out): the local-checkout switch succeeds. Sync it with two separate commands (not chained with `&&`, per the inherited bash-discipline rule):
     ```
     git checkout <base-branch>
     git pull
     ```
     then confirm `git log --oneline -1` shows the merged commit.
   - **If it does not** (the normal case for a chain run inside a dedicated feature-branch worktree — the usual shape this skill runs in): that second step fails with `fatal: '<base-branch>' is already used by worktree at <primary-clone-path>`. **The remote merge itself already succeeded** — don't treat this error as a failed merge, and don't attempt the `git checkout <base-branch>` / `git log -1` steps above (they don't apply in this worktree). Skip straight to the verification below.

   **Authoritative verification (either path):** `gh pr view <#> --json state,mergedAt` — state `MERGED` confirms the merge landed regardless of which branch this arrives from. In the second case above, if the remote feature branch wasn't deleted as part of that failed local-switch step, delete it explicitly: `git push origin --delete feature/<change-name>`. This repeats on every merge in a chain run from a worktree, so expect it rather than re-diagnosing each time. Only after this verification passes should the change's task be marked complete.

   **Local `<base-branch>`/`main` is never auto-updated by a sibling worktree's merge.** In a worktree that doesn't hold `<base-branch>`/`main` (the second case above), this worktree's local base-branch ref goes stale the moment ANY merge happens — including this chain's own earlier merges — since there's no `git checkout <base-branch> && git pull` step to refresh it. Any later diff-scoping command in this run (e.g. Revise's `git diff <base-branch>..HEAD` for a *subsequent* change in the chain) MUST target `origin/<base-branch>` (after an explicit `git fetch origin <base-branch>`), never the local `<base-branch>`/`main` ref — a stale local ref silently produces a diff padded with every prior change's own files. Confirmed in practice via an ad hoc file-count sanity check against the expected total, but no such check is built into this skill — treat "target `origin/<base-branch>`, always" as the actual safeguard, not the possibility of noticing the padding after the fact.

6. **Capture a real end timestamp** — `date -u +%Y-%m-%dT%H:%M:%SZ` via Bash — closing the window opened in step 2. This spans the change's full per-change loop (the `/cla:spec-to-pr` run, any step 4 fix round, and the step 5 merge), i.e. genuine measured wall-clock for everything this change actually cost, not just its `/cla:spec-to-pr` sub-call. Record the delta in the per-run running-notes file next to the Phase 1c prediction for this change. Mark the change's `TaskCreate` entry `completed`.

7. **Report the actual wall-clock this change took against its Phase 1c prediction, then a revised ballpark for the rest of the chain.** This is a long unattended run and the user has no other way to gauge progress or remaining time. Keep it rough — a ballpark is the goal, not a precise forecast.
   - State the measured minutes (step 6's timestamp minus step 2's) against the Phase 1c predicted minutes for this change's complexity bucket, e.g. "operator-x: 72 min actual vs ~90 min predicted (large-extend)."
   - Restate the remaining-chain estimate as a range. If the run is trending clearly faster or slower than its Phase 1c predictions across the changes done so far, nudge the remaining estimate in that direction — no need for a precise per-change ratio recomputation, just don't keep quoting an upfront number the run has visibly diverged from (e.g. "the run's been running ~20% ahead, so the last change is likely ~65–80 min rather than its ~90 min prediction"). Refresh it after each subsequent change.

Move to the next change in the sequence.

## Resume behavior

Re-invoking `/cla:multi-pr` (same arguments, or empty for auto-discover) after an interruption should pick up cleanly:
- Phase 1's discovery naturally excludes already-archived changes (they're no longer under `openspec/changes/`).
- Phase 3 step 1's resume check catches a change that's mid-flight (branch/PR exists, not yet archived) and hands it back to `/cla:spec-to-pr`, which has its own implicit-resume-via-probe behavior (see `/cla:spec-to-pr`'s "Resume / dry-run" section) — `multi-pr` doesn't need to duplicate that, just re-invoke `Skill(cla:spec-to-pr, args="<name> ...")` again and let it figure out where it left off.
- Skip Phase 1's `AskUserQuestion` gate only if this is a genuine same-session resume (the user hasn't left and come back to a fresh session) — a fresh session re-asks, since a fresh session has no way to know what the previous one decided.
