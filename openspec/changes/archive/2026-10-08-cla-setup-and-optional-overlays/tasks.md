## 1. The skill

- [x] 1.1 `skills/cla-setup/SKILL.md`: Part 1 from `cla-init` (items 1–7, overlay stubs dropped), Part 2 from `sync-context` (facts rule, overlay migration in place of pointer lines, terminology format, checker run); `disable-model-invocation: true`.
- [x] 1.2 `check_fact_paths.py` moved to `skills/cla-setup/scripts/`; `skills/cla-init/` and `skills/sync-context/` deleted.
- [x] 1.3 Run-notes ignore check runs with `-c core.excludesFile=/dev/null`.

## 2. Overlays optional

- [x] 2.1 Remove every "fall back to the overlay" clause; facts read from `cla.io/project-facts.md` only.
- [x] 2.2 review-change: "Injection is mandatory" and per-placeholder overlay sources replaced by one filling rule; 0f–0i and 1–9 read from the overlay only when present. project-review: named overlay sections ("What the repo is", "Per-dimension…", "Review criteria — repo specifics") removed.
- [x] 2.3 This repo: delete the content-free overlays; move the codify-learnings overlay's commands into a new `cla.io/project-facts.md`.

## 3. Callers

- [x] 3.1 Every `/cla:cla-init`, `/cla:sync-context` and `skills/sync-context/` reference across the repo (skills, README, CLAUDE.md, DEVELOPER-GUIDE, fleet list, OpenSpec config comment, `lib/log_run.py`).

## 4. Tests

- [x] 4.1 `test_cla_setup_*` (renamed from `test_cla_init_*`), `test_run_notes_stay_local.py`, `test_ledger_names_agree.py`, `test_scenario_proof_format.py` read `cla-setup/SKILL.md` (`requirement: repo-context / Setting up a repo with cla-setup`, `requirement: repo-context / OpenSpec authoring rules on setup`, `requirement: repo-context / Retired ledgers on setup`).
- [x] 4.2 A run-notes test with a global excludes file (`core.excludesFile` and the XDG default) that already ignores the notes: the repo line is still written.
- [x] 4.3 `test_overlays_are_reachable.py`: no overlay-count floor; every overlay present parses and is scanned (`requirement: repo-context / Optional per-skill overlays`).
- [x] 4.4 A guard that no shipped skill tells a reader to fall back to an overlay, and no overlay is called mandatory.
- [x] 4.5 Mutation batches over every touched batch: all killed.

manual: Repo facts in one file: Part 2 is a read-and-reason pass over the repo's manifests with no script to test.
