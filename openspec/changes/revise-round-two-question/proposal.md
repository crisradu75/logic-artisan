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
- **The round cap's description is corrected where it is stated.** `--pr-rounds` already defaults
  to `2`, so the cap has never been what ends Revise early; the exit gate at step 4 — zero
  *untriaged* Critical/Important findings — is. Because step 2 requires every Critical and Important
  finding to be triaged in the round that surfaced it, that count is zero by construction at the end
  of round 1, so as written the loop ordinarily exits there and the default cap never binds. The
  skill will say so at the point it names the cap, so a reader stops mistaking `default 2` for a
  promise of two rounds.
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

- `cla-plugin`: three ADDED requirements — a distinct framing question for a second review round;
  an accurate statement of what ends the Revise loop, with the round cap left where it is; and a
  per-round finding attribution in the run record so the declined default has a stated reversal
  condition someone can check.

## Impact

Prose and one schema field, all inside the shipped plugin tree. No executable code changes.

- `.claude/plugins/cla/skills/spec-to-pr/references/revise.md` — §"Round N (N ≥ 2)" (line 68) gains
  the framing question; §"For each round" step 4 (line 134) gains the accurate exit-gate statement;
  the `Cap:` line (line 5) gains its clarifying half-sentence.
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
