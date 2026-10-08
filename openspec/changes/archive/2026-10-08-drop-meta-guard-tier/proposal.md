## Why

Part of the dev-tree test suite only checked the suite's own bookkeeping: that every guard had a
mutation batch, that guards were not vacuous, that every shipped file was listed against a scanner,
that duplicated helpers stayed byte-identical, that commit claims named a command, and that counts
restated in the docs were current. Keeping them green cost more upkeep than they caught, and they
pin wording that later simplifications rewrite.

## What Changes

- Delete `test_guards_have_mutant_batches.py`, `test_guards_are_not_vacuous.py`,
  `test_shipped_files_are_scanned.py`, `test_measurement_names_its_command.py`,
  `check_script_drift.py` and its test, and their mutation batches. Mutation batches become
  optional.
- Replace the drift checker with one behavioural test: the ledger writer and the spec-to-pr reader,
  run as programs, resolve the same directory with and without `CLAUDE_RETRO_DIR`.
- Move the `make_dir_alias` test helper, copied into four test modules, into one shared fixture.
- Shrink `test_doc_facts.py` to the release-version line and the skill invocation table.
- Keep the token and path scanners as they are. The plugin's own `README.md` names this repo and
  the plugin path on purpose, so scanning every shipped file would fail on it. The spec no longer
  requires unscanned files to be listed.
- Update comments, docs and batches that named the deleted pieces.
