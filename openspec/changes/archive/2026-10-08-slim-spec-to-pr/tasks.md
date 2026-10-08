## 1. Slim

- [x] 1.1 Rewrite `spec-to-pr/SKILL.md` to stubs that read their references first, keeping every pinned region and the resolver short form. measured: 4171 words, from 9125.
- [x] 1.2 Move rationale out of `revise.md`, `ship.md`, `handoff.md`, `review-sweeps.md`, `precheck.md` and `run-log-schema.md` into `design-tradeoffs.md`; state `Measured-by:` once, in `ship.md` §2b. measured: revise 3859, ship 1434, handoff 1097, review-sweeps 645, precheck 363, run-log-schema 550.
- [x] 1.3 Merge `archive-preflight.md` into `archive.md` and drop it from `measure_load.py`'s profile.
- [x] 1.4 Fix the stale pointers: "Autonomy modes", "Incident history", removed SKILL.md section names cited by lite-pr, multi-pr, implement-delegate, concurrent-runs, bash-discipline and runtime-rules, `npm run` in the diagram and delegate brief, the diagram's `--interactive` row.
- [x] 1.5 Diff each rewritten file against its old text and list every dropped rule (proposal).

## 2. Gate

- [x] 2.1 Re-anchor the moved pinned text: two `test_chain_obligation_carry` mutants, and the recorded counts and floors in `test_no_hardcoded_plugin_paths.py` and its batch. measured: typical-run profile 18732 words over 10 files, from 30738 over 11.
- [x] 2.2 Mutation batches over every touched guard or target, all killed; the full suite parallel and serial on one tree with matching counts; the node suite; `openspec validate --specs --strict`.
