# candidate-loop — Phase 3's 8-step per-candidate procedure + resume mechanics (full mechanics)

The Phase 3 step-by-step procedure. `SKILL.md`'s Phase 3 stub carries the load-bearing invariants (merge-authorization scope, downstream-only quarantine, the review-enforcement boundary, ledger-keyed identifier capture — all stated in the hoisted rules); this file carries the 8-step recipe and the resume behavior it enables.

For each candidate in the confirmed order:

1. **Skip if quarantined.** If any candidate in this one's `depends_on` (transitively) was quarantined earlier in this run, skip it too — mark it `blocked-by-upstream-failure` (in both the task and the run-notes ledger) and record which upstream failed. Don't run a candidate on a base its dependency never landed on.

2. **Resume check (keyed off the run-notes ledger, not a guess).** Look this candidate up in `cla.io/retro/multi-lite-run-notes-<date>.md`. If it has a recorded `branch`/`pr_number` from an earlier pass, confirm its real state with `gh pr list --state all --head <recorded-branch>` (use `--state all`, not the default open-only — a merged dependency's branch was deleted by `--delete-branch` and its PR won't show as open). An open or merged PR → treat as done, mark the task complete, skip. Only when there is **no** recorded identifier for this candidate (a fresh session whose notes file was lost) fall back to a best-effort title match, and say so — this arm is explicitly weaker because `multi-lite` can't reconstruct `commit-push-pr`'s branch name.

3. **Ensure the right base.** `git checkout <base-branch>`, then `git status --porcelain` (empty = clean) before running. Under merge-before-dependents, every candidate in this one's `depends_on` must already be merged into `<base-branch>` before it runs (step 8 below does that merge as the chain reaches each dependency) — so a dependent candidate branches off a `<base-branch>` that actually contains its prerequisites. (In a reactive-worktree pivot, substitute the `origin/<base-branch>`-based worktree idiom from the hoisted rule for the `git checkout <base-branch>` here.)

4. **Run `/cla:lite-pr` on the candidate:** `Skill(cla:lite-pr, args="<one-line description>")`. Let it run its full Explore→Plan→Implement→Test→Ship→Review cycle uninterrupted — do not intervene mid-phase. **Descriptions must be concrete enough that `/cla:lite-pr`'s optional Explore phase auto-skips** — Phase 1a already requires this. Never let a candidate enter `/cla:lite-pr`'s interactive `Skill(shape-decision)` Q&A during an unattended chain: an under-specified candidate that triggers Explore would block the whole run waiting on input. If a candidate genuinely needs shaping, that's a Phase 1 signal it isn't lite-ready — route it out of scope rather than discovering it here.

5. **Classify the outcome.**
   - **Test-phase halt (hard failure — never opened a PR).** `/cla:lite-pr` stopped at its one deliberate halt (an unresolved Test failure). Mark this candidate `failed`, mark everything transitively downstream `blocked-by-upstream-failure`, record the failing check, and **continue with the next independent candidate**.
   - **PR opened.** A PR being open does **not** yet mean the candidate is clean — proceed to step 6.

6. **Capture the real identifiers immediately (this is what makes resume/merge deterministic).** From `/cla:lite-pr`'s ship report, read the concrete **branch name** and **PR number** it just opened, and write them into this candidate's row in the run-notes ledger. Every later step that needs to act on this PR (step 8's merge, a resume in step 2) keys off these recorded values — never a re-derived branch name or an "in-context" PR number.

7. **Enforce `/cla:lite-pr`'s deferred review findings (the thin layer it doesn't do itself).** `/cla:lite-pr` opens the PR even when its Review phase *defers* Critical/Important findings — it never halts on them, and it has already spent its own single fix round before deferring. Read its final report:
   - **No deferred Critical/Important findings** → the candidate is clean; go to step 8.
   - **One or more deferred Critical/Important findings** → run **one additional enforcement round** on exactly those deferred findings (this is a round *on top of* `lite-pr`'s own already-spent one — not a re-run of it, and not a loop). For each finding: read it, apply the `Edit`, then re-run the narrow gate the finding was about plus the changed-file tests. Commit path-scoped (`fix: resolve deferred review findings`) after a `git_state.py` check, and push to the captured branch. **Verify the push landed** — `git rev-parse HEAD` vs `git ls-remote origin <captured-branch>`, compared in-context (not piped through `grep`/`awk`); a mismatch halts this candidate and surfaces to the user rather than proceeding as if the fix shipped.
     - **Resolved by that round** → clean; go to step 8.
     - **Still unresolved after the round (or genuinely out of scope)** → never treat as silently clean, and **never merge a candidate carrying an unresolved Critical/Important finding.** If anything depends on this candidate, mark it `failed-review` and quarantine its downstream subtree (`blocked-by-upstream-failure`). If it's independent, leave its PR open but flag it `open — unresolved <severity> finding` in the report. Surface the specific finding either way.
   - **Suggestion-level findings** → reported only; never a fix round or a quarantine trigger (same as `/cla:lite-pr`).

8. **Merge if a dependency (only when clean).** If a later candidate in the confirmed plan depends on this one, **merge now** — using the PR number captured in step 6 — so the dependent can branch off it:
   ```
   ALLOW_PR_MERGE=1 gh pr merge <captured-pr-number> --squash --delete-branch
   git checkout <base-branch>
   git pull
   ```
   **The `ALLOW_PR_MERGE=1` prefix is required, and belongs on the merge
   command only.** `ask-destructive-git.py` prompts on every `gh pr merge`,
   because a hook cannot tell an authorized merge from one the agent assumed —
   a real failure that shipped two unrequested merges. This chain is the
   legitimate exception: the user confirmed the candidate plan, including this
   dependency edge, in Phase 1, and the run is unattended by design, so a
   prompt here would hang. Use the narrow variable, NOT
   `ALLOW_DESTRUCTIVE_GIT=1` — that would also disarm the force-push and
   `reset --hard` checks. Do not export either; prefixing this one command is
   what keeps the exception scoped.
   (separate commands, per bash-discipline). Confirm the merge landed (`git log --oneline -1`) before moving on, and update the candidate's run-notes status to `merged`. If **nothing** depends on this candidate, leave its PR **open** — merging is the user's call for independents — and set its status to `open`. Mark the task `completed` either way.

Move to the next candidate.

## Resume mechanics

Re-invoking `/cla:multi-lite` on the same doc after an interruption picks up cleanly, keyed off the run-notes ledger: step 2 above reads each candidate's recorded `branch`/`pr_number` and skips the ones with an already-open-or-merged PR (`gh pr list --state all`). Quarantine is a **runtime** outcome, not something the plan encodes — it re-derives correctly by simply re-running the chain: a candidate that `failed` last time left no successful PR, so it runs again, and its downstream (still marked `blocked-by-upstream-failure` until that upstream lands) stays skipped until the upstream actually succeeds. Skip Phase 1c's confirmation only on a genuine same-session resume — a fresh session re-confirms, since it can't know what the previous one decided. If the run-notes file was lost, resume degrades to the weaker best-effort title match (step 2's fallback arm above), so keeping that file around is what makes cross-session resume reliable.
