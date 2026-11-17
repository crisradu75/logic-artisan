# Proposal

Budget: protected

## Why

Recall logs every question, but nothing turns those signals into better notes or rules. The recursive-self-improvement decision (Q1–Q7, Q10) and structure Q14 settle how a loop may do that: on demand, through PRs the owner merges and issues the owner approves, with provenance and a scorecard, and without ever touching a note's body. This change builds that loop as the fifth skill, last, after `add-check-scripts` and the other skills land.

## What Changes

- Add the `mnemo-improve` skill under `mnemo-plugin/skills/`. A domain session starts it with "run Mnemo maintenance"; there is no schedule.
- It reads the domain's query log, proposes changes with the log lines behind each, and opens domain PRs (content changes, and separate `[meta]` PRs) with a diff, provenance and a scorecard.
- It sends everything that belongs to `mnemo` (the loop itself, the scorer, the Mnemo copy) as an issue on `mnemo`, filed or commented through `gh api` after the owner approves the text.
- Add the metadata deferred until now (structure Q14): optional loop-owned `questions` and `links` note fields, `hubs/` and `archive/` note folders, the test set `_meta/tests/questions.yml`, and a `mnemo_schema_version` key in the domain schema. No existing note needs rewriting.
- Bump `VERSION`.

## Capabilities

### New Capabilities

- `improvement-loop`: when a run starts and stops, what it may change and where each change lands, and what every PR shows.
- `loop-scorecard`: the main-versus-branch comparison each PR carries.
- `upstream-issues`: how an approved proposal reaches `mnemo` as an issue, and what may leave a domain.

### Modified Capabilities

- `note-checks` (created by `add-check-scripts`, archived first): adds the deferred note fields, folders and schema key.

## Impact

- New: `mnemo-plugin/skills/mnemo-improve/`, test-set format, tests under `tests/`, trigger prompts under `evals/`.
- Changed: the base schema in `mnemo-plugin/mnemo/conventions/`; `VERSION`.
- Domains get the skill through a refresh PR from `mnemo-setup`; the domain `CLAUDE.md` exception for `mnemo` (Q10) is written by `add-mnemo-setup`, not here.

## Risks noted

- An interrupted run can leave a pushed branch with no PR; the next run does not see it as an open loop PR and may propose the same change again.
- `gh api` from a cloud session is unverified (decision Noted); filing may fail until a device test confirms it.
- A failure after the duplicate search but before the issue is created leaves nothing filed; the owner re-runs.
- Three answers per side is a small sample; the scorecard's spread figure shows how much a result moves.
- Nothing improves unless the owner starts a run (accepted, Q4).

## Open questions

1. **What counts as a correct answer on the scorecard?** The decisions fix the question set and run count, not the score. Recommended: an answer is correct when it cites the question's answering note; the scorecard has no pass mark (the merge is the gate, Q5) and marks each question where the branch scores below `main`. Specified that way.
2. **Which PR labels?** Structure Q14 defers "PR labels" until now but marks `[meta]` by title prefix, not label. Recommended: no labels; the prefix carries the only distinction. Not specified.
3. **What do `hubs/` and `archive/` hold?** The decisions name them but not their use. Recommended: this change only makes them note folders the checks treat like any other; the skill that first writes them specifies their use.
4. **What a `[meta]` PR can hold.** Q5 sends loop, scorer and guardrail changes to a `[meta]` PR, but Q1 sends every change to the loop's skill or scorer, which live in `mnemo`, out as issues. Recommended: in a domain repo a `[meta]` PR holds test-set changes only. Specified that way.
5. **Uncommitted notes when a run starts.** The decisions are silent. Recommended: the run stops and asks the owner to save first, so scoring never switches branches over unsaved work. Specified that way.
