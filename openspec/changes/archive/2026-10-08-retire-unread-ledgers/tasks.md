## 1. Retire the unread ledgers

- [x] 1.1 Remove the logging steps from `lite-pr`, `shape-decision` and `feedback`, and the `Bash` grant the last two held only for it; delete `lib/ledger_summary.py`, its tests and mutants, and every reference.
- [x] 1.2 `log_run.py` refuses any ledger name outside `SHAPES` (`test_log_run.py`, `requirement: run-ledgers / Only checked run records are written`); `test_ledger_names_agree.py` pins skills' ledgers and cla-init's seeded ones to `SHAPES`.

## 2. Prune the spec-to-pr record

- [x] 2.1 Drop from `SHAPES`, `run-log-schema.md`, `handoff.md` step 5 and the `SKILL.md` Handoff stub every field the aggregator does not read: `args`, `report_chars`, Review `size_gate` / `verdict` / `verified_claims_count` / `agents`, `version_bumped`, Revise `agents`, `sibling_instance`, `deferred_to_todo`, `cost`, `routing.models` / `implement_delegated` / `escalate_up_fired`; keep `ts`, `change`, `mode`.
- [x] 2.2 Add `flags` and `escalated_to_diagnose`, and count them in `spec_to_pr_aggregate.py` (`test_spec_to_pr_aggregate.py`, `requirement: run-ledgers / Summarising flag use and diagnose escalations`); the example in `run-log-schema.md` passes `test_run_record_examples.py` (`requirement: run-ledgers / The spec-to-pr run record`).
- [x] 2.3 `migrate_run_records.py` drops the Review-gate and Revise-agents mappings the record no longer needs.

## 3. Ledger rows ride the work PR

- [x] 3.1 `multi-lite` Phase 4 and `multi-pr` cleanup commit run notes onto the last open PR, or leave them uncommitted and say so; re-runs untrack them first; multi-lite forgives a notes-only head move (`test_run_records_ride_the_work_pr.py`, `requirement: run-ledgers / Run records ride the work's pull request`).

## 4. Retired ledgers

- [x] 4.1 `cla-init` item 7 lists the retired ledgers present (`test_cla_init_retired_ledgers.py`, `requirement: repo-context / Reporting retired ledgers`).
- [x] 4.2 manual: Reporting retired ledgers: the deletion on an explicit yes is the model's own `rm`, not a script the suite can run.

## 5. Gate

- [x] 5.1 Mutation batches over every touched guard, all killed; the full suite parallel and serial on one tree with matching counts; `openspec validate --specs --strict`.
