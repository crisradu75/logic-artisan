# candidate-loop — Phase 3's 8-step per-candidate procedure + resume mechanics (full mechanics)

The Phase 3 step-by-step procedure. `SKILL.md`'s Phase 3 stub carries the load-bearing invariants (merge-authorization scope, downstream-only quarantine, the review-enforcement boundary, ledger-keyed identifier capture — all stated in the hoisted rules); this file carries the 8-step recipe and the resume behavior it enables.

For each candidate in the confirmed order:

1. **Skip if quarantined.** If any candidate in this one's `depends_on` (transitively) was quarantined earlier in this run, skip it too — mark it `blocked-by-upstream-failure` (in both the task and the run-notes ledger) and record which upstream failed. Don't run a candidate on a base its dependency never landed on.

2. **Resume check (keyed off the run-notes ledger, not a guess).** Look this candidate up in `cla.io/retro/multi-lite-run-notes-<date>.md`. If it has a recorded `branch`/`pr_number` from an earlier pass, confirm its real state with `gh pr list --state all --head <recorded-branch>` (use `--state all`, not the default open-only — a merged dependency's branch was deleted by `--delete-branch` and its PR won't show as open). Then decide from the PR state plus the ledger row:
   - **Merged** → done. Mark the task complete and skip.
   - **Open, and the row's `status` is already `open` (with or without a reason)** → step 8 already left it open on purpose. Done; skip.
   - **Open, `status` is `failed-merge`** → its downstream subtree is waiting on this merge, and the cause may be gone (the user resolved a conflict, or this session's host allows merges). Re-enter at step 8; its checks run again from scratch.
   - **Open, `review` empty** → the run stopped during or before step 7. Re-enter at step 7 for this candidate.
   - **Open, `review` is `clean`, no final `status`** → the run stopped between step 7 and step 8. Re-enter at step 8. Under `merge-dependencies-only` for an independent candidate, step 8 only records `open`.
   - **Open, `review` is `unresolved`** → re-enter at step 7's unresolved branch, which records the flag or quarantine; never merge it.

   Resuming into step 7 or 8 first checks out the recorded branch — never `<base-branch>` — because the PR's commits live there. Only when there is **no** recorded identifier for this candidate (a fresh session whose notes file was lost) fall back to a best-effort title match, and say so — this arm is explicitly weaker because `multi-lite` can't reconstruct `commit-push-pr`'s branch name.

3. **Ensure the right base.** `git checkout <base-branch>`, then `git status --porcelain` (empty = clean) before running. Under either policy, every candidate in this one's `depends_on` must already be merged into `<base-branch>` before it runs (step 8 below does that merge as the chain reaches each dependency) — so a dependent candidate branches off a `<base-branch>` that actually contains its prerequisites. (In a reactive-worktree pivot, substitute the `origin/<base-branch>`-based worktree idiom from the hoisted rule for the `git checkout <base-branch>` here.)

4. **Run `/cla:lite-pr` on the candidate:** `Skill(cla:lite-pr, args="<one-line description>")`. Let it run its full Explore→Plan→Implement→Test→Ship→Review cycle uninterrupted — do not intervene mid-phase. **Descriptions must be concrete enough that `/cla:lite-pr`'s optional Explore phase auto-skips** — Phase 1a already requires this. Never let a candidate enter `/cla:lite-pr`'s interactive `Skill(shape-decision)` Q&A during an unattended chain: an under-specified candidate that triggers Explore would block the whole run waiting on input. If a candidate genuinely needs shaping, that's a Phase 1 signal it isn't lite-ready — route it out of scope rather than discovering it here.

5. **Classify the outcome.**
   - **Test-phase halt (hard failure — never opened a PR).** `/cla:lite-pr` stopped at its one deliberate halt (an unresolved Test failure). Mark this candidate `failed`, mark everything transitively downstream `blocked-by-upstream-failure`, record the failing check, and **continue with the next independent candidate**.
   - **PR opened.** A PR being open does **not** yet mean the candidate is clean — proceed to step 6.

6. **Capture the real identifiers immediately (this is what makes resume/merge deterministic).** From `/cla:lite-pr`'s ship report, read the concrete **branch name** and **PR number** it just opened, then read the PR's head commit with `gh pr view <pr-number> --json headRefOid`. Write all three into this candidate's row in the run-notes ledger as `branch`, `pr_number`, and `head_sha`. Every later step that needs to act on this PR (step 8's merge, a resume in step 2) keys off these recorded values — never a re-derived branch name or an "in-context" PR number.

