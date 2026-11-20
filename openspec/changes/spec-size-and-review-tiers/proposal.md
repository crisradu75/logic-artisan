# Proposal

Budget: protected

## Why

`/cla:review-change` sends a change to the three-agent review when it has more than 20 subtasks, even when nothing else about it is large. That costs three agents for task count alone. `/cla:multi-spec` authors write proposals past the config's per-artifact word limits, and the budget check after authoring is information only, so nothing cuts them. Both behaviours ship to every installing repo. The owner decided Q4 and Q5 in `cla.io/decisions/open-issues-2026-11-21.md`.

## What Changes

- Review sizing (Q4): the subtask count alone no longer grades a change Large. The exception is a proposal carrying the line `Budget: protected`, read the way the budget checker reads it. The complexity-concentration override and the file, capability and claim thresholds stay as they are. The review's mode line says whether the marker was read.
- multi-spec authoring (Q5): before reporting `done`, the author checks the whole-change budget with `check_spec_proof.py` and the proposal and design word limits with `wc -w`, then cuts what is over. It never cuts a requirement that guards a protected area, and never cuts an open question. It reports what still does not fit, and the batch goes on.
- multi-spec's batch review gate reuses the checklist's size gate, so Q4 reaches it with no edit there.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `change-workflow`: one ADDED requirement for review sizing.
- `change-chains`: two ADDED requirements for the author's self-check.

## Impact

Shipped prose only: `review-change/references/checklist.md`, `multi-spec/references/authoring-brief.md`, and the parenthetical in `multi-pr/references/discover-and-gate.md` that predicts small or large from the subtask count. No script, hook or test is added. `check_spec_proof.py` is unchanged. Every line the decision file cites was re-read on the current `main` and still holds.

## Risks noted

- A protected change whose author leaves out `Budget: protected` gets the lighter review. The decisions accept this.
- An author's self-cut may drop something the spec review must catch. The decisions accept this.
- An author that skips the self-check is caught later only by the review's Size check, which grades a word overrun as a Suggestion.

## Open questions

1. Q4 affects only changes that list 3 to 5 files. Under the kept concentration override, a change with 15 or more subtasks in one or two files stays Large. **Recommend:** specify as decided.
2. The decisions do not say what the review does with a `Budget:` line it cannot honour, such as a misspelled value. **Recommend:** grade as unmarked, and report the line as an Important finding. The Size check already runs the checker that prints it.
3. "Over" a per-artifact limit needs a concrete reading. **Recommend:** any `wc -w` count above the config's figure is over. proposal.md is counted without its `## Open questions` and `## Risks noted` sections, as the review's Size check counts it.
