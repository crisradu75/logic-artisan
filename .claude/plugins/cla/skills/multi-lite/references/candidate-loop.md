# candidate-loop — Phase 3's 8-step per-candidate procedure + resume mechanics (full mechanics)

The Phase 3 step-by-step procedure. `SKILL.md`'s Phase 3 stub carries the load-bearing invariants (merge-authorization scope, downstream-only quarantine, the review-enforcement boundary, ledger-keyed identifier capture — all stated in the hoisted rules); this file carries the 8-step recipe and the resume behavior it enables.

For each candidate in the confirmed order:

1. **Skip if quarantined.** If any candidate in this one's `depends_on` (transitively) was quarantined earlier in this run, skip it too — mark it `blocked-by-upstream-failure` (in both the task and the run-notes ledger) and record which upstream failed. Don't run a candidate on a base its dependency never landed on.

2. **Resume check (keyed off the run-notes ledger, not a guess).** Look this candidate up in `cla.io/retro/multi-lite-run-notes-<date>.md`. If it has a recorded `pr_number` from an earlier pass, read the PR's real state by that number — never by branch or title, which can match a different PR:
   ```
   gh pr view <recorded-pr-number> --json state,headRefOid,mergeCommit
   ```
   **A resume never merges a head this run did not test and review.** Commits pushed to a candidate's branch after the ledger recorded its `head_sha` — a user's fix, a bot, another session — are the user's to review. So a moved head leaves the PR open with a reason; it never re-enters step 7 or step 8. Take the **first** arm that matches:
   - **`gh` reports no such PR** → `failed — recorded PR not found`. Quarantine the downstream subtree and skip.
   - **`MERGED`** → done. Write `status: merged` if it is not already, and write `merge_commit` from `mergeCommit.oid` whenever that column is empty, because step 3 and Phase 4 read it. Skip.
   - **`CLOSED` without merging** → a human closed it; do not reopen it by re-running. Write `failed — PR closed without merging`, quarantine the downstream subtree, and skip.
   - **`OPEN`, and `head_sha` is empty or differs from `headRefOid`** → the PR now holds commits nobody in this run tested or reviewed. Do not merge. Set status `open — head moved since review` for an independent candidate. For a candidate something depends on, set `failed-merge — head moved since review` and quarantine its downstream subtree. Skip. The Phase 4 report tells the user to review and merge it by hand.
   - **`OPEN`, `review` empty** → the run stopped during or before step 7, and the head is the one step 6 recorded.
     - `deferred` recorded (step 6 wrote it) → re-enter step 7, working from the recorded findings.
     - `deferred` empty → the findings lived only in the lost session. **Never infer clean.** Write `review: unresolved` with the reason `findings lost on resume`, and take step 7's unresolved branch.
   - **`OPEN`, `review` is `unresolved`** → final. If `status` is empty, take step 7's unresolved branch to write it; otherwise skip.
   - **`OPEN`, `review` is `clean`, and `status` is plain `open` under `merge-dependencies-only`** → final. The policy left it for the user. Skip.
   - **`OPEN`, `review` is `clean`, any other `status`** → re-enter step 8. That covers: an empty `status` (the run stopped between steps 7 and 8), `failed-merge`, a `merged` status the PR state contradicts, every `open — <merge-side reason>`, and a plain `open` under `merge-each-clean` (a fresh session may have confirmed the wider policy). Step 8 runs every check again from scratch.

   Re-entering step 7 or 8 first runs `git fetch origin`, then `git checkout <recorded-branch>`, then `git pull` (three separate commands) — never `<base-branch>` — because the PR's commits live there. Only when there is **no** recorded `pr_number` for this candidate (a fresh session whose notes file was lost) fall back to a best-effort title match with `gh pr list --state all`, and say so. That arm is explicitly weaker because `multi-lite` can't reconstruct `commit-push-pr`'s branch name, and a PR it finds has no recorded `head_sha`, so the moved-head arm leaves it open.

3. **Ensure the right base.** `git checkout <base-branch>`, then `git pull`, then `git status --porcelain` (empty = clean) before running — three separate commands. Under either policy, every candidate in this one's `depends_on` must already be merged into `<base-branch>` before it runs (step 8 below does that merge as the chain reaches each dependency) — so a dependent candidate branches off a `<base-branch>` that actually contains its prerequisites. **Check it rather than assume it:** every candidate in `depends_on` must have ledger `status: merged` with a `merge_commit`, and `git merge-base --is-ancestor <merge_commit> HEAD` must exit 0 after the pull (in a reactive-worktree pivot, run `git fetch origin <base-branch>` and check against `origin/<base-branch>` instead of `HEAD`). If either fails, mark this candidate `blocked-by-upstream-failure`, naming the unmerged dependency, and move on. (In a reactive-worktree pivot, substitute the `origin/<base-branch>`-based worktree idiom from the hoisted rule for the `git checkout <base-branch>` here.)

