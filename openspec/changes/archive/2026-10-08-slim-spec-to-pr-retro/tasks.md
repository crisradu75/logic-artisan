## 1. The retro

- [x] 1.1 Rewrite `spec_to_pr_aggregate.py`: fleet by default with the local fallback, the kept metrics, the reversal check, `--nudge`; `_runs_dir` and `_fleet_roots` stay code-identical to their `lib/` copies.
- [x] 1.2 Rewrite `SKILL.md` to about 300 words; delete `_shared/references/retro-skeleton.md` and fix every reference.
- [x] 1.3 Check 2, what was dropped: emitted `phase_outcomes`, `round_counts`, Review size-gate / verdict / verified-claims / pair-mismatch / agent metrics, Revise dispatch counts, `version_bump_misses`, `deferred_to_todo_total`, `report_chars`, `retired_agent_keys`, every `*_unknown*`, `*_legacy_*`, `*_malformed_*` and `shape_drift_*` bucket, `log_path`/`log_paths`, and the `--fleet` flag (now the default). From the skill: the dead `escalate_up_fired` heuristic, the Review-phase and schema-integrity heuristics, the dispatch-rate rules, the version-bump rule, the worked example. From the skeleton: the generic preamble and "Sources of truth" list; its window/patterns/edits report, 2–4 pattern rule, anecdote rule, metric-per-proposal rule, apply gate, writability check, script/openspec exclusion and "when not to use" survive in `SKILL.md`.
- [x] 1.4 `test_spec_to_pr_aggregate.py` covers every emitted field, the fleet default and fallback, skipped lines, the reversal check and `--nudge` (`requirement: run-ledgers / The spec-to-pr retro summary`, `requirement: run-ledgers / Handoff suggests a retro`); `test_run_record_values_agree.py` keeps the read phase names and reason statuses inside the writer's.

## 2. Handoff

- [x] 2.1 `handoff.md` step 5 and the `SKILL.md` Handoff stub print `--nudge` after appending the record.
- [x] 2.2 `run-log-schema.md`: `findings_by_round` has a reader; the exception paragraph is gone.

## 3. Spec and gate

- [x] 3.1 `run-ledgers`: "The spec-to-pr retro report" removed; "The spec-to-pr retro summary" and "Handoff suggests a retro" added.
- [x] 3.2 Mutation batches over every touched batch, all killed; the full suite parallel and serial with matching counts.
