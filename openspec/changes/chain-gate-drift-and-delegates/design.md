# Design

Stock trigger: **cross-cutting change**. It touches `spec-to-pr`, `multi-pr`, two shared references and one shipped script.

## Context

The post-Archive full gate, the merge-step reuse rule ("a green run this session on exactly `head_sha` … counts", `chain-merge.md` "Pre-merge checks" step 3), the Revise diff anchor (`origin/<pr-base>...<branch>`), and the single Implement delegate all exist today. This design records only the choices the specs leave open.

## Decisions

### 1. How the merge step learns the gated commit

**Choice:** spec-to-pr's Handoff report carries one line in its Test row: `full gate: green|red on <sha>`. `multi-pr` reads that line when the `Skill` call returns, in the same session. It compares the line with the `head_sha` it records under "Record the head" right afterwards. `chain-merge.md` step 3's existing "this session" rule then decides. No new field.
**Why:** the reuse rule already counts only this session's runs. An in-session report line is all it needs.
- *Rejected: a `gate_sha` column in the run notes.* A fresh-session resume must not reuse it anyway, so it would store a value nothing may read.
- *Rejected: a field in the spec-to-pr run record.* That means a `log_run.py` schema change for a value the retro never reads.

### 2. Where the base-drift step lives

**Choice:** a new first section of `spec-to-pr/references/revise.md`, "Before round 1: base drift", plus one sentence in SKILL.md's Revise stub. The steps:
1. `git fetch origin <pr-base>`.
2. Compute the base's files as `git diff --name-only <merge-base> origin/<pr-base>`, and the PR's files the same way against `HEAD`. Intersect the two lists.
3. If they overlap: `git merge --no-edit origin/<pr-base>`, then the touched tests (found the way the `Full gate: final-commit-only` paragraph finds them), then a push checked by `ship_check.py pushed`.

**Why:** the step then runs exactly when Revise round 1 runs (open question 4). And because round 1's three-dot diff anchor moves to the new merge base, the reviewers read the merged code with no extra step.
- *Rejected: inside `_shared/references/ship.md`.* Ship's steps are about cutting and opening the PR, and the fetch belongs after the PR exists.
- *Rejected: a new phase.* It would change the phase order, the probe, the workflow diagram and the docs for one conditional step.

### 3. The review-round count after a drift merge

**Choice:** `_fix_rounds_applied` ranges over `origin/<base>..<branch>` when `refs/remotes/origin/<base>` resolves. Otherwise it falls back to the local name, as today.
**Why:** the remote-tracking ref holds every commit a drift merge took, because the merge was made from it after a fetch. That is the "fetched base" the decision names.
- *Rejected: `git log --first-parent`.* It is also correct, but it drifts from the decision's wording and from the probe's other ranges.
- *Rejected: a fetch inside the probe.* That would make a read-only probe call the network, and it would fail offline.

### 4. The Implement split

**Choice:** subtasks are the checkbox lines in `tasks.md`, and groups are its `## N.` headings. Above 40 subtasks, the orchestrator dispatches one delegate per group, in order. Each brief does three things:
- enumerates only that group's tasks, under the existing eight delegation rules;
- carries a summary of at most about 150 words of the earlier groups: the files they touched, the names they introduced, and any deviation from the tasks, built from the earlier returns, the ticked boxes and `git diff --stat`;
- marks the other groups' tasks `held by orchestrator`.

Each return goes through the existing miss handling before the next dispatch, which goes in the same message (turn liveness). The Post-check still counts the whole `tasks.md` after the last group.
- *Rejected: groups in parallel.* Later groups build on earlier ones, and two writers in one checkout break the orchestrator-vs-delegate rule.
- *Rejected: a checkpoint hand-off.* The owner declined it.

### 5. Continuing an agent for a correction

**Choice:** one short section in `_shared/references/subagent-brief.md`, "Correcting a reply". When `SendMessage` is available, the correction goes to the same agent id and names only the gap. When the tool is absent or the call errors, the fallback is a fresh dispatch with the full brief (open question 5). Each case keeps its existing attempt limit. An implementer's continuation still waits for the settle-the-tree check. The three call sites each carry one pointer sentence, and nothing else restates the rule.
- *Rejected: continuing reviewers into a later round.* Round 2 must read the fix independently.

## Risks / Trade-offs

- [A summary drops a detail a later group needs] → the delegate can still read the branch, and the Post-check catches unticked tasks.
- [The decided reuse never fires while Handoff commits after the gate (open question 1)] → this is safe, because the merge step re-gates. It only costs one full run per merged change until the owner decides.
