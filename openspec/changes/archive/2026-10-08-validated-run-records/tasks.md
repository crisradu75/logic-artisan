## 1. Writer

- [x] 1.1 `lib/log_run.py`: `SHAPES` for the two ledgers, checked after the JSON parse; one-line refusal naming the field; nothing written.

## 2. Producers

- [x] 2.1 spec-to-pr Handoff step 5 and SKILL.md stub: build from the reference, retry once on a refusal, then continue.
- [x] 2.2 `run-log-schema.md`: field meanings and one conforming example; the shape statement points at `log_run.py`.
- [x] 2.3 codify-learnings Step 7 and its ledger schema: required keys and value shapes stated; retry once.
- [x] 2.4 multi-pr checked: no place writes or instructs a run record.

## 3. Migration

- [x] 3.1 `plugin-tests/scripts/migrate_run_records.py`: every off-shape form found in the fleet, idempotent, reports what it changed and what it cannot map.
- [x] 3.2 Migrate this repo's `cla.io/retro/spec-to-pr-runs.jsonl`; every record passes the check. measured: 6 of 11 migrated, 0 unmappable.

## 4. Tests

- [x] 4.1 `test_log_run.py`: conforming records accepted; each shape violation refused naming its field, `phases` as an object first; other ledgers unchanged (`requirement: run-ledgers / Run records are checked when written`).
- [x] 4.2 `test_migrate_run_records.py`: each fleet form maps and passes, other fields kept, a second pass changes nothing; this repo's ledgers pass.
- [x] 4.3 Mutation batches for both: every mutant killed. measured: 22 of 22 (`log_run`) and 15 of 15 (migration) killed; 1894 passed, 12 skipped both parallel and serial.

manual: Run records are checked when written: the retry-once-then-continue step is skill prose a model follows; it is checked by reading the two producer recipes.
