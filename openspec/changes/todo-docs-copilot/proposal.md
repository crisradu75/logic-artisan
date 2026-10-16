# Proposal

## Why

Leftover review suggestions sit in root `TODO.md`. The owner approved clearing the ones for the
orchestration economy rules, the Copilot manifest, the session traps in CLAUDE.md and the Copilot
agents. Each was re-checked against main first. One of them edits the `plugin-distribution` spec,
which is why this is a change and not a lite PR.

## What Changes

- Economy rules 8 and 12 (`orchestration-economy.md`): rule 8 says to leave lines under
  `scratchpad/` out of the debris diff (the TODO asked to create the folder first; git lists ignored
  files singly and an empty folder not at all, so that would not keep the check quiet); rule 12 adds
  `gh pr checks` for the green case. `_flat` in `test_mutation_batch_is_opt_in.py`
  skips fenced lines and thematic breaks, with a test.
- The shipped root `plugin.json` description stops saying the Copilot install is untested (owner
  decision): a release tag is never moved, so a claim in it outlives the first live test. README,
  DEVELOPER-GUIDE and the spec keep the claim.
- The spec requirement "Installing from GitHub Copilot CLI" is split into the install line and the
  disclosure duty. The disclosure must sit beside the install command, and the docs test checks
  that, within one heading section.
- Two CLAUDE.md traps: `check_spec_proof.py` names `--root <worktree>`; the closing-keyword trap
  says "without a closing keyword such as `Closes #N` in the PR body".
- `sync_copilot_agents.py` reports an orphaned Copilot copy in check mode (exit 1) and deletes it
  with `--write`.
- `/release` gains a step that fetches GitHub's supported-models table for Copilot CLI and refuses
  when a `MODEL_MAP` ID is missing (owner decision). It is a stdlib script like the release skill's
  other check; its tests build a page with the table's layout and make no network call.

## Dropped

- Tasks 2.1 to 4.1 of the archived change `copilot-manifest-and-release-drift` run long: archived
  changes are not edited.

## Capabilities

### Modified Capabilities

- `plugin-distribution`: "Installing from GitHub Copilot CLI" is removed and replaced by two
  requirements, "Listing for GitHub Copilot CLI" and "Disclosing the Copilot CLI install is
  untested". The spec goes from 7 to 8 requirements, the cap.

## Impact

`orchestration-economy.md` (shipped), root `plugin.json` (shipped), CLAUDE.md, the release skill and
its new script, `sync_copilot_agents.py` and tests under `plugin-tests/`, `TODO.md`. The Claude
install is unchanged: `claude plugin validate` runs before and after.
