# Tasks

Settle the proposal's `## Open questions` with the owner before group 2. Tasks 2.1, 2.2, 3.2 and 3.4 follow the recommended answers unless the owner picks otherwise.

**Every shipped edit (files under `.claude/plugins/cla/`) cites no issue or pull request number of this repo.** State the lesson in words. Check (e) of `check_no_project_tokens.py` fails on a `#NNN`.

## 1. Baseline

- [ ] 1.1 Before any shipped edit, run `measure_load.py --skill lite-pr` and record its `profile:` words as a `measured:` note here. At proposal time it read 4,690, but re-measure, since `main` may have moved. measured:

## 2. The failure-only reference (new `lite-pr/references/red-gate.md`)

- [ ] 2.1 Write the reference that is read only when a test fails. It covers the attended ask and the unattended halt for a labelled failure, with a decline handled as an unlabelled failure. It sets the long-log rule: over 4,000 characters, read the first error and the final summary.
- [ ] 2.2 In the same reference, add the one rerun. It triggers only when the log shows no failed assertion, compiler error or test error and names an unreachable network or service; a timeout alone is no trigger. It runs at most once per run, before the label, spends no fix, and is reported.
- [ ] 2.3 Confirm the reference leaves the escalation reference's budget intact. A labelled test is never sent to `/cla:diagnose`, and a red rerun returns to the one fix. Verify by reading both references side by side.

manual: change-workflow / A test already failing on the base is labelled, not fixed: the label is a reading judgement made by the model from skill prose; checked in a scratch repo where one test fails on the base and the change touches other files.
manual: change-workflow / A labelled failure ships only by a person's choice: the ask and the halt are model behaviour from skill prose; checked by one attended run (accept, then decline) and one `/cla:multi-lite` run in a scratch repo.
manual: change-workflow / One reported rerun for a failure with no code error: model behaviour from skill prose; checked in a scratch repo with a test that fails on a refused local connection, and one that fails on an assertion.

## 3. `lite-pr/SKILL.md`

- [ ] 3.1 Test step 3: add the Q1 label sentence and one pointer to the reference from 2.1, read when a test fails. Nothing else from groups 2 or 3 goes in SKILL.md.
- [ ] 3.2 Plan: add the one duplicate-work search. It runs `gh pr list --state all --search "<key words>"` plus the base branch's last 50 commits from the local ref, with no fetch. It skips when there is no GitHub remote or the search fails, says so in the `Checks:` line, and is read-only on every match.
- [ ] 3.3 Ship: add the `Checks:` line next to the `Risk:` line. Keep `Risk: <level> — <reason>; reviewers: <list>.` verbatim and on one line, so `test_review_sizing_single_source.py` still passes.
- [ ] 3.4 Per open question 1, amend the description's "Stops only on an unresolved test failure", Autonomy's only-stop sentence and Plan's no-pause sentence to name the attended duplicate wait and the labelled-failure ask. Grep shows no stale copy.
- [ ] 3.5 Run `python3 .claude/plugins/cla/skills/_shared/scripts/check_no_project_tokens.py` and confirm it exits 0.

manual: change-workflow / A search for duplicate work before building: an end-to-end run needs a real GitHub remote and a model; checked by one attended run and one `/cla:multi-lite` run against a scratch remote holding a matching merged pull request, and one run with no remote.
manual: change-workflow / Matched work is left untouched: checked in the same scratch runs by comparing the matched pull request's comments, labels, state and head before and after.
manual: change-workflow / The pull request says what was checked: the line is written by the model; checked by reading the bodies of the scratch-run pull requests, docs-only and with notes.

## 4. Ledger, changelog, measurement, gate

- [ ] 4.1 Add a `docs/rule-ledger.md` line for each new shipped `never`, `always` or `must`. Prefer guidance wording. Use `keep` only for the unattended halt (`honesty`) and the read-only match (`user's files`). Verify that `test_rule_ledger.py` passes.
- [ ] 4.2 Add a `CHANGELOG.md` `[Unreleased]` entry for the patch. Edit no version and not the "Current release" line.
- [ ] 4.3 After the edits, re-run `measure_load.py --skill lite-pr` and record the profile before and after, with the difference, as a `measured:` note. Flag it to the owner if the result is well above the decision's estimate of about 145 words. measured:
- [ ] 4.4 Run `pytest plugin-tests -q -n 4 --dist loadfile` and `openspec validate --specs --strict` once each, on the final commit. Both pass.
- [ ] 4.5 docs and spec map: grep `README.md`, `DEVELOPER-GUIDE.md`, root `CLAUDE.md` and the plugin `README.md` phase table for lite-pr's stop and Test wording, and update each hit; `openspec/spec-map.md` none affected: lite-pr's workflow step and spec links are unchanged.
