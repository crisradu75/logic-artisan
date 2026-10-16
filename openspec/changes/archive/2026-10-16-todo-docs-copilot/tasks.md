# Tasks

## 1. Economy rules and the bullet test

- [x] 1.1 In `orchestration-economy.md`, rule 8 says the debris diff leaves out lines under `scratchpad/` (git lists ignored files singly and an empty folder not at all, so creating it first would not keep the check quiet) and rule 12 names `gh pr checks` for the green case.
- [x] 1.2 `_flat` in `test_mutation_batch_is_opt_in.py` tags no bullet marker inside a fenced block or on a thematic break (`* * *`, `- - -`). Test both, and that a bullet after the closing fence is still tagged.

## 2. Copilot install requirement

- [x] 2.1 Remove the untested claim from the description in the root `plugin.json`; test that the description does not say "untested". Carry `requirement: plugin-distribution / Disclosing the Copilot CLI install is untested`.
- [x] 2.2 The docs test requires "Copilot CLI only" and the untested phrase in the same heading section as the install command, within 1000 characters of it. Test a document that says it only in another section. Carry `requirement: plugin-distribution / Disclosing the Copilot CLI install is untested`.
- [x] 2.3 Move the `requirement:` markers of the catalog and manifest tests to "Listing for GitHub Copilot CLI". Done when `check_spec_proof.py` run from the worktree reports no problem.

## 3. CLAUDE.md traps

- [x] 3.1 The `check_spec_proof.py` trap names `--root <worktree>`, checked by running it from another directory. The closing-keyword trap reads "without a closing keyword such as `Closes #N` in the PR body".

## 4. Copilot agents

- [x] 4.1 `sync_copilot_agents.py` names an orphaned copy and exits 1 in check mode, and `--write` deletes it and exits 0. Test both with a copy whose Claude agent is gone.
- [x] 4.2 `/release` Step 1 runs a stdlib script that reads GitHub's supported-models table and exits 1 naming each `MODEL_MAP` ID missing from it, and 2 when the table cannot be read. Test with saved table text, no network.

## 5. Close out

- [x] 5.1 Remove each fixed line from `TODO.md`, and the dropped archived-tasks line.
- [x] 5.2 docs and spec map: DEVELOPER-GUIDE.md (script table row and tree, manifest and agent stories) and CLAUDE.md updated; README.md, the plugin README and the spec map none affected: they keep the claim, and the map links specs, not requirements.
