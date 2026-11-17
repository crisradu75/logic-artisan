# Tasks

Owner-on-device tasks are marked **[owner, device]**. Every other task runs in an agent session on this machine.

The implementer runs on Opus, for three reasons: the skill writes the owner's files, it scores its own changes, and it is agent-instruction prose.

Ground rules for every task:
- Use scratch repos only, never a real domain.
- Each agent works in `scratchpad/add-mnemo-improve/`.
- Notes, questions, log lines, fixtures, prompts and issue texts all use invented placeholders.
- No task files on the real `mnemo-plugin`, except the probe in 1.2.

## 1. Verify first (gates later groups)

- [ ] 1.1 Confirm `add-check-scripts`, `add-guard-hooks`, `add-mnemo-setup`, `add-mnemo-capture`, `add-mnemo-recall` and `add-mnemo-review` are merged and archived. Done when `openspec list --specs` shows `note-schema`, `note-checks`, `domain-layout`, `domain-instructions`, `note-recall` and `review-scan`, and `openspec validate add-mnemo-improve --strict` prints no "target spec does not exist" line.
- [ ] 1.2 **[owner, device]** In a cloud session on a scratch domain with `mnemo-plugin` attached, run four REST calls through `gh api`:
  - the D9 search
  - a create of an issue titled `mnemo-improve: cloud filing probe`
  - a comment on it
  - a list of open issues

  Done when all four succeed. `measured:` each HTTP status. The owner then closes the probe issue by hand. If a call fails, stop here: the issue design changes.
- [ ] 1.3 **[owner, device]** Check that the domain-wall exception lets nothing else through.
  - Reuse `add-mnemo-setup`'s device tasks 1.1 and 1.2, if they ran these cases.
  - Otherwise, on a scratch domain set up by `mnemo-setup`, ask the session three things:
    - add `mnemo-plugin` to read its code (it must be refused);
    - add another scratch repo (refused);
    - add `mnemo-plugin` to file an approved loop issue (allowed).
  - Done when all three match. `scenario: domain-instructions / The plugin repository for another purpose refused`, `/ Another repository refused`, `/ The plugin repository for an approved loop issue allowed`.
- [ ] 1.4 **[owner, device]** In a cloud session on a scratch domain repo, confirm three things:
  - `git worktree add` under the system temp folder works;
  - a subagent can be started and can read that worktree;
  - `gh api -X POST repos/<o>/<r>/pulls` opens a PR from a pushed scratch branch. If it cannot, record whether the built-in GitHub tool does.

  Done when all three are recorded. A "no" on subagents blocks group 3 until design D7 changes.
- [ ] 1.5 Add `"repository": "https://github.com/crisradu75/mnemo-plugin"` to `plugins/mnemo/.claude-plugin/plugin.json`. No earlier change in the batch adds it. Add a test that the field is a non-empty `https://github.com/` URL. Done when the test and `claude plugin validate plugins/mnemo` pass.
- [ ] 1.6 On a scratch domain with 10 invented notes, run one D7 answerer subagent on one question. `measured:` tokens and seconds per answer, to state in `scorecard.md` as the per-answer cost.

## 2. Loop metadata (checks and setup)

- [ ] 2.1 Extend `mnemo_check.py schema`:
  - `questions` and `links` are optional inline lists;
  - notes in `hubs/` follow the hub rule;
  - notes in `archive/` follow the archive rule.

  Add one `unittest` per scenario, each tagged with its scenario:
  - `note-schema / Optional fields left out`, `/ Extra field`, `/ Date in another format`, `/ Tags not a list`, `/ Unknown status`, `/ Undeclared type`, `/ Missing type field`, `/ Wrong folder or name`
  - `loop-metadata / Hub passes without a declared type`, `/ Wrong type in the hubs folder`, `/ Archived note passes`, `/ Active note in the archive`

  Also add one test where `links: a.md` (not a list) is reported. Done when the touched test files pass.