7. **Enforce `/cla:lite-pr`'s deferred review findings (the thin layer it doesn't do itself).** `/cla:lite-pr` opens the PR even when its Review phase *defers* Critical/Important findings — it never halts on them, and it has already spent its own single fix round before deferring. Read its final report:
   - **No deferred Critical/Important findings** → the candidate is clean. Write `review: clean` to its ledger row and go to step 8.
   - **One or more deferred Critical/Important findings** → run **one additional enforcement round** on exactly those deferred findings (this is a round *on top of* `lite-pr`'s own already-spent one — not a re-run of it, and not a loop). For each finding: read it, apply the `Edit`, then re-run the narrow gate the finding was about plus the changed-file tests. Commit path-scoped (`fix: resolve deferred review findings`) after a `git_state.py` check, and push to the captured branch. **Verify the push landed** — `git rev-parse HEAD` vs `git ls-remote origin <captured-branch>`, compared in-context (not piped through `grep`/`awk`); a mismatch halts this candidate and surfaces to the user rather than proceeding as if the fix shipped. On a match, update the row's `head_sha` to that pushed commit.
     - **Resolved by that round** → **re-run `/cla:lite-pr`'s full Test gate before calling it clean** — smoke then full, the commands `/cla:lite-pr`'s Test phase reads from `cla.io/project-facts.md`. The round above re-ran only the narrow gate and the changed-file tests. That is enough to leave a PR open, but step 8 may now merge it, and this repo's local gate is the only one a merge passes. Green → write `review: clean` and go to step 8. Red → treat the finding as still unresolved (next bullet), and name the failing check.
     - **Still unresolved after the round (or genuinely out of scope)** → write `review: unresolved`. Never treat it as silently clean, and **never merge a candidate carrying an unresolved Critical/Important finding.** If anything depends on this candidate, mark it `failed-review` and quarantine its downstream subtree (`blocked-by-upstream-failure`). If it's independent, leave its PR open and set its status to `open — unresolved <severity> finding`. Surface the specific finding either way, and skip step 8.
   - **Suggestion-level findings** → reported only; never a fix round or a quarantine trigger (same as `/cla:lite-pr`).

8. **Merge per the confirmed policy (only when clean).** Reaching this step means step 7 wrote `review: clean`.

   **8a. Should this candidate merge?**
   - **`merge-each-clean`** → yes, whether or not anything depends on it.
   - **`merge-dependencies-only`** → yes only if a later candidate in the confirmed plan `depends_on` it. (The other merge-before-next edge, shared environment state, never reaches this step: Phase 1a routed such candidates out of scope.) No → set its status to `open`, mark the task `completed`, and move on.
   - **The ledger header records `merging stopped`** → no, under either policy. An independent candidate gets status `open — merge refused earlier in the run`. A candidate something depends on gets `failed-merge`, and its downstream subtree is quarantined (`blocked-by-upstream-failure`).

   **8b. Pre-merge checks (every merge, under either policy).**
   ```
   gh pr view <captured-pr-number> --json mergeable,headRefOid,state
   ```
   Read the JSON in context:
   - `state` must be `OPEN`, and `headRefOid` must equal the row's `head_sha`. A different head means someone pushed commits nobody tested or reviewed in this run. Do not merge; the reason is `head moved`.
   - `mergeable` must be `MERGEABLE`. `CONFLICTING` → do not merge; the reason is `conflicts`. Never rebase to clear it, because a rebase changes the code that was tested and reviewed. `UNKNOWN` means GitHub has not computed it yet. Wait once with `python3 -c "import time; time.sleep(15)"`, then query again. Still `UNKNOWN` → do not merge; the reason is `mergeability unknown`.

   A failed check on a candidate nothing depends on → set its status to `open — <reason>` and move on. On a candidate something depends on → set `failed-merge — <reason>` and quarantine its downstream subtree. Either way the chain continues.

   **8c. Merge.** Pass the checked head to the merge, so the merge refuses if the branch moved after 8b:
   ```
   ALLOW_PR_MERGE=1 gh pr merge <captured-pr-number> --squash --delete-branch --match-head-commit <head_sha>
   git checkout <base-branch>
   git pull
   ```
   **The `ALLOW_PR_MERGE=1` prefix is required, and belongs on the merge
   command only.** `ask-destructive-git.py` prompts on every `gh pr merge`,
   because a hook cannot tell an authorized merge from one the agent assumed —
   a real failure that shipped two unrequested merges. This chain is the
   legitimate exception: the user confirmed the candidate plan and the merge
   policy that authorizes this merge in Phase 1, and the run is unattended by
   design, so a prompt here would hang. Use the narrow variable, NOT
   `ALLOW_DESTRUCTIVE_GIT=1` — that would also disarm the force-push,
   `reset --hard` and branch-force-delete checks. Do not export either;
   prefixing this one command is what keeps the exception scoped.
   (separate commands, per bash-discipline). Confirm the merge landed (`git log --oneline -1`) before moving on, and update the candidate's run-notes status to `merged`. Mark the task `completed`.

   **If `gh pr merge` fails, read why before doing anything else.**
   - **It names the head commit** (the `--match-head-commit` refusal) → the branch moved between 8b and 8c. Handle it as a `head moved` check failure from 8b.
   - **It names a merge conflict, a failing required check, or branch protection** → handle it as a failed 8b check, with that message as the reason.
   - **The host runtime refused to run the command at all** — a permission denial, not an error from `gh` → this is the answer for the whole run. Do NOT hunt for a flag spelling that gets through; that is working around a safety gate, not configuring one (the same rule as `/cla:multi-pr`). Append `merging stopped: host refused merge of <id>` to the ledger header. Handle this candidate as a failed 8b check with the reason `merge refused`. Every later candidate then takes 8a's `merging stopped` branch. Do not switch to "dependencies only" instead: a host that refused one merge refuses a dependency's merge too.

Move to the next candidate — **in the same message as step 8's outcome.**

This seam is where a chain has been measured to die. Step 8 produces a natural closing shape (a
candidate done, a PR left open or merged, a status written to the ledger), and a well-written status
report reads as a legitimate place to stop even though nothing is blocked and nobody is waiting on
input. It is not a pause: an idle turn has no pending event to re-invoke the session, so the chain
stops until a human notices, and this run is unattended by design.

The hoisted turn-liveness rule in `SKILL.md` binds here, and is restated because this is exactly the
point at which that file has been closed and the orchestrator is running on the `SKILL.md` summary.
Mechanically: step 8's outcome and the next candidate's step-1 quarantine check go **in the same
message**. If there is no tool call to pair the report with, the candidate is not over. The test is
whether a **pending event** will re-invoke this session, not whether you asked the user anything —
announcing the next candidate **is not a mechanism**, while a backgrounded dispatch, the next
`Skill(cla:lite-pr, …)` call itself, or a watchdog armed before the message ends all are.

## Resume mechanics

Re-invoking `/cla:multi-lite` on the same doc after an interruption picks up cleanly, keyed off the run-notes ledger: step 2 above reads each candidate's recorded `branch`/`pr_number` (`gh pr list --state all`) plus its `review` and `status`, skips a merged PR or one step 8 deliberately left `open`, and re-enters step 7 or step 8 for an open PR the previous run never finished deciding. That re-entry is what keeps `merge-each-clean` honest across an interruption: a clean PR open only because the run stopped still gets merged. Quarantine is a **runtime** outcome, not something the plan encodes — it re-derives correctly by simply re-running the chain: a candidate that `failed` last time left no successful PR, so it runs again, and its downstream (still marked `blocked-by-upstream-failure` until that upstream lands) stays skipped until the upstream actually succeeds. Skip Phase 1c's confirmation only on a genuine same-session resume — a fresh session re-confirms, since it can't know what the previous one decided. A fresh session replaces the `policy:` header line with its own confirmed policy and drops any `merging stopped` line, because a host refusal is a fact about the session that met it; the first-refusal rule in step 8 applies again from scratch. If the run-notes file was lost, resume degrades to the weaker best-effort title match (step 2's fallback arm above), so keeping that file around is what makes cross-session resume reliable.
