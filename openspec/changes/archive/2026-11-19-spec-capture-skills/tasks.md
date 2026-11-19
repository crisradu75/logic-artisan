# Tasks

## 1. Specs

- [x] 1.1 Add the three new specs and the two reworded requirements. `openspec validate --specs --strict` passes after archive.
- [x] 1.2 Audit the paths in `instruction-files`, `spec-proof`, `cla-setup` and `repo-context`: each kept path is a file a consuming repo writes or reads. Measure every requirement of `change-chains`, `change-workflow` and `run-ledgers`; none is over 500 characters.

## 2. Tests

- [x] 2.1 Test `session-records / A checkpoint is a resumable briefing`, `A checkpoint never holds a secret` and `A checkpoint is checked against the tree before it is followed`: the skill's text carries each.
- [x] 2.2 Test `session-records` feedback requirements: one note per turn, read-only grounding with no editing tool, a suffixed new file, the inbox untouched, and merges only on confirmation.
- [x] 2.3 Test `session-records` decision requirements: the existing shape-decision tests carry the axis marker; the question form and the explicit-yes, never-overwrite write are pinned.
- [x] 2.4 Test the four `project-review` requirements: baseline before dispatch, five concurrent reviewers with the routing table agreeing, the verdict rows equal in the skill and the rubric reference, and no editing tool.
- [x] 2.5 Test the two `model-advice` requirements: the five axes, separate model and effort signals, escalation only on a signal, and a start only on a yes.
- [x] 2.6 Test the reworded `spec-proof` and `repo-context` requirements: their existing tests carry the markers and still pass.

## 3. Docs

- [x] 3.1 docs and spec map: `openspec/spec-map.md` (every new spec linked from a workflow step; the unspecced-skills section removed); `CHANGELOG.md`, `README.md`, `DEVELOPER-GUIDE.md` and `.claude/plugins/cla/README.md` left to the orchestrator's PR; root `CLAUDE.md` none affected: it names no spec.
