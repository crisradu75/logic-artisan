# Tasks

Settle the proposal's `## Open questions` with the owner before group 1. Tasks 1.3 and 2.1 follow the recommended answers unless the owner picks otherwise.

**Every shipped edit (files under `.claude/plugins/cla/`) cites no issue or pull request number of this repo.** State the lesson in words. Check (e) of `check_no_project_tokens.py` fails on a `#NNN`.

## 1. Review sizing (`review-change/references/checklist.md`, Step 3 and the report)

- [ ] 1.1 Step 3's rule: a subtask count over 20 grades Large only when the proposal carries `Budget: protected`, read as the budget checker reads it (that exact line, outside a code fence). The file, capability and claim thresholds and both overrides stay unchanged.
- [ ] 1.2 The Small and Large announcements and the report's Mode line say whether the marker was read. Verify by reading Step 3 and Step 5 against the three change-workflow scenarios.
- [ ] 1.3 Size check: a budget-checker problem line naming this change's `Budget:` value grades the change as unmarked and is an Important finding.
- [ ] 1.4 `multi-pr/references/discover-and-gate.md`, the prediction step: its parenthetical stops naming the subtask count as a sizing signal on its own. A grep for "subtask count" in multi-pr finds no stale copy.
- [ ] 1.5 Confirm `multi-spec/references/review-gate.md` Step 3 and `multi-spec/SKILL.md` Phase 4 reuse the checklist's gate and restate no subtask threshold. Edit neither unless one does.

manual: change-workflow / Task count alone does not buy the full review: the grade is a model's reading of skill prose; checked by one `/cla:review-change` run on a scratch change with four files and 30 tasks, once without the marker, once with it and once with `Budget: protcted`.

## 2. Author self-check (`multi-spec/references/authoring-brief.md`)

- [ ] 2.1 Before `done`, the author reads `check_spec_proof.py`'s budget lines for its change and runs `wc -w` on proposal.md and design.md. Count proposal.md without its open-questions and risks sections. A count above the config's figure is over and gets cut.
- [ ] 2.2 The cut never removes a requirement guarding a protected area or an open question. The `done` line names what is still over, and `done` stays valid. Fold in the existing protected-area sentence rather than repeating it.
- [ ] 2.3 Post-check: record the author's still-over list in the PR body and final report beside the budget result. An exit 2 is "budget not checked", never "fits", and nothing blocks.
- [ ] 2.4 Run `pytest plugin-tests/tests/consistency -n 4 --dist loadfile` once; the caps, turn-liveness and proof-format tests that read the brief and checklist pass.

manual: change-chains / An author checks its change's size before reporting it done: model behaviour from skill prose; checked by one `/cla:multi-spec` run in a scratch repo whose decision yields a proposal over 400 words.
manual: change-chains / What still does not fit is reported and the batch goes on: checked in a scratch batch whose first change holds more protected requirements than the budget allows; the requirements stay, the pull request names the overrun, the second change is authored.

## 3. Ledger, changelog, gate, docs

- [ ] 3.1 Run `python3 .claude/plugins/cla/skills/_shared/scripts/check_no_project_tokens.py` and confirm it exits 0.
- [ ] 3.2 Add a `docs/rule-ledger.md` line for each new shipped `never`, `always` or `must`. Prefer guidance wording. Use `keep` only for the protected-requirement cut and "never fits" (`honesty`). `test_rule_ledger.py` passes.
- [ ] 3.3 Append a `CHANGELOG.md` `[Unreleased]` bullet for this patch below any sibling's bullet, leaving theirs unchanged. Edit no version and not the "Current release" line.
- [ ] 3.4 Run `pytest plugin-tests -q -n 4 --dist loadfile` and `openspec validate --specs --strict` once each, on the final commit. Both pass.
- [ ] 3.5 docs and spec map: grep `README.md`, `DEVELOPER-GUIDE.md` (review-change and multi-spec sections), root `CLAUDE.md` and the plugin `README.md` phase table for subtask-based sizing and multi-spec's budget check, and update each hit; `openspec/spec-map.md` none affected: no workflow step or spec link changes.
