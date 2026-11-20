# Open issues — 2026-11-21 (revised)

## Topic

What to do about each of the five open issues: #507 (multi-spec/multi-pr have no proportionality gate),
#568 (spec-to-pr's post-Archive gate skip depends on free text), #569 (multi-pr has no model for one large
change), #570 (base drift found only at merge), #436 (live check that reviewer prompts carry the diff-review
rule).

This revision replaces a first version of this file (uncommitted) after an independent Opus review found two
decisions that would do harm as written (a caller flag that left independent chain changes with no full gate;
a drift check placed before any code exists), a liveness rule that contradicted `spec-to-pr/SKILL.md:177`, and
wrong rationales about Stakes-driven review routing.

## Questions and decisions

| Q | Decision | Rationale |
|---|---|---|
| Q1 | (#568) Remove the "invocation names `/cla:multi-pr`" skip at `spec-to-pr/SKILL.md:161`. Under `Full gate: final-commit-only`, `spec-to-pr` always runs its one full gate after Archive, and its Handoff names the commit that run passed on. The merge step reuses it when the PR head still equals that commit (`_shared/references/chain-merge.md:150`). The free-text caller sentence at `multi-pr/references/change-loop.md:61` goes | Every change gets its one full gate — `multi-pr` merges only a change a later change needs (`change-loop.md:114`), so a skip left independent changes ungated. The existing reuse rule prevents the duplicate; this deletes text rather than adding a flag |
| Q2 | (#570) After Ship opens the PR and before Revise round 1: `git fetch origin <base>`, list files changed on the base since the branch point that the PR also touches; overlap → merge (never rebase) `origin/<base>` into the feature branch, run the touched area's tests, and Revise reviews the merged code | By then the work is committed, so the merge cannot hit uncommitted edits; reviewers see the code that will land. Spec-to-pr's Review phase runs before any code exists (`spec-to-pr/SKILL.md:117-121`), and Ship already `git pull`s before cutting the branch (`_shared/references/ship.md:18`) |
| Q3 | (#569) In `spec-to-pr/references/implement-delegate.md` (one delegate today, `:9`): over ~40 subtasks, dispatch one delegate per `tasks.md` group, sequentially, each briefed with a summary of the earlier groups | The context exhaustion in #569 points at the single Implement delegate; groups already exist in `tasks.md` |
| Q4 | (#507 comment) `review-change/references/checklist.md:145`: the subtask count `b` alone no longer makes a change Large, unless its `proposal.md` carries `Budget: protected` (`openspec/config.yaml:18`). The concentration override (`checklist.md:158`) stays | Removes the three-agent cost that task count alone triggered, while protected changes keep the full pre-build review via a marker the author already writes |
| Q5 | (#507 part 2) `multi-spec/references/authoring-brief.md`: before reporting `done`, the author runs `check_spec_proof.py` for the whole-change budget and `wc -w` for the per-artifact limits (proposal ~400, design ~800 words, `openspec/config.yaml:16,21`), cuts anything over, never cuts a requirement that guards a protected area (`authoring-brief.md:45`), and reports what still does not fit. The batch is not blocked | Enforces the config's "Over budget, cut" and the per-artifact limits #507 actually hit, with no extra agent run and no script change. Today the result is information only (`authoring-brief.md:75`) |
| Kept | (#507 part 1) No audience question at the batch gates | Review depth is judged from the diff's risk signals (`_shared/references/model-routing.md:62-71`), and the blocking filter keeps only findings in a Stakes-protected area (`spec-to-pr/references/revise.md:119`); a per-run question adds cost for nothing |
| Kept | (#436) At the next real `lite-pr` or `spec-to-pr` review round, read the built reviewer prompts for the diff-review rule's wording and the diff-file path, record the result (command, session) on #436, then close it or file the gap | `warn-agent-dispatch.py:8-17` checks only a missing `model` and pasted diff text, and warn output is not in transcripts |

## Noted, not asked

- **Reversibility:** every item is prose in one revertible commit.
- **Release:** each shipped item is a patch under the root `CLAUDE.md` versioning rule.
- **#570 resume counting:** `spec-to-pr/scripts/probe_state.py:354-367` counts only `fix: review round N` subjects, so a merge commit is not counted; base commits merged in could match only in a non-squash repo with a stale local base. Build detail: the new step fetches first, and the probe's `base..branch` range uses the fetched base.
- **#570 window left open:** drift landing during Revise fix rounds or Archive is still found at merge (`change-loop.md:118`).
- **#507 parts 3 and 4:** already handled — round 2 only after a protected-area fix (`revise.md:5`); mutation gate only on blocking-finding fixes (`revise.md:173`).
- **Declined, stated when closing:** #507's "block the batch"; #569's checkpoint hand-off and one-worker-per-change mode. #569's "coordinator waits for its background jobs" is already covered (`spec-to-pr/SKILL.md:177`, `_shared/references/subagent-brief.md:270-290`).
- **Accepted risks:** a protected change without the `Budget: protected` marker gets the lighter review (Q4); an author's self-cut may drop something the spec review must catch (Q5); a later task-group delegate depends on the summary of earlier groups (Q3).
- **Downstream consumers:** every built item changes shipped skills (`spec-to-pr`, `multi-pr`, `review-change`, `multi-spec`) — protected under `cla.io/project-facts.md` ("anything shipped to other repos").

## Final axes

All Clear — Reversibility (Noted), Release (Noted), Smaller option (Q1, Q3, Q4, Q5), Invariants (Q1, Q4),
Edge cases (Q2, Noted), Downstream consumers (Noted).

## Why it matters, and next step

These fixes make the batch skills cheaper where cost bought nothing (task-count reviews, oversized specs) and
safer where a gap was real (an ungated or duplicated full gate, drift reviewed only after the fact, one agent
carrying an 80-task build).

Build paths (per `cla.io/project-facts.md` Stakes: shipped behaviour is protected), three `/cla:spec-to-pr`
changes, one PR at a time per area:

1. Chain fixes in `spec-to-pr` and `multi-pr` (Q1, Q2, Q3) — closes #568, #570, #569 (with the declined parts stated).
2. `review-change` sizing (Q4).
3. `multi-spec` author self-check (Q5) — with change 2, closes #507 with a comment mapping each part (part 1 → Kept, part 2 → Q5 with the block declined, part 3 → `revise.md:5`, part 4 → `revise.md:173`, comment → Q4).

#436 is handled at the next review round.
