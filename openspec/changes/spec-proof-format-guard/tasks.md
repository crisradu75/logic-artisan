# Tasks

## 1. The guard

- [ ] 1.1 Add the format guard to `check_spec_proof.py` as its own function, reading the three limits from `rules.specs`; test the over-limit, different-limit and missing-limit cases. Carry the comment `requirement: spec-proof / A checker reports specs over the repo's format limits`. Done when this repo's own run reports no format problem.
- [ ] 1.2 Apply the round-2 review findings and add mutants for every changed checker line; run the batch once. Done when every mutant is killed.
- [ ] 1.3 Run `pytest plugin-tests -q -n auto --dist loadfile` and `openspec validate --specs --strict` once each.
