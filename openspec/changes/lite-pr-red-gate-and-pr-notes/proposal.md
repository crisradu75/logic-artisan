# Proposal

Budget: protected

## Why

`/cla:lite-pr` spends its one fix on any red test, including one already failing before the change. It treats a network blip as a defect, never checks whether a parallel session built the same change, and never says which checks ran. The behaviour ships to every installing repo. The owner decided Q1, Q2, Q4, Q8 and Q9 in `cla.io/decisions/autocraft-adoptions-2026-11-21.md`.

## What Changes

- Test: a failing test that shares no file with the change is labelled probably already failing on the base branch, judged by reading alone. When the user is present, they decide whether to ship with a known-failing note. Under `/cla:multi-lite` the run halts.
- Test: a failure that shows no code error and names an unreachable network or service gets one reported rerun, which does not use the one fix.
- A new failure-only reference holds Q2's handling, all of Q4 and the long-log rule. SKILL.md gains only the label sentence, the pointer to the reference, the Plan search and the `Checks:` line.
- Plan: one read-only duplicate-work search, which does nothing when the repo has no GitHub remote.
- Ship: a `Checks:` line next to `Risk:` in the PR body.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `change-workflow`: six ADDED requirements for lite-pr's Test, Plan and Ship.

## Impact

Shipped: `lite-pr/SKILL.md` and one new reference, plus the ledger, changelog and docs. No script, hook or test is added. Every line the decision file cites was re-read on the current `main`, and each still holds.

## Risks noted

- If the base branch is already red, every candidate in a `/cla:multi-lite` batch halts on the same label. The label names the test, so the cause shows in one place.
- Sibling pull requests in a batch can show up as likely duplicates. Unattended runs only name them.
- A key-word search can miss a duplicate. The search is a courtesy, not a guarantee.

## Open questions

1. The Q8 wait and the Q2 ask contradict lite-pr's "Stops only on an unresolved test failure" (in its description and in Autonomy) and Plan's "no pause". **Recommend:** amend those sentences in place, and count the words in the load measurement.
2. Q2 does not say what happens when the user declines. **Recommend:** treat the test as an unlabelled failure, so it gets the one fix, then the diagnose offer, then the HALT.
3. Is the rerun limited per run or per failing tier? **Recommend:** at most one per run.
4. "Recent commits" needs a default. **Recommend:** the base branch's last 50 commits, read from the local ref.
5. When both apply, which comes first, the rerun or the label? **Recommend:** the rerun, so a rerun that stays red can then be labelled.
