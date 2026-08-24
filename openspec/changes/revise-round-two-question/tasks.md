## 1. Re-anchor before editing

- [ ] 1.1 Re-run the anchor measurements and record the values inline, because every line number in `design.md` is stale the moment a sibling change lands: `wc -l .claude/plugins/cla/skills/spec-to-pr/references/revise.md .claude/plugins/cla/skills/spec-to-pr/SKILL.md .claude/plugins/cla/skills/_shared/references/run-log-schema.md` — measured: `<paste the three counts>`
- [ ] 1.2 Locate every edit site by content, not by line number: `grep -n 'pr-rounds' .claude/plugins/cla/skills/spec-to-pr/references/revise.md .claude/plugins/cla/skills/spec-to-pr/SKILL.md` and `grep -n 'Round N (N ≥ 2)\|Exit gate' .claude/plugins/cla/skills/spec-to-pr/references/revise.md` and `grep -n '"name": "Revise"\|revise_findings_by_tier' .claude/plugins/cla/skills/_shared/references/run-log-schema.md` — measured: `<paste the hits>`
- [ ] 1.3 Confirm the sibling change `fix-brief-binding-defect` has already landed its own edits to `revise.md` §"Round N (N ≥ 2)" and to the INT-CAP step, and read what it left there. This change is last in the batch and appends after it; if that change has NOT landed, note it and proceed anyway — the edits are additive paragraphs in the same section, not a rewrite.
- [ ] 1.4 Read the paragraph immediately before and immediately after each insertion point **in the file**, not from memory of it, per the repo's ordered-sequence check. §"Round N (N ≥ 2)" ends on a defensive fallback sentence about an empty `PREV_FIX_SHA`; the inserted paragraph must not read as a condition on that fallback.

## 2. The round-≥2 question

- [ ] 2.1 In `revise.md` §"Round N (N ≥ 2)", append the framing question as a quoted block, verbatim from `design.md` "Pinned implementation parameters": "Does this fix introduce the defect it fixed, somewhere else? Enumerate every other instance of the resource or shape the fix concerns."
- [ ] 2.2 Immediately after it, add the enumeration obligation verbatim from the same pinned block — the enumeration is the deliverable, per-instance verdicts, and an empty enumeration as a stated result rather than a skipped step.
- [ ] 2.3 State in the same paragraph that the question is what the round's Agent prompts carry, so it reaches the reviewers rather than only the orchestrator: the existing "Inline the scoped diff into each agent's prompt" sentence is the right anchor.
- [ ] 2.4 In `SKILL.md`'s Revise stub, add one invariant bullet carrying the question and the enumeration obligation, since the stub must stay self-sufficient when `revise.md` is not reloaded. Keep it to one bullet — the stub is a list of one-liners and a paragraph there breaks its shape.
- [ ] 2.5 Verify the question text is byte-identical in both files and matches `design.md`: `grep -n 'introduce the defect it fixed' .claude/plugins/cla/skills/spec-to-pr/references/revise.md .claude/plugins/cla/skills/spec-to-pr/SKILL.md openspec/changes/revise-round-two-question/design.md` — measured: `<paste the hits>`

## 3. What actually ends the loop

- [ ] 3.1 In `revise.md`, extend the `Cap: --pr-rounds N (default 2).` line with the exit-gate clarification: the loop ordinarily ends at the exit gate, not at the cap, because every Critical and Important finding is triaged in the round that surfaced it.
- [ ] 3.2 Apply the same clarification to the `Cap:` sentence in `SKILL.md`'s Revise stub.
- [ ] 3.3 In `revise.md` §"For each round" step 4 (`**Exit gate.**`), state what the untriaged count means at the end of round 1 — zero by construction under step 2's triage rule — phrased as an observation about the count, NOT as a new rule and NOT as a change to the threshold.
- [ ] 3.4 Do not touch the per-loop caps table in `SKILL.md`. Confirm no cap moved: `grep -n 'pr-rounds\|review-rounds\|test-rounds' .claude/plugins/cla/skills/spec-to-pr/SKILL.md .claude/plugins/cla/skills/spec-to-pr/references/revise.md` shows `--pr-rounds` default `2`, `--review-rounds` default `1`, `--test-rounds` default `3`, unchanged — measured: `<paste the hits>`

