# Proposal

Budget: protected

## Why

The query log records every recall, but nothing turns it into better recall. The owner decided how the loop works (recursive self-improvement Q1–Q7, Q10, with Q8–Q9 for the log; structure Q14; architecture Q12–Q14 in `cla.io/decisions/mnemo-benchmark-batch-2026-11-18.md`). The loop is the one Mnemo part that proposes changes to a domain holding the owner's notes, so its limits must be enforced, not just written down.

## What Changes

- New domain skill `mnemo-plugin/skills/mnemo-improve/`: an on-demand run ("run Mnemo maintenance") that reads the query log and proposes domain changes as PRs the owner merges, and everything else as approved issues on `mnemo`.
- Each loop PR carries the diff, a targeted scorecard (main vs branch) and provenance; `[meta]` PRs are separate and get the full-set scorecard.
- Issues go to the stamp's `repository` key through GitHub's REST API, deduplicated, counts only.
- A standard-library helper script beside `mnemo_check.py` holds the parts that must be tested (see `design.md`).
- Deferred metadata (structure Q14), add-only: `questions` and `links` fields, `mnemo_schema_version`, and the test set `_meta/tests/questions.yml`.
- Bumps `VERSION`.
- Out of scope: the check scripts and `save` (`add-check-scripts`), the stamp file and the domain `CLAUDE.md` rule (`mnemo-setup`), the recall skill and its log writing, the Stop hook, and trigger prompts or evals for this skill (architecture Q9; Open question 10).

## Capabilities

### New Capabilities
- `improve-loop`: when a run starts and stops, what a loop PR may change, provenance, `[meta]` PRs.
- `improve-scorecard`: which questions are scored, against what baseline, and what a figure means.
- `improve-issues`: target, approval, deduplication and content of issues on `mnemo`.
- `loop-metadata`: the add-only fields, schema version key and test set format.

### Modified Capabilities
None.

## Impact

New skill and helper script in `mnemo-plugin/`, two optional base-schema fields and a version key, new tests in `tests/`. Applies only after `add-check-scripts` merges (base schema, YAML subset, check script). A real run also needs `mnemo-recall` (scoring), `mnemo-setup` (stamp, domain rule) and the Stop hook, none yet proposed; until the stamp exists a run files no issue and asks (Q7).

## Risks noted

- Two sessions (laptop and cloud) starting runs at once can both pass the open-PR check and open two PRs; the owner closes one.
- A malformed query-log line is skipped and counted in the run report, never fatal.
- Scoring costs model calls (2 sides × 3 answers per question); a cut-off run opens no PR and the next run starts over.
- The `links` frontmatter field's targets are not checked by this change.
- A filing whose reply is lost may add one repeat comment on retry; the search prevents a second issue.
- A leftover temporary worktree from a killed run is pruned at the next run's start.

## Open questions

1. **Which log lines a run reads** (silent). Recommend: lines dated on or after the day the newest loop PR was opened, whatever its state; the first run reads all.
2. **What a scorecard pass is** (silent). Specified as in `design.md`: the answer cites the question's expected note, or, when the change edits no note, any note.
3. **Provenance vs counts-only in issues.** "Every proposed change cites the query-log lines" collides with "nothing leaving a domain carries question text or note content" (log lines name notes). Specified: PRs cite the lines; issues carry only what counts-only allows, with no line-level provenance. Recommend: issues state counts per result and a date range; owner to decide.
4. **PR labels and `hubs/`, `archive/`** (Q14 defers them, with no behaviour). Recommend: no label (Q5 marks meta by title prefix; loop PRs are found by branch prefix); the folders are created by `mnemo-setup`'s next refresh; the loop never moves notes into `archive/` until the owner decides moves.
5. **`mnemo_schema_version` location and value** (silent). Recommend a top-level base-schema key starting at `1`, raised when a field is added.
6. **Missing stamp key: what improve asks** (Q7 says "stops and asks"). Recommend: ask the owner to refresh with `mnemo-setup`; accept no target typed in the session, since Q10 allows only `mnemo`.
7. **If `gh api` is also blocked in cloud sessions** (unverified, owner-run gate). Recommend: the run shows the approved text for the owner to file by hand; no other route.
8. **`[meta]` PRs (Q5) vs issues (Q1, Q7).** Q5 sends loop, scorer and guardrail changes to `[meta]` PRs; Q1's clarification and Q7 send every change to anything in `mnemo` or the Mnemo copy, where those live, to issues. Specified as decided: `[meta]` covers such items held in the domain. Recommend: the owner confirms the test set is the only domain-held meta item, so scorer, guardrail and loop changes go out as issues.
9. **Built last vs batch order.** Structure Q1 and the self-improvement decision say `mnemo-improve` is built last, after its dependencies; this batch sequences it second, before recall, setup and the hooks exist. Recommend: keep the proposal, and apply it only after those changes merge.
10. **Trigger prompts for this skill** (architecture Q9). No change owns them. Recommend: the evals change adds a "run Mnemo maintenance" prompt.
