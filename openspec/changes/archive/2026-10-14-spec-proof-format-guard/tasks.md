# Tasks

## 1. The guard

- [x] 1.1 Add the format guard to `check_spec_proof.py` as its own function, reading the three limits from `rules.specs`; test the over-limit, different-limit and missing-limit cases. Carry the comment `requirement: spec-proof / A checker reports specs over the repo's format limits`. Done when this repo's own run reports no format problem. measured: `check_spec_proof.py` on this repo prints `problems: 0` with limits chars 500, scenarios 3, requirements 8.
- [x] 1.2 Apply the review findings. Each fix was broken once by hand and a test failed. The mutation batch was extended but not run to completion: the owner made mutation testing opt-in and stopped it.
- [x] 1.3 Run `pytest plugin-tests -q -n auto --dist loadfile` and `openspec validate --specs --strict` once each.
