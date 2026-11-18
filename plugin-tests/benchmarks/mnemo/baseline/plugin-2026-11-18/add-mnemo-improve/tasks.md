# Tasks

Apply only after `add-check-scripts` is merged. Every test builds a scratch domain repo in a temporary folder, with invented notes, a bare repo as remote and a fake `gh` on `PATH` that records calls and returns canned JSON. Answers for scoring come from a canned file. No task reads or writes a domain repo or the owner's notes. Each test carries a `scenario: <spec> / <heading>` comment line for every heading it names.

## 1. Owner-run gates (outside what apply can tick; groups 2–8 are not blocked on them unless the owner says so)

- [ ] 1.1 In a cloud session with a scratch repo attached, the owner confirms `gh api` (REST) can list, comment on and create issues, open a PR, and push a branch named `mnemo-improve/<date>-content`. Record the result in the PR; on failure see proposal Open question 7.
- [ ] 1.2 Once `mnemo-setup` writes the domain `CLAUDE.md` rule, the owner runs the device test on a scratch domain: a request for another repository is refused (self-improvement Q10).
- [ ] 1.3 Once `mnemo-recall` exists, the owner runs the skill once on a scratch domain.
  - manual: improve-loop / Owner asks: needs a live session
  - manual: improve-loop / Mixed run: needs a live run opening both PRs
- [ ] 1.4 During that live run, the owner checks model judgement.
  - manual: improve-loop / Domain rule: needs model judgement
  - manual: improve-loop / Change to a Mnemo skill: needs model judgement
  - manual: improve-loop / Log pushes for a body fix: needs model judgement
- [ ] 1.5 During that live run, the owner checks approval.
  - manual: improve-issues / Owner declines: approval happens in conversation
  - manual: improve-issues / Owner edits the text: approval happens in conversation
- [ ] 1.6 During that live run, the owner checks scoring with real recall subagents.
  - manual: improve-scorecard / Note newer than the branch: the side restriction is an instruction to a subagent
  - manual: improve-scorecard / Log unchanged after scoring: canned answers write no log line

## 2. Helper skeleton

- [ ] 2.1 Create `mnemo_improve.py` with subcommand dispatch, exit statuses 0, 1 and 2, and `sys.dont_write_bytecode` set before importing the reader from `mnemo_check.py`. Check: every subcommand runs in a scratch domain and no `__pycache__` appears there.
- [ ] 2.2 Add the REST wrapper: `gh api` only, `GH_PROMPT_DISABLED=1`, a 30-second limit, all pages. Check: the fake `gh` records no `gh issue` or `gh pr` call.
- [ ] 2.3 Add temporary worktrees outside the session folder for the loop branch and each side, removed on exit or interrupt. Check: after a normal and a killed run, `git worktree list` shows only the session.

## 3. Loop metadata

- [ ] 3.1 Add `questions` and `links` to the base schema's `optional` list and `mnemo_schema_version: 1` as a top-level key; bump `VERSION`. Tests for loop-metadata: "Old note still passes", "Version key present". Check: the add-only base-schema test passes.
- [ ] 3.2 Read the test set in the design's block format. Test for loop-metadata: "Valid test set".

## 4. Start, log and guards

- [ ] 4.1 Add `start`: schema guard, loop PRs in any state, leftover branch check, stale worktree prune. Tests for improve-loop: "Not a Mnemo repo", "Loop PR open", "Branch left by an interrupted run", "Merged PR's branch remains".
- [ ] 4.2 Add `signals` with the design's log window. Tests for improve-loop: "No log yet", "Only blank or malformed lines", "Unsupported change dropped".
- [ ] 4.3 Add `guard` on a loop branch's diff. Tests for improve-loop: "Alias added", "Body edit refused", "Sources and deletions refused", "Content PR stays clean"; plus one refusing a change to each Mnemo-copy path.

## 5. Scorecard and PR

- [ ] 5.1 Add `score`'s question set. Tests for improve-scorecard: "Targeted content PR", "Meta PR", "Test set edited"; for loop-metadata: "No test set".
- [ ] 5.2 Add the sides at the starting commit. Tests for improve-scorecard: "Main moves during the run", "Note newer than the branch" (the side worktree holds no newer file); for loop-metadata: "Answering note gone".
- [ ] 5.3 Add the tally of canned answers. Tests for improve-scorecard: "Partial passes", "Side not measured", "Totals show spread"; plus a conventions-PR pass case.
- [ ] 5.4 Test that the helper writes nothing under the domain while scoring. Tests for improve-scorecard: "Log unchanged after scoring", "Next run ignores paraphrases".
- [ ] 5.5 Add `open-pr`: provenance, checks on the branch, push and open. Tests for improve-loop: "Complete PR", "Provenance in a PR", "Scoring cut off", "Secret in a loop change", "Run complete".
- [ ] 5.6 Run start, guard, scoring and `open-pr` against a scratch domain holding an uncommitted note, then kill a run partway. Tests for improve-loop: "Capture waiting during a run", "Run interrupted", "Nothing scheduled".

## 6. Issues

- [ ] 6.1 Add stamp target reading. Tests for improve-issues: "Target set", "Key missing" (fake `gh` records no call).
- [ ] 6.2 Add `issue-check`. Tests for improve-issues: "Logged question in the draft", "Note path in the draft" (tracked and untracked), "Counts only".
- [ ] 6.3 Add `issue-file` (search, comment or create). Tests for improve-issues: "Open match", "No match", "Retry after a lost reply", "After filing", "Other repository asked for", "Network failure", "No answer" (a fake `gh` that never answers; assert elapsed time).

## 7. Skill

- [ ] 7.1 Write `mnemo-plugin/skills/mnemo-improve/SKILL.md` calling the helper for every guard, with the schema guard first. Check: the shipped-layout test passes, and a test asserts the skill names every helper subcommand and calls `start` first.

## 8. Docs

- [ ] 8.1 docs and spec map: `README.md` (how to start a run, where issues go), `mnemo-plugin/skills/README.md` (the improve skill), or none affected: `CLAUDE.md`: no rule changes.