## 4. The declined default and its reversal condition

- [ ] 4.1 In `revise.md`, beside the round-≥2 question, state the deferral in two or three sentences: a second round is not unconditional; the evidence is one chain of three to four changes with one still in flight; a hundred-percent rate on a denominator of four is suggestive, not a base rate.
- [ ] 4.2 Add the reversal condition verbatim from `design.md`'s pinned block, and label the eight-change denominator and the majority bar as stated judgements rather than measurements. The two-chain floor is the originating decision's and carries its authority.
- [ ] 4.3 State, in `revise.md`, that this position is the same one `fix-brief-binding-defect` defers to — no round cap is raised by either change — so a reader of both sees one position rather than two. Do not name the sibling change by name in the shipped file (it will not exist in a consuming repo); state the position, not the cross-reference.

## 5. The ledger field

- [ ] 5.1 In `_shared/references/run-log-schema.md`, add `findings_by_round` to the `Revise` phase object in the JSON skeleton, matching the surrounding formatting: an array of `{"round": N, "found": N, "sibling_instance": N}` in round order, one entry per dispatched round.
- [ ] 5.2 Add the field's semantics paragraph beside the `revise_findings_by_tier` note: `found` is the round's deduplicated Critical-plus-Important count after triage; `sibling_instance`'s definition verbatim from `design.md`'s pinned block; `0` on round 1 by construction; the field is optional and absent on older records; absent is distinguishable from `found: 0`.
- [ ] 5.3 State the non-equality explicitly in that paragraph: `findings_by_round[*].found` is NOT expected to equal the sum of `routing.revise_findings_by_tier[*].found`, because the per-agent field credits one finding to every agent that surfaced it. This is the sentence that stops a later reader planting a false invariant between two fields both spelled `found`.
- [ ] 5.4 Add the reversal condition to the same note, so the field says what it is for at the point someone reads its shape.
- [ ] 5.5 In `SKILL.md`'s Handoff invariants, extend the run-log bullet so the producer obligation is named where the record is assembled — `findings_by_round` is built at triage time from what each round actually found, not reconstructed afterwards from memory of the rounds.

## 6. Verify

- [ ] 6.1 Confirm no script change was needed: `log_run.py` validates only the ledger filename shape, UTF-8, that the top level is an object, and the 4 KiB ceiling — `grep -n 'def main' -A 60 .claude/plugins/cla/lib/log_run.py | grep -n 'allowlist\|phases\|Revise'` returns nothing — measured: `<paste the result>`
- [ ] 6.2 Confirm the aggregator ignores the new field rather than bucketing it as drift: `grep -n 'findings_by_round\|malformed' .claude/plugins/cla/skills/spec-to-pr-retro/scripts/spec_to_pr_aggregate.py` shows the malformed bucket is scoped to `revise_findings_by_tier` only — measured: `<paste the hits>`
- [ ] 6.3 Run the synced-core conformance guard over the three edited files, since all three ship verbatim to consuming repos: `python .claude/plugins/cla/skills/_shared/scripts/check_no_project_tokens.py` — measured: `<paste exit status and any violations>`
- [ ] 6.4 Run the area suite once: `pytest plugin-tests/tests/skills` — measured: `<paste the summary line>`
- [ ] 6.5 Run the full gate before opening a PR, each once: `pytest plugin-tests` and `node --test plugin-tests/node/mechanical-checks.test.mjs` — measured: `<paste both summary lines>`
- [ ] 6.6 Diff-review the three files against their pre-change state and state what, if anything, was dropped — none of these edits is a rewrite, so the expected answer is "nothing"; if it is not, that is the finding.
- [ ] 6.7 Confirm the round-count claim this change makes is true of the tree it leaves: the only edits to a cap value anywhere in the diff are zero. `git diff --unified=0 -- .claude/plugins/cla/skills/spec-to-pr/ | grep -n '^[+-].*rounds' ` shows no line changing a default — measured: `<paste the result>`
