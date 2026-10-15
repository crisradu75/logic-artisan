# Docs currency and the spec map — 2026-10-15

**Topic:** how OpenSpec changes keep repo documents outside `openspec/` current, and how a spec map
bridges high-level capabilities and workflows to the granular specs. Covers GitHub issues "Every
OpenSpec change gets a task to update the repo docs outside openspec" (#387) and "Spec map: bridge
capabilities and workflows to the granular OpenSpec specs" (#376).

**Grounding:** `spec-to-pr/references/review-sweeps.md` runs doc-staleness sweeps only when a change
retires something, and reads a "Doc-sweep paths" list from `cla.io/project-facts.md`. This repo's
facts file has no such heading. `openspec/config.yaml` `rules.tasks` has no docs task. The cla-setup
rules copy lives only in `cla-setup/scripts/seed_openspec_rules.py`.

## Decisions

1. **Enforcement:** a task at planning, verified at Review. The task names the docs. spec-to-pr's
   post-check confirms it exists and is ticked. Review compares the named docs with the diff, and a
   stale doc is an Important finding.
2. **Which docs:** a "Doc-sweep paths" list in `cla.io/project-facts.md`, with judgement as the
   fallback when it is absent. It fills the heading the existing sweep already reads.
3. **The map's task:** one task per change, with the map as one entry in the doc list. Wording:
   "docs and spec map: <files updated>, or `none affected: <reason>`".
4. **Map location:** declared in `project-facts.md` under "Spec map", globs allowed, any layout
   (e.g. `docs/products/*/overview.md`, `openspec/spec-map.md`, `docs/spec-map.md`). No
   declaration means no map, and nothing fires. `cla-setup` offers a default and never imposes it.
5. **Map content:** three layers — capabilities, then the workflows that deliver them, then the
   specs each workflow step links. Links only: no configurable values, no restated rules.
6. **Guard location:** a new check inside `check_spec_proof.py`, not a new script.
7. **Guard strictness:** `PROBLEM` (exit 1) for an unlinked live spec or a dangling map link, once
   a map is declared; nothing when none is declared.
8. **Shipping:** two OpenSpec changes in order, each through `/cla:spec-to-pr`.
   - **A, "docs task":** this repo's doc list; the tasks rule in `config.yaml` and the seed
     script; the spec-to-pr post-check; Review verification; the lite-pr duty (decision 9).
   - **B, "spec map":** the "Spec map" fact with globs; the three-layer scaffold `cla-setup`
     offers; the `check_spec_proof.py` problem; this repo's own map.
9. **lite-pr:** carries the same duty as one plan line and one Review check, reading the same doc
   list. Part of change A.

## Decision Summary

| # | Question | Choice | Rationale |
|---|---|---|---|
| 1 | Where enforced | Task at planning, verified at Review | Pairs intent with evidence |
| 2 | Which docs | Doc list in project-facts, judgement fallback | One list for task and Review; fills the sweep's missing input |
| 3 | Map's task | One shared task; the map is a doc-list entry | No per-change boilerplate |
| 4 | Map location | Declared in project-facts, globs, any layout | A repo fact, nothing hard-coded |
| 5 | Map content | Capabilities, workflows, specs | The bridge the owner asked for |
| 6 | Guard location | Inside `check_spec_proof.py` | Already reads facts and specs; already wired |
| 7 | Guard strictness | PROBLEM once declared | Declaring is opting in |
| 8 | Shipping | Two spec-to-pr changes, A then B | Reviewable alone; B builds on A |
| 9 | lite-pr | Same duty, plan line plus Review check | Drift ignores the path taken |

## Why it matters and what's next

Docs and the spec map drift because nothing names them when a change is planned, and nothing checks
them at Review. Next: rewrite both issue bodies to match these decisions, then run change A through
`/cla:spec-to-pr`. Change B follows after A merges.
