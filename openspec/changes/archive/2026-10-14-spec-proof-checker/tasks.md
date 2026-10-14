# Tasks

## 1. The checker

- [x] 1.1 Add `check_spec_proof.py` in `skills/_shared/scripts/` (stdlib only): read specs and deltas, markers, `manual:`, `waiting:` lines; changed-since-merge-base rule; dangling, repeated-heading and empty-corpus rules; printed counts. Done when 1.2 to 1.5 pass.
- [x] 1.2 Test the unproven and renamed cases. Carry the comment `requirement: spec-proof / A checker reports requirements with no proof`.
- [x] 1.3 Test the dangling, repeated and empty-corpus cases. Carry the comment `requirement: spec-proof / A checker reports proof that points at nothing`.
- [x] 1.4 Test the facts line: absent, `scenario`, malformed, repeated. Carry the comment `requirement: spec-proof / A repo chooses proof per requirement or per scenario`.
- [x] 1.5 Test `(prompt half)` and `waiting:` lines. Carry the comment `requirement: spec-proof / Half-proven and waiting requirements are counted apart`.

## 2. Wiring

- [x] 2.1 `cla-setup` asks for the granularity and writes the facts line; this repo's `project-facts.md` states `requirement`. Done when a test pins the line the checker reads.
- [x] 2.2 `spec-to-pr` Implement's post-check runs the script and carries each problem to Handoff; add the script and its one-line reason to the DEVELOPER-GUIDE §11 table.

## 3. Gate

- [x] 3.1 Add a mutation batch under `plugin-tests/mutants/_shared/`; run it once over the changed checker lines and read each killing test. Done when every mutant is killed. measured: 40 of 40 killed.
- [x] 3.2 Run the checker read-only on this repo's `openspec/` and `plugin-tests/`. Done when its output is recorded in the PR body.
- [x] 3.3 Run `pytest plugin-tests -q -n auto --dist loadfile` and `openspec validate --specs --strict` once each.
