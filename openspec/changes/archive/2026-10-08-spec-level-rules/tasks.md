## 1. Rules

- [x] 1.1 Rewrite `rules.specs` and `rules.tasks` in `openspec/config.yaml` and the cla-init block to match.
- [x] 1.2 Replace the restated rules in multi-spec's authoring brief, spec-to-pr and review-change with a pointer to the config rules.

## 2. Review and edit sites

- [x] 2.1 review-change checklist and dispatch: spec level finding, MODIFIED requirements included, proof per requirement, fixes routed away from spec text; drop "pinning a wording detail" and the delta-spec ask.
- [x] 2.2 spec-to-pr Review and multi-spec's review gate route fixes the same way; spec-to-pr Implement and `test-quality.md` name the requirement marker.
- [x] 2.3 project-review grades spec level; lite-pr edits a live spec only for an outcome or interface.
- [x] 2.4 cla-init compares an existing config's rules, lists missing or outdated ones, and updates only on the user's yes.

## 3. Tests

- [x] 3.1 `test_scenario_proof_format.py` checks requirement markers and the retired forms; the existing markers name their requirements; batch updated.
- [x] 3.2 `test_cla_init_rules_match_config.py` runs the seed script against scratch repos (`requirement: plugin-architecture / cla-init seeds OpenSpec authoring rules without clobbering`) and guards against a third copy of the spec rules; batch updated.
- [x] 3.3 Both batches: every mutant killed. Parallel and serial `pytest plugin-tests` agree; `node --test` passes; `openspec validate --specs` passes. measured: 13 of 13 and 18 of 18 killed; 1781 passed, 12 skipped both ways; 70 node tests pass; 6 of 6 specs valid.
