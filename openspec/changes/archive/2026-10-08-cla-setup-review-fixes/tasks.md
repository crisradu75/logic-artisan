## 1. cla-setup

- [x] 1.1 Item 9 sorts overlay lines into fact, rule, incident, duplicate and scaffolding; a rule inside an incident, and a path only one rule uses, stays in the overlay; the old pointer is scaffolding.
- [x] 1.2 Item 7 accepts only a `.gitignore` match; multi-lite and multi-pr say their check accepts any source.
- [x] 1.3 Terminology format moved to `_shared/references/terminology-format.md`; duplicated prose cut.

## 2. Callers

- [x] 2.1 The shared transitional line in every skill that reads a fact from the facts file.
- [x] 2.2 routing.md's "or the overlay" removed; dispatch.md and lite-pr name the lockstep set by meaning.
- [x] 2.3 This repo's three overlays migrated: rules kept, stories appended to the lessons log, two overlays deleted.

## 3. Tests

- [x] 3.1 `test_run_notes_stay_local.py`: a pattern only in `.git/info/exclude` gets the line written; a nested `.gitignore` counts (`requirement: repo-context / Setting up a repo's cla.io tree`).
- [x] 3.2 `test_cla_setup_overlay_migration.py` (`requirement: repo-context / Repo facts and overlay rules on setup`).
- [x] 3.3 `test_overlays_are_reachable.py`: the transitional line in every reading skill, and the widened fallback pattern (`requirement: repo-context / Optional per-skill overlays`).
- [x] 3.4 Mutation batches over every touched batch: all killed.
