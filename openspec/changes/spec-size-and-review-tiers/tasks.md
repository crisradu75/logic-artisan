# Tasks

Settle the proposal's `## Open questions` with the owner before group 1. Tasks 1.3 and 2.1 follow the recommended answers unless the owner picks otherwise.

**Land this change second of three** (the lite-pr red-gate change, then this one, then the chain-gate change): the order matters for the shared `CHANGELOG.md`, `docs/rule-ledger.md` and docs sweep.

**Every shipped edit (files under `.claude/plugins/cla/`) cites no issue or pull request number of this repo.** State the lesson in words. Check (e) of `check_no_project_tokens.py` catches only "issue/PR/pull request #N" and the repo's GitHub URLs, not a bare `#12`; task 3.2 greps for that. This file does not ship, so the number in task 3.7 is allowed.

## 1. Review sizing (`review-change/references/checklist.md`, Step 3 and the report)

- [ ] 1.1 Step 3: a subtask count over 20 grades Large only when the proposal's `Budget:` line has the value `protected` (task 1.3). The file, capability and claim thresholds and both overrides stay unchanged.
- [ ] 1.2 The Small and Large announcements and the report's Mode line say whether the marker was read. Verify by reading Step 3 and Step 5 against the three change-workflow scenarios.
- [ ] 1.3 Grade on the value of the `Budget:` line (outside a code fence), not on checker output: exactly `protected` keeps the full review; absent or any other value is unmarked, and a value other than `protected` is an Important finding.
- [ ] 1.4 `multi-pr/references/discover-and-gate.md`, the prediction step: its parenthetical stops naming the subtask count as a sizing signal on its own. A grep for "subtask count" in multi-pr finds no stale copy.
- [ ] 1.5 Confirm `multi-spec/references/review-gate.md` Step 3 and `multi-spec/SKILL.md` Phase 4 reuse the checklist's gate and restate no subtask threshold. Edit neither unless one does.
- [ ] 1.6 Run `pytest plugin-tests/tests/consistency -n 4 --dist loadfile` once; `test_review_sizing_single_source.py` and `test_chain_obligation_carry.py` read checklist text. The bar is no failure beyond main's baseline here: the mutation-batch preflight CRLF tests and `test_pre_push_is_installed`.

manual: change-workflow / Task count alone does not buy the full review: the grade is a model's reading of skill prose; checked by one `/cla:review-change` run on a scratch change with four files and 30 tasks spread across them: without the marker, with it (in a config with and without a protected budget sentence) and with `Budget: protcted`.

## 2. Author self-check (`multi-spec/references/authoring-brief.md`)

- [ ] 2.1 Before `done`, the author reads `check_spec_proof.py`'s budget lines for its change and runs `wc -w` on design.md and on proposal.md without its open-questions and risks sections. A count above the config's figure is cut.
- [ ] 2.2 The cut never removes an open question or a requirement guarding a protected area; fold in the existing protected-area sentence rather than repeating it. The `done` line names what is still over, and `done` stays valid.
- [ ] 2.3 Post-check: record the author's still-over list in the PR body and final report beside the budget result. An exit 2 is "budget not checked", never "fits", and nothing blocks.
- [ ] 2.4 Re-run the consistency test files that read the brief (caps, turn-liveness, proof-format) once, against the baseline in 1.6.

manual: change-chains / An author checks its change's size before reporting it done: model behaviour from skill prose; checked by one `/cla:multi-spec` run in a scratch repo whose decision yields a proposal over 400 words.
manual: change-chains / An overrun that could not be cut is reported and the batch goes on: checked in a scratch batch whose first change holds more protected requirements than the budget allows; the requirements stay, the pull request names the overrun, the second change is authored.

## 3. Ledger, changelog, docs, gate, issue

- [ ] 3.1 Run `python3 .claude/plugins/cla/skills/_shared/scripts/check_no_project_tokens.py` and confirm it exits 0.
- [ ] 3.2 Run `git diff <base>...HEAD -- .claude/plugins/cla | grep -nE '#[0-9]'` over the changed shipped files and expect no hit.
- [ ] 3.3 Add a `docs/rule-ledger.md` line for each new shipped `never`, `always` or `must`, in guidance wording; use `keep` only for the protected-requirement cut and "never fits" (`honesty`). `test_rule_ledger.py` passes.
- [ ] 3.4 Append this patch's `CHANGELOG.md` `[Unreleased]` bullet below the lite-pr change's bullet and above the chain-gate change's, leaving theirs unchanged. Edit no version and not the "Current release" line.
- [ ] 3.5 The implementation PR body says `Closes #507` (the issue about the batch skills having no proportionality gate).
- [ ] 3.6 Post one comment on #507 mapping its parts: 1 (audience question) declined, covered by the Stakes section; 2 (over-size specs) is the author self-check, batch block declined; 3 (review loop bound) handled, round two only after a protected-area fix; 4 (mutation check) limited to blocking-finding fixes; review-depth comment is the task-count sizing.
- [ ] 3.7 docs and spec map: update each hit for subtask-based sizing or multi-spec's budget check in `README.md`, `DEVELOPER-GUIDE.md`, root `CLAUDE.md` and the plugin `README.md` phase table; none affected for `openspec/spec-map.md`: no step or spec link changes. Then run `pytest plugin-tests -q -n 4 --dist loadfile` and `openspec validate --specs --strict` once each, on the final commit, so no doc edit lands after the final run. Both pass, apart from the baseline failures named in 1.6.
