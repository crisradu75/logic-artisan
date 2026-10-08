## 1. Delete the meta guard tier

- [x] 1.1 Delete the five meta guards, `check_script_drift.py`, and their mutation batches.
- [x] 1.2 Shrink `test_doc_facts.py` and its batch to the release line and the invocation table.
- [x] 1.3 Keep the scanners; remove the exemption-listing rule from the conformance guard requirement.

## 2. Replace what is still needed

- [x] 2.1 Add `tests/consistency/test_ledger_dir_agrees.py` and a batch that breaks each side's resolver.
- [x] 2.2 Move `make_dir_alias` into `plugin-tests/tests/conftest.py` as a fixture.

## 3. References and verification

- [x] 3.1 Update the pyproject, `mutate.py`, batches, tests, shipped comments, the release skill, CLAUDE.md and DEVELOPER-GUIDE.md where they named the deleted pieces.
- [x] 3.2 Parallel and serial `pytest plugin-tests` agree; `node --test` passes; `openspec validate --specs` passes.
