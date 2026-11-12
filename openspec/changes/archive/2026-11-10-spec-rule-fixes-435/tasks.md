# Tasks

## 1. Specs

- [x] 1.1 Add the untested-claim scenario to the plugin-distribution Listing requirement and split the review-agents requirement in the delta specs.
- [x] 1.2 Update the `# requirement:` references in `test_reviewer_dispatch.py` to the new names. `test_marketplace_manifest.py` is unchanged: its test already cites "Listing for GitHub Copilot CLI".

## 2. Verify

- [x] 2.1 Run the consistency tests, the full suite once, `openspec validate --specs --strict` and `check_spec_proof.py`.
- [x] 2.2 docs and spec map: none affected; `openspec/spec-map.md` still describes review-agents accurately (diff file and no-git brief) and plugin-distribution is unchanged in scope.