- [ ] 2.2 Extend `mnemo_check.py links` for `links` field entries. Tests carry `scenario: note-checks / Entry names a missing note`, `/ Wrong letter case`, `/ Linked note deleted`. Done when they pass, and the existing `note-checks` tests still pass.
- [ ] 2.3 Update the setup templates:
  - add the folders `hubs/`, `archive/` and `_meta/tests/`, with keep files;
  - add a `questions.yml` template holding the D10 comment line only;
  - add write rules for those folders in `AGENTS.md`.

  Change `add-mnemo-setup`'s test 2.4 so it forbids only `mnemo_schema_version`, `index.md`, `log.md` and `.github/workflows/`. Tests carry `scenario: domain-layout / Fresh repo holds none of them`, `/ Folders survive a fresh clone`, `/ Fresh repo`, `/ Top-up keeps the owner's questions` and `domain-instructions / Agents file within limits`. Done when they pass.
- [ ] 2.4 Write a test-only validator for the test set in `tests/`, following D10. Test it on the template and on an invented one-entry example. `scenario: loop-metadata / Entry read back`. Done when it passes, and it fails on an entry missing `from`.
- [ ] 2.5 Recall: make `SKILL.md` follow `links` field entries one level. In recall's D11 static test, allow `links` only in that step; keep the bans on `questions` and `hubs/`. Done when the static test passes and fails again if `SKILL.md` names `questions`.
- [ ] 2.6 Review: reword `SKILL.md` and its test to match `review-scan` "Deferred metadata is not checked". Done when the test carrying `scenario: review-scan / Notes with base fields only` passes on a fixture that has `hubs/` and notes with `links`.

## 3. Skill files

- [ ] 3.1 Write the four reference files from design D5, D7 and D9, plus `pr-body.md` with the D6 provenance line and every section `improve-pull-requests` "Pull request body" names. Done when the packaged-path test passes.
- [ ] 3.2 Write `SKILL.md`, in this order: the D2 guards, then D3, D4, D5, D7, D8 and D9. Done when `claude plugin validate plugins/mnemo` and the packaged-path test pass.
- [ ] 3.3 Add static tests for `SKILL.md`. Done when the tests pass, and each one fails on a planted violation. `SKILL.md` must hold:
  - no `gh issue`, no `gh pr` and no `mnemo_check.py save`;
  - no bare `python3`;
  - no push to `main`;
  - no clone, push or PR on the plugin repository;
  - no step that starts `mnemo-review`;
  - the strings `[meta]`, `2 paraphrases`, `3 answers` and `2 of 3`.
- [ ] 3.4 Add the description test. `scenario: improve-triggering / Description length`. Add the hook-file test. `scenario: improve-run / Hook file names no run`.
- [ ] 3.5 Add a static test that `issue-body.md` lists only the D9 fields, and that `pr-body.md` has a provenance slot for each change. Done when both pass.

## 4. Trigger evals

- [ ] 4.1 Write improve's 20 prompts from design D12 in the evals folder. Each carries `scenario: improve-triggering / Maintenance request` or `/ Near-miss request`. Other skills' prompts are not edited.
- [ ] 4.2 Run `claude plugin eval` on improve's set. Done at 18 of 20 or better. `scenario: improve-triggering / Pass mark`. `measured:` the score and the misses.

## 5. Scratch-repo runs (real-file check)

Setup for these runs:
- The owner creates two private scratch repos: a scratch domain and a scratch issue target.
- Runs use `claude -p --plugin-dir <test copy of plugins/mnemo>`, with the copy's `repository` pointing at the scratch target. The guard hooks are loaded.
- The scratch domain is built from the setup templates, with invented notes and an invented query log.

After every run, check all of these and record each outcome in the PR body:
- `git status` in the session tree shows no loop change;
- the remote's `main` has no loop commit;
- the query log is byte-identical to before;
- `secrets --all` exits 0.

- [ ] 5.1 `manual: improve-run / Repo without a schema`, `/ Domain set up before this change`, `/ Earlier loop pull request still open`, `/ GitHub cannot be reached`, `/ Empty query log`: done when each stops with the stated message and nothing changes.
- [ ] 5.2 `manual: improve-run / Owner asks for maintenance`, `/ Recall finishes`, `/ Earlier run closed`, `/ First run`, `/ One broken line`, `/ Turn ends during a run`, `/ Run finished`: done when the covered lines and the unreadable count match the planted log.
- [ ] 5.3 `manual: improve-proposals`, all scenarios: done when each planted signal gives exactly the stated proposal, or no proposal.
- [ ] 5.4 `manual: improve-guardrails`, all scenarios: done when the branch diff touches only the four fields, every change cites `file:line`, the planted instructions appear only in the summary, and a decline or a refused push leaves GitHub unchanged.
- [ ] 5.5 `manual: improve-pull-requests`, all scenarios: done when the PR titles, contents, bodies and merge-order line match. A planted bad `links` entry blocks the push.
- [ ] 5.6 `manual: improve-scorecard`, all scenarios: done when the answer counts match design D7, the figures read `k/3`, the pass and fail verdicts match the stated rules on planted cases, and the log is byte-identical.
- [ ] 5.7 `manual: upstream-issues`, all scenarios, on the scratch target: done when the body check finds no planted `q`, `user` or note text, and a matching open issue gets a comment, not a new issue. The transcript holds no `gh issue`. The refusal case is run with a revoked token, which leaves the target unchanged.
- [ ] 5.8 `manual: note-recall / Answer sits in a note named in the links field`, `/ Answer sits in a linked note`, `/ Links stop at one level`: done when recall cites the expected notes.

## 6. Release

- [ ] 6.1 Bump `plugins/mnemo/.claude-plugin/plugin.json` to `0.8.0`, or to the next minor version above `main` if the merge order changed. Done when `claude plugin validate plugins/mnemo` passes.

## 7. Integration

- [ ] 7.1 Save `git status --porcelain --ignored --untracked-files=all` outside the repo. Run `python -m unittest discover -s tests` once on the final commit, then diff the status. Done when the suite passes and no new line appears outside `scratchpad/`.
- [ ] 7.2 **[owner, device]** Run maintenance end to end from the iPhone on the scratch domain, with `mnemo-plugin` attached. Done when:
  - the domain PR and the `[meta]` PR open after the owner's yes;
  - one approved issue or comment lands on the real `mnemo-plugin`, holding counts and rule text only;
  - the owner closes it by hand afterwards.
- [ ] 7.3 `manual: No note content: confirm by reading that SKILL.md, every reference file, every fixture, every eval prompt and every example log line and issue body use invented placeholders, as the repo rules require.`
- [ ] 7.4 docs and spec map:
  - `plugins/mnemo/skills/README.md`: `mnemo-improve` exists; what it reads; the two PR kinds; issues.
  - `README.md`: how to run maintenance; the new folders; the `repository` field.
  - `CLAUDE.md`: issues titled `mnemo-improve: …` come from the loop, and each becomes an OpenSpec change before any code changes.

## Workflow follow-up

- Archive this change last in the batch, after the six changes whose capabilities it modifies.
- In `crisradu75/research`, record that additive-only, the never-list, the weekly scheduled task and Actions scoring are replaced by the self-improvement decision (its first follow-up).
- Once a real domain exists, re-run group 5's proposal and scorecard runs on a scratch clone of it, never on the real working copy.
