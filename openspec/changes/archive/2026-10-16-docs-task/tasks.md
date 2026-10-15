# Tasks

## 1. The doc list and the task rule

- [x] 1.1 Add the "Doc-sweep paths" list to this repo's `cla.io/project-facts.md`. Done when `check_fact_paths.py` run on this repo reports no stale path.
- [x] 1.2 Add the docs task rule to `rules.tasks` in `openspec/config.yaml` and to `RULES` in the seed script, word for word. Done when `test_cla_setup_rules_match_config.py` passes.

## 2. spec-to-pr

- [x] 2.1 The review-before-implementation checklist, and Agent 2 in `dispatch.md`, flag a missing, empty or unreasoned docs task as Important, only when the repo's `rules.tasks` carries the rule (token `docs and spec map:`).
- [x] 2.2 The Implement post-check, gated the same way, confirms the docs task exists, is ticked and names only files changed on the branch. A miss is a Handoff issue; the doc is edited before Test.
- [x] 2.3 Revise round 1: the orchestrator searches every doc on the doc list that the diff leaves untouched for the names the diff alters. A stale doc is an Important finding; `--pr-rounds 0` skips the check.

## 3. lite-pr and cla-setup

- [x] 3.1 `/cla:lite-pr` gains one Plan line naming the docs it will update, from the same doc list, and one Review check that compares them with the diff.
- [x] 3.2 Correct the `cla-setup` description of the doc list: it serves every change, and the spec tree is not on it. Done when the old wording is gone.

## 4. Proof and gates

- [x] 4.1 One consistency test pins each site above and this repo's own list to the same heading and task token. Carry the comment `requirement: docs-currency / A change keeps the repo's docs current`. Done when removing the token from one site fails it.
- [x] 4.2 Run `pytest plugin-tests -q -n auto --dist loadfile` and `openspec validate --specs --strict` once each. measured before archive: 2429 passed, 8 skipped, 1 failed (the marker test needs the spec live, which archive makes so); validate 10 passed, 0 failed.
- [x] 4.3 docs and spec map: `cla.io/project-facts.md`, `cla-setup/SKILL.md`, `workflow-diagram.md`; none affected: root `CLAUDE.md`, `README.md`, `DEVELOPER-GUIDE.md`, plugin readme (none describes the post-check, tasks rules or lite-pr Plan).

manual: A change keeps the repo's docs current: the stale-doc finding is a model reading prose; the test pins only the sites that instruct it (prompt half)
