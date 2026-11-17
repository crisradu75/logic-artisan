# Tasks

## 1. Deferred metadata

- [ ] 1.1 Add optional `questions` and `links` to the base schema and make `hubs/` and `archive/` note folders; tests with `scenario: note-checks / Existing note without the new fields`, `/ Note in hubs` and `/ Schema version key` comments pass, and the pinned required set is unchanged.
- [ ] 1.2 Define the test-set format of design.md; a test reads an invented `_meta/tests/questions.yml` with the schema reader, and an empty or missing file yields an empty set.

## 2. Helper script: guards and filters

- [ ] 2.1 Body and path guard; tests with `scenario: improvement-loop / Proposal touches a body`, `/ Attachment`, `/ Allowed field` and `/ Change to the copied check script` comments, on scratch repos with invented notes.
- [ ] 2.2 Kept-rule guard; a test with a `scenario: improvement-loop / Proposal weakens a kept rule` comment drops a candidate that edits either kept rule's text in conventions or the skill.
- [ ] 2.3 Leak filter; tests with `scenario: upstream-issues / Draft quotes a question` and `/ Draft holds a secret pattern` comments, using an invented query log and invented secrets.
- [ ] 2.4 Provenance check; tests with `scenario: improvement-loop / Provenance shown` and `/ No signal behind a change` comments: a candidate without log lines is rejected, and the PR body lists date, result, opened and cited paths.

## 3. Helper script: scorecard

- [ ] 3.1 Question selection; tests with `scenario: loop-scorecard / Change to one note`, `/ No test set yet` and `/ Test question removed` comments.
- [ ] 3.2 Figures and marking; a test with a `scenario: loop-scorecard / Branch is worse on one question` comment checks "k of 3", the spread string and the mark.
- [ ] 3.3 Baseline and trace; tests with `scenario: loop-scorecard / Remote main moved` and `/ After scoring` comments, on a scratch repo with a local bare remote, assert the `main` side uses the pushed commit and the query log and history are unchanged.

## 4. Helper script: issues

- [ ] 4.1 Target lookup; tests with `scenario: upstream-issues / Key present` and `/ Key missing` comments read invented stamp files.
- [ ] 4.2 Dedupe against a fake `gh` on `PATH`; tests with `scenario: upstream-issues / Matching open issue` and `/ No match` comments assert one comment or one create call, and that no `gh issue` call is made.
- [ ] 4.3 Approval gate; a test with a `scenario: upstream-issues / Owner declines` comment asserts the fake `gh` receives no write call when approval is withheld.
- [ ] 4.4 Repo wall; tests with `scenario: upstream-issues / Another repository` and `/ Write to Mnemo` comments assert the helper refuses any target other than the stamp's and makes only issue calls on it.

## 5. The skill

- [ ] 5.1 Write `mnemo-plugin/skills/mnemo-improve/SKILL.md` calling the helper; the shipped-layout and path-map tests pass, and `VERSION` is bumped.
- [ ] 5.2 Start and stop; tests with `scenario: improvement-loop / Not a Mnemo repo`, `/ Empty query log`, `/ Loop PR already open` and `/ Uncommitted note at the start` comments call the helper's pre-run check on scratch repos and a fake `gh`.
- [ ] 5.3 Add trigger prompts for the skill to `evals/`; a `claude -p` trigger test with a `scenario: improvement-loop / Owner asks` comment meets the 18-of-20 pass mark against a scratch domain repo.
- [ ] 5.4 Before merge, run the skill once for real on a scratch domain repo with invented notes and a seeded query log; it covers these whole-run scenarios:
  - manual: improvement-loop / Run finishes: whole-run behaviour, checked on the real scratch run.
  - manual: improvement-loop / Domain rule: whole-run behaviour, checked on the real scratch run.
  - manual: improvement-loop / Owner's merge is the only gate: whole-run behaviour, checked on the real scratch run.
  - manual: improvement-loop / Change to the loop's own skill: whole-run behaviour, checked on the real scratch run.
  - manual: improvement-loop / PR body: whole-run behaviour, checked on the real scratch run.
  - manual: improvement-loop / Run with both kinds: whole-run behaviour, checked on the real scratch run.
  - manual: improvement-loop / Proposed summary holds a secret: whole-run behaviour, checked on the real scratch run.
- [ ] 5.5 manual: upstream-issues / Another repository: the domain `CLAUDE.md` exception is confirmed by the device test the decision names, once `add-mnemo-setup` writes it.

## 6. Docs

- [ ] 6.1 docs and spec map: `README.md` (the improve skill and how to start it), `mnemo-plugin/skills/README.md` (skill list); none affected for `CLAUDE.md`: no rule changes.
