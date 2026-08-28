## Why

Every `spec-to-pr` change that has reached a second Revise round found something new, and it was
never a leftover from round 1 — it was a defect round 1's own fix introduced, or a sibling instance
of the defect round 1's fix missed. Two of the four observed findings were the second shape,
including a safety cap added in round 1 that silently recreated the very count-vs-match divergence
round 1 had just fixed. Round 2 currently inherits round 1's framing, so it re-asks "is this diff
correct" over a smaller diff, when the question that actually caught those defects is a different
one: *does this fix introduce the defect it fixed, somewhere else?*

The originating decision (`cla.io/decisions/open-issues-2026-08-24.md`, item **H**, GitHub #106)
proposes two things — encode that question, **and** make a second round the default. This change
does the first and explicitly declines the second, because the two have very different evidence
behind them. The question costs one paragraph of prose in a file the round already reads. The
default is a cost every run pays, and the evidence for it is one chain with three to four data
points, one still in flight when it was logged. A 100% hit rate across four changes is suggestive,
not a base rate.

## What Changes

- **Round N ≥ 2 of Revise gains its own framing question**, distinct from round 1's, carried in
  `spec-to-pr/references/revise.md` §"Round N (N ≥ 2)" and mirrored as a one-line invariant in
  `SKILL.md`'s Revise stub. The question binds an **enumeration** obligation, not just a re-read:
  every other instance of the resource or shape the fix concerns is listed, and each is stated as
  carrying the defect or not.
- **The round cap's description is corrected where it is stated.** Both sites that name
  `--pr-rounds` now say the default is a ceiling, not a target, so a reader stops mistaking
  `default 2` for a promise of two rounds. That is the whole edit, and it deliberately stops short of
  saying what *does* end the loop. **An earlier draft said the loop ordinarily ends at the exit gate,
  justified by "the untriaged count is zero by construction at the end of round 1". Both halves are
  false** — a reason-less rejection routes to untriaged, a loop holding open findings is ended by the
  cap, and the ledger shows four of the five logged runs that ran Revise using a second round the
  gate as written should have ended. The claim is gone from every file, the annotation it would have
  put at the exit gate was withdrawn rather than written, and the half-sentence stands without it.
- **The Revise phase record gains a later-round yield field** in
  `_shared/references/run-log-schema.md`, so the deferral above has an instrument that can end it.
  Today the ledger records `rounds_used` and a per-agent finding count summed across all rounds —
  nothing attributes a finding to the round that surfaced it, which is exactly the number needed to
  decide whether a second round earns its cost.
- **NOT changed: the `--pr-rounds` default, the exit gate's threshold, or anything that makes a
  second round run more often.** No new agent, no new script, no new hook.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `cla-plugin`: five ADDED requirements — a distinct framing question for a second review round; the
  three things that make its enumeration answerable and its answer checkable; an accurate statement
  that the round cap is a ceiling, with the cap left where it is; a per-round finding attribution in
  the run record so the declined default has a stated reversal condition someone can check; and the
  qualifying test a ledger field must meet to be kept for a deferred decision rather than for the
  aggregator.

## Impact

Prose and one schema field, all inside the shipped plugin tree. No executable code changes.

- `.claude/plugins/cla/skills/spec-to-pr/references/revise.md` — §"Round N (N ≥ 2)" gains the
  framing question, the three things that make it answerable, and the three-outcome check on the
  returned enumeration; §"For each round" step 1 gains that check; the `Cap:` line (line 5) gains
  its clarifying half-sentence. §"For each round" step 4, the exit gate, is **not** edited — the
  annotation an earlier draft planned there was withdrawn.
- `.claude/plugins/cla/skills/spec-to-pr/SKILL.md` — the Revise stub (line 329) gains the one-line
  invariant and the same cap clarification; the per-loop caps table (line 375) is left numerically
  unchanged.
- `.claude/plugins/cla/skills/_shared/references/run-log-schema.md` — the `Revise` phase object
  gains one optional field and its semantics paragraph.
- `cla.io/retro/spec-to-pr-runs.jsonl` — no migration. The field is optional and absent records stay
  valid; `spec_to_pr_aggregate.py` reads phase fields by name via `.get()`, so an unread field is
  ignored rather than bucketed as drift.
- Closes GitHub issue **#106**, partially and deliberately: the question is encoded, the default
  change is declined with a stated reversal condition rather than left open.

**Shared files across this batch.** Three files are touched by more than one change, and two earlier
statements of this were wrong — corrected here rather than left standing:

| file | changes touching it | shape |
|---|---|---|
| `spec-to-pr/references/revise.md` | `fix-brief-binding-defect`, this change | both append to §"Round N (N ≥ 2)"; additive, ordering constraint only |
| `spec-to-pr/SKILL.md` | `fix-brief-binding-defect` (Review, Revise stub), `delegate-liveness-contract` (Concurrent runs, brief citation, References), this change (Revise stub, Handoff) | **three** changes, and changes 1 and this one both add a bullet to the SAME Revise-stub list |
| `_shared/references/run-log-schema.md` | `fix-brief-binding-defect` (`rows_remeasured*` on the **`Review`** object), this change (`findings_by_round` on the **`Revise`** object) | different phase objects; no textual conflict expected, but the file is NOT this change's alone |

An earlier draft asserted "`run-log-schema.md` is touched by no sibling" and accounted only for
`revise.md`. Both were false. `review-change/references/checklist.md` and `subagent-brief.md` this
change genuinely does not open.

This change is last in the batch and edits last, so on every shared file it appends after the
siblings rather than ahead of them. Its task 1.3 reads each shared region as it actually stands
before editing — which is the only reason the two corrected claims above do not also make its tasks
wrong.