4. **Run `/cla:lite-pr` on the candidate:** `Skill(cla:lite-pr, args="<one-line description>")`. Let it run its full Explore→Plan→Implement→Test→Ship→Review cycle uninterrupted — do not intervene mid-phase. **Descriptions must be concrete enough that `/cla:lite-pr`'s optional Explore phase auto-skips** — Phase 1a already requires this. Never let a candidate enter `/cla:lite-pr`'s interactive `Skill(shape-decision)` Q&A during an unattended chain: an under-specified candidate that triggers Explore would block the whole run waiting on input. If a candidate genuinely needs shaping, that's a Phase 1 signal it isn't lite-ready — route it out of scope rather than discovering it here.

5. **Classify the outcome.**
   - **Test-phase halt (hard failure — never opened a PR).** `/cla:lite-pr` stopped at its one deliberate halt (an unresolved Test failure). Mark this candidate `failed`, mark everything transitively downstream `blocked-by-upstream-failure`, record the failing check, and **continue with the next independent candidate**.
   - **PR opened.** A PR being open does **not** yet mean the candidate is clean — proceed to step 6.

6. **Capture the real identifiers immediately (this is what makes resume/merge deterministic).** From `/cla:lite-pr`'s ship report, read the concrete **branch name** and **PR number** it just opened, then read the PR's head commit with `gh pr view <pr-number> --json headRefOid`. Write all three into this candidate's row in the run-notes ledger as `branch`, `pr_number`, and `head_sha`.

   **In the same write, record the deferred findings.** `/cla:lite-pr` keeps them only in context, so a resumed step 7 has nothing else to read them from. Count a Critical/Important finding as settled only when the report says explicitly that it was **fixed**. Every other Critical/Important finding counts as deferred:
   - one the report says was deferred, with its rationale,
   - one whose outcome the report does not state,
   - one whose fix left a surviving mutant, meaning a deliberately broken version of the fix that no test caught (`/cla:lite-pr` names these in its report with a reason). Nobody has shown that fix works.

   Set `deferred` to that count (`0` when there are none). Copy each one verbatim — severity, file:line, the finding, and the report's rationale or "outcome not stated" — under the ledger's `## Deferred findings` section, headed by this candidate's id. If the report's Review section is missing or cannot be read, do not guess a count. Leave `deferred` empty, which step 7 treats as unresolved.

   Every later step that needs to act on this PR (step 8's merge, a resume in step 2) keys off these recorded values — never a re-derived branch name or an "in-context" PR number.

7. **Enforce `/cla:lite-pr`'s deferred review findings (the thin layer it doesn't do itself).** `/cla:lite-pr` opens the PR even when its Review phase *defers* Critical/Important findings — it never halts on them, and it has already spent its own single fix round before deferring. Work from the findings step 6 recorded in the ledger — the same list whether this is the first pass or a resume:
   - **`deferred` is empty** → step 6 could not determine the findings. Write `review: unresolved` with the reason `deferred findings not determinable`, and take the unresolved branch below.
   - **`deferred` is `0`** → no finding is unresolved. Write `review: clean` to its ledger row and go to step 8. (This review verdict is not a test verdict. `/cla:lite-pr`'s own review fixes were committed after its Test phase, so step 8b runs the full gate before any merge.)
   - **One or more deferred Critical/Important findings** → run **one additional enforcement round** on exactly those deferred findings (this is a round *on top of* `lite-pr`'s own already-spent one — not a re-run of it, and not a loop). For each finding: read it, apply the `Edit`, then re-run the narrow gate the finding was about plus the changed-file tests. Commit path-scoped (`fix: resolve deferred review findings`) after a `git_state.py` check, and push to the captured branch. **Verify the push landed** — `git rev-parse HEAD` vs `git ls-remote origin <captured-branch>`, compared in-context (not piped through `grep`/`awk`); A mismatch means the fix did not ship. Write `review: unresolved` with the reason `push not verified`, and take the unresolved branch below. Do not stop to ask: this run is unattended, and a question here stalls every later candidate. On a match, update the row's `head_sha` to that pushed commit.
     - **Resolved by that round** → write `review: clean` and go to step 8. Step 8b runs the full Test gate on this head before any merge.
     - **Still unresolved after the round (or genuinely out of scope)** → write `review: unresolved`. Never treat it as silently clean, and **never merge a candidate carrying an unresolved Critical/Important finding.** The status carries the review's own reason, so Phase 4 tells the user the real problem: `unresolved <severity> finding` for a finding that survived, or the reason already written beside `review` (`push not verified`, `findings lost on resume`, `deferred findings not determinable`). If anything depends on this candidate, set `failed-review — <reason>` and quarantine its downstream subtree (`blocked-by-upstream-failure`). If it's independent, leave its PR open and set `open — <reason>`. Surface the specific finding either way, and skip step 8.
   - **Suggestion-level findings** → reported only; never a fix round or a quarantine trigger (same as `/cla:lite-pr`).

8. **Merge per the confirmed policy (only when clean).** Reaching this step means step 7 wrote `review: clean`.

   **8a. Should this candidate merge?** First, the policy decides:
   - **`merge-each-clean`** → yes, whether or not anything depends on it.
   - **`merge-dependencies-only`** → yes only if this candidate needs merging before a later one, by either edge:
     - a later candidate in the confirmed plan `depends_on` it, **or**
     - its PR moves shared environment state. Phase 1a routed out every item the doc said would do this, but an implementation can still add one. So read the PR's file list with `gh pr diff <captured-pr-number> --name-only` and look for a migration, data seeded into a shared environment, or a provisioning script. Test fixtures loaded only by the test suite are not shared state. Record the derivation in the row either way: the matching paths and why each moves shared state, or `no shared-state paths in <N> changed files`. A match is a merge-before-next edge. Merge it, and flag it in the Phase 4 report as a shared-state change Phase 1a did not predict. If `gh pr diff` fails, the edge is undetermined. Do not merge; set `open — shared-state check failed`.

     Neither edge → set its status to `open`, mark the task `completed`, and move on.

   **Then, only for a yes: the ledger header records `merging stopped`** → the host already refused a merge this session, so do not attempt one. An independent candidate gets status `open — merge refused earlier in the run`. A candidate something depends on gets `failed-merge — merge refused earlier in the run`, and its downstream subtree is quarantined (`blocked-by-upstream-failure`). A candidate the policy said no to keeps its plain `open`: a refusal does not change what the user has to do about it.

   **8b. Pre-merge checks (every merge, under either policy).** Run them in this order. The local gate runs before GitHub's merge state is read, because the gate takes minutes and remote checks are usually still running right after a push.
   1. **The PR is open on the recorded head.** Run `gh pr view <captured-pr-number> --json state,headRefOid`. `state` must be `OPEN`. `headRefOid` must equal the row's `head_sha`; a different head means commits nobody tested or reviewed here, so do not merge, and the reason is `head moved`. This holds on a resume too: step 2 never sends a moved head here.
   2. **The local checkout is that head.** `git rev-parse HEAD` must equal `head_sha`. If it does not, run `git checkout <captured-branch>` then `git pull`, and compare again. Still different → do not merge; the reason is `local head mismatch`.
   3. **The full Test gate is green on `head_sha`.** Every merge needs this. `/cla:lite-pr` ran its gate before its own review fixes were committed, and step 7's enforcement round re-ran only narrow tests. Run `/cla:lite-pr`'s full Test gate: smoke, then full, the commands its Test phase reads from `cla.io/project-facts.md`.
      - Green → continue.
      - Red → do not merge; the reason is `full gate red: <failing check>`. Do not re-run it hoping for green. A flaky gate is a finding for the user, not a retry.
      - `cla.io/project-facts.md` names no test commands and the PR changes source-affecting paths (as `/cla:lite-pr`'s Test phase defines them) → do not merge; the reason is `full gate unavailable`. `/cla:lite-pr` treats this case as a warning. A merge cannot, because nothing would have tested the merged code.
      - The PR changes no source-affecting paths → there is nothing to gate. Record `gate skipped: no source-affecting paths` beside the status and continue.
   4. **Remote checks have finished.** Run `gh pr checks <captured-pr-number>`. If any check is still pending, wait for it with `python3 -c "import time; time.sleep(60)"` and query again, for at most 15 checks in total. A check still pending after that → the reason is `checks still pending`. A check that failed → the reason is `checks not green`. A repo with no remote checks makes `gh pr checks` report none; that is a pass.
   5. **`mergeStateStatus` allows the merge.** Run `gh pr view <captured-pr-number> --json mergeStateStatus`.
      - `CLEAN`, `HAS_HOOKS`, or `BEHIND` → proceed. `BEHIND` means the base gained commits after this branch was cut. Squash applies onto the current base, and branch protection that requires an up-to-date branch reports `BLOCKED` instead. Under `merge-each-clean` in a live run, every earlier merge happened before this candidate branched, so `BEHIND` means someone else pushed to the base. Record `behind base: merged tree not tested` beside the status so Phase 4 reports it.
      - `DIRTY` → the reason is `conflicts`. Never rebase to clear it, because a rebase changes the code that was tested and reviewed.
      - `UNSTABLE` → the reason is `checks not green`.
      - `BLOCKED` → the reason is `blocked by branch protection`.
      - `DRAFT` → the reason is `draft`.
      - `UNKNOWN` → GitHub has not computed it yet. Wait once with `python3 -c "import time; time.sleep(15)"`, then query again. Still `UNKNOWN` → the reason is `mergeability unknown`.

   A failed check on a candidate nothing depends on → set its status to `open — <reason>` and move on. On a candidate something depends on → set `failed-merge — <reason>` and quarantine its downstream subtree. Either way the chain continues.

   **8c. Merge, then confirm it landed.** Pass the checked head to the merge, so the merge refuses if the branch moved after 8b:
   ```
   ALLOW_PR_MERGE=1 gh pr merge <captured-pr-number> --squash --delete-branch --match-head-commit <head_sha>
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

   **An exit code of 0 does not prove a merge.** A repo with a merge queue, for one, exits 0 while the PR stays open. Confirm it:
   1. `gh pr view <captured-pr-number> --json state,mergeCommit`. `state` must be `MERGED`. Anything else → a failed 8b check with the reason `merge not confirmed (state <state>)`.
   2. `MERGED` is the fact. Write `status: merged` and `merge_commit: <mergeCommit.oid>` to the row now, and mark the task `completed`.
   3. Bring the local base up to date so the next candidate branches off it. In the primary clone: `git checkout <base-branch>` then `git pull`. In a reactive-worktree pivot, which cannot check out `<base-branch>`: `git fetch origin <base-branch>`. A failure here is not a merge failure. Say so in the Phase 4 report and continue: step 3 checks each dependency's `merge_commit` against the base before a dependent runs, so a stale base blocks that dependent instead of breaking it.

   **If `gh pr merge` exits non-zero, check the PR before reading the error.** Run `gh pr view <captured-pr-number> --json state,mergeCommit`. A `MERGED` state means the merge happened and only a later part failed. `--delete-branch` fails this way when the branch is checked out in a worktree. Take the confirmation steps above. Otherwise, take the first arm that matches:
   - **The host runtime refused to run the command at all** → a tool-permission denial from the host, with no output from `gh` itself. This is the answer for the whole run. Do NOT hunt for a flag spelling that gets through; that is working around a safety gate, not configuring one (the same rule as `/cla:multi-pr`). Append `merging stopped: host refused merge of <id>` to the ledger header. Handle this candidate as a failed 8b check with the reason `merge refused`. Every later candidate then takes 8a's `merging stopped` branch. Do not switch to "dependencies only" instead: a host that refused one merge refuses a dependency's merge too.
   - **Any other error from `gh`** → a failed 8b check with the reason `merge error: <first line of the error>`. That covers the `--match-head-commit` refusal (the branch moved after 8b), a conflict, a failing required check, branch protection, an auth or rate-limit error, and a disallowed merge method. It does **not** set `merging stopped`: an error `gh` returned is about this PR or this moment, not a refusal by the host.

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

Re-invoking `/cla:multi-lite` on the same doc after an interruption picks up cleanly, keyed off the run-notes ledger: step 2 above reads each candidate's PR by its recorded `pr_number`, plus the row's `deferred`, `review`, `head_sha` and `status`. It skips a merged PR, a closed one, and one whose open state is final. It re-enters step 7 or step 8 for an open PR the previous run never finished deciding. That re-entry is what keeps `merge-each-clean` honest across an interruption: a clean PR open only because the run stopped still gets merged. Two things a resume never does. It never infers `review: clean`: without recorded findings, the candidate stays unresolved. And it never merges a moved head: commits pushed after the ledger recorded `head_sha` leave the PR open for the user to review and merge by hand, whoever pushed them. Quarantine is a **runtime** outcome, not something the plan encodes — it re-derives correctly by simply re-running the chain: a candidate that `failed` last time left no successful PR, so it runs again, and its downstream (still marked `blocked-by-upstream-failure` until that upstream lands) stays skipped until the upstream actually succeeds. Skip Phase 1c's confirmation only on a genuine same-session resume — a fresh session re-confirms, since it can't know what the previous one decided. A fresh session replaces the `policy:` header line with its own confirmed policy and drops any `merging stopped` line, because a host refusal is a fact about the session that met it; the first-refusal rule in step 8 applies again from scratch. If the run-notes file was lost, resume degrades to the weaker best-effort title match (step 2's fallback arm above), so keeping that file around is what makes cross-session resume reliable.
