## 1. Specs

- [x] 1.1 Write the deltas for guard-hooks, change-chains, small-change-chains, change-workflow, repo-context and plugin-distribution; validate with `openspec validate live-specs-review-fixes --strict`
- [x] 1.2 After archive, give `small-change-chains` a one-sentence Purpose and run `openspec validate --specs --strict` with no warning

## 2. Proof per requirement

Each test below carries a `requirement: <spec> / <heading>` comment line above it.

- [x] 2.1 guard-hooks / Unsafe commands are blocked: `test_block_unsafe_recursive_delete.py`, `test_block_cd_in_bash.py`, `test_block_worktree_path_escape.py` (markers unchanged)
- [x] 2.2 guard-hooks / Destructive git commands ask first: `test_ask_destructive_git.py`, plus a marker on the `ALLOW_DESTRUCTIVE_GIT` override test
- [x] 2.3 guard-hooks / Risky actions warn: `test_warn_wholesale_rewrite.py` (re-pointed) and `test_warn_stacked_pr_merge.py` (the `--delete-branch` trigger)
- [x] 2.4 change-chains / A later change is held to what an earlier one owes it: `test_chain_obligation_carry.py` (re-pointed)
- [x] 2.5 small-change-chains / What a small-change chain merges: `test_multi_lite_policy_names_agree.py` (lost findings count as open; the full gate runs before every merge)
- [x] 2.6 small-change-chains / A resumed small-change chain never merges unchecked commits: `test_multi_lite_policy_names_agree.py` (a moved head is never merged)
- [x] 2.7 repo-context / Seeding a repo's OpenSpec authoring rules: `test_cla_init_rules_match_config.py` (re-pointed)
- [x] 2.8 change-workflow / Specs follow the repo's authoring rules: `test_scenario_proof_format.py`, `test_cla_init_rules_match_config.py` (markers unchanged)
- [x] 2.9 plugin-distribution / Installing a pinned release: `test_marketplace_manifest.py` (marker unchanged)
- [x] 2.10 The policy-name consistency test in `test_multi_lite_policy_names_agree.py` loses its marker: it checks that five files spell the two policy names alike, which proves no requirement

manual: Running a batch of small changes: an end-to-end chain run needs a real repo, `gh` and a model; checked by running `/cla:multi-lite` on a doc with several small fixes.
manual: A failed small change skips its dependents: chain behaviour on a failed change needs a real chain run; checked from a chain's report.
manual: Running a batch of OpenSpec changes in dependency order: an end-to-end chain run; checked by running `/cla:multi-pr`.
manual: What an OpenSpec change chain merges: merging needs a real host and chain run; checked from a chain's report.
manual: A failed OpenSpec change stops the chain: needs a real chain run with a failing change; checked from the halt report.
manual: Options for one change's run: the options are read by the model from the skill text; checked in a run with each option. The flag-parity test in `test_chain_obligation_carry.py` covers only the options multi-pr passes, so it carries no marker for this requirement.

## 3. Follow-through

- [x] 3.1 Reword the dead spec citations in `test_mutation_gate_sites_agree.py`, `test_orchestrators_state_turn_liveness.py` and `_shared/references/skill-authoring.md` to point at the test or skill file that now holds the rule
- [x] 3.2 Add `openspec validate --specs --strict` to CLAUDE.md's "Before opening a PR" row and its "No CI" paragraph, and to the release skill's Step 1 and Step 3 command blocks; add a mutant for it to the release-preconditions batch
