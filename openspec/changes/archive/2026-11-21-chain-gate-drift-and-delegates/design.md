# Design

Stock trigger: **cross-cutting change**. It touches `spec-to-pr`, `multi-pr`, two shared references and one shipped script.

## Context

The post-Archive gate, the merge-step reuse rule (`chain-merge.md` "Pre-merge checks" step 3), the Revise diff anchor and the single Implement delegate exist. This records only choices the specs leave open.

## Decisions

### 1. How the merge step learns the gated commit and reuses its run

**Choice:** spec-to-pr's Handoff Test row carries `full gate: green|red on <gated>`, or `full gate: skipped (<reason>)`. `multi-pr` reads it when the `Skill` call returns, in the same session, before "Record the head" stores `head_sha`. Step 3 then reuses that run when either holds:
- `<gated>` equals `head_sha`; or
- `git log --format=%s <gated>..<head_sha>` lists only `docs: TODO.md` and `chore: spec-to-pr run log`, each at most once, and `git diff --name-only <gated>..<head_sha>` names only `TODO.md` and the run-log path Handoff stages.

The allowance is void when the full gate may read `TODO.md`: a gate command from `cla.io/project-facts.md` that names `TODO.md`, a Markdown linter or a `*.md` glob, or a wrapper whose contents the step does not read (a `make` target, a script). Unknown means run. A red reused run means do not merge and do not re-run. Any other case runs the gate.
**Why:** Handoff commits after the gate, so equality alone never fires; those two commits change nothing the suite tests.
- *Rejected: a `gate_sha` column in the run notes.* A fresh-session resume must not reuse it, so nothing may read it.
- *Rejected: a field in the spec-to-pr run record.* That means a `log_run.py` schema change for a value the retro never reads.

### 2. Where the base-drift step lives

**Choice:** a new first section of `spec-to-pr/references/revise.md`, "Before round 1: base drift", plus one sentence in SKILL.md's Revise stub; it runs only when round 1 runs: `git fetch origin <pr-base>`; the base's files are `git diff --name-only <merge-base> origin/<pr-base>`, the PR's the same against `HEAD`; on overlap, `git merge --no-edit origin/<pr-base>`, the touched tests (found as the `Full gate: final-commit-only` paragraph finds them), and a push checked by `ship_check.py pushed`. A merge that refuses to start or fails its commit is aborted (`git merge --abort` when `MERGE_HEAD` exists) and reported as not merged.
**Why:** round 1's three-dot anchor moves to the new merge base, so reviewers read the merged code with no extra step.
- *Rejected: inside `_shared/references/ship.md`.* Ship cuts and opens the PR; the fetch belongs after the PR exists.
- *Rejected: a new phase.* It changes the phase order, probe, diagram and docs for one conditional step.

### 3. The review-round count after a drift merge

**Choice:** `_fix_rounds_applied` ranges over `origin/<base>..<branch>` when `refs/remotes/origin/<base>` resolves, else the local name. `<base>` stays `_base_branch()`, the default branch, named by its full ref `refs/remotes/origin/<base>` so a local branch called `origin/<base>` cannot win. The drift step runs only when the PR targets the default branch: for a stacked child `origin/<default>` would not hold the parent's later round commits, so it reports "not checked: stacked child" and merges nothing.
**Why:** the remote-tracking ref holds every commit a drift merge took, because the merge was made from it after a fetch.
- *Rejected: `git log --first-parent`.* Correct, but unlike the decision's wording and the probe's other ranges.
- *Rejected: a fetch inside the probe.* A read-only probe would need the network.

### 4. The Implement split

**Choice:** subtasks are `tasks.md` checkbox lines; groups are its `## N.` headings. Above 40 subtasks with two or more groups, one delegate per group runs in order. Each brief enumerates its group, marks other groups `held by orchestrator`, and carries a summary of at most about 150 words of earlier groups (files, names, deviations), built from earlier returns, ticked boxes and `git diff --stat`. Miss handling runs on each return; the next dispatch goes in the same message. A flat `tasks.md` keeps one delegate. The Post-check counts the whole file at the end.
- *Rejected: groups in parallel.* Later groups build on earlier ones, and two writers in one checkout break the orchestrator-vs-delegate rule.
- *Rejected: a checkpoint hand-off.* The owner declined it.

### 5. Continuing an agent for a correction

**Choice:** one section in `_shared/references/subagent-brief.md`, "Correcting a reply". A correction continues the same agent id, naming only the gap, when `SendMessage` is available and the agent returned a non-empty report with an identified gap. An agent that returned nothing, or stopped on exhausted context, gets one fresh dispatch scoped to what remains (`implement-delegate.md`'s recovery). A continuation that errors or comes back unfinished gets one fresh dispatch, never a third try. An implementer's continuation still waits for the settle-the-tree check. Three call sites carry one pointer sentence each.
**Why:** continuing an agent whose context ran out repeats the failure Q3 fixes.
- *Rejected: continuing reviewers into a later round.* Round 2 must read the fix independently.

## Risks / Trade-offs

- [A summary drops a detail a later group needs] → the delegate can still read the branch, and the Post-check catches unticked tasks.
- [A test reading `TODO.md` or the run log is not detected] → the reuse assumes suites read neither; a gate command naming them voids it.
