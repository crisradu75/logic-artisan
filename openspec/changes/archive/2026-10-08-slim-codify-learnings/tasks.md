## 1. Delete codify-retro

- [x] 1.1 Remove the skill, `codify_aggregate.py`, its tests and mutants, and its `pythonpath` entry.
- [x] 1.2 Remove every reference: README phase table, CLAUDE.md and DEVELOPER-GUIDE skill lists and script table, `cla-init` ledger list, `fleet.local.md` (two `_fleet_roots` copies), `retro-skeleton.md`, the lib and aggregator docstrings, `spec-to-pr-retro/SKILL.md`.
- [x] 1.3 Consistency guards: drop the codify reader from `test_ledger_dir_agrees.py` and `test_ledger_names_agree.py` and their batches.

## 2. Slim codify-learnings

- [x] 2.1 Rewrite `SKILL.md` as five steps. measured: 1,032 words, reachable 2,122 (from 3,150 and 9,540).
- [x] 2.2 Merge the references into `references/routing.md`; 15 failure prompts from 51; delete the other four.
- [x] 2.3 This repo's overlay keeps only the sections the skill reads; retro-skeleton and the conftests point at the merged reference.

## 3. Record shape

- [x] 3.1 `lib/log_run.py` `SHAPES` and `RUNGS` for the new codify record; the example lives in `SKILL.md` Step 5.
- [x] 3.2 `test_log_run.py`: the new record accepted, each violation refused by name, the old record refused (`requirement: run-ledgers / Run records are checked when written`).
- [x] 3.3 `test_run_record_examples.py` extracts the example from `SKILL.md`; `test_migrate_run_records.py` skips pre-change codify records.

## 4. Spec and gate

- [x] 4.1 `run-ledgers`: "Retro reports" removed; "The spec-to-pr retro report" added, tested by `test_spec_to_pr_aggregate.py` (`requirement: run-ledgers / The spec-to-pr retro report`).
- [x] 4.2 Mutation batches over every touched guard, all killed; the full suite parallel and serial with matching counts.
