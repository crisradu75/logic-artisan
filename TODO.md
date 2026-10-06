## Deferred from PR #294 (lighter-openspec-packages) — 2026-10-07

**Rejected remedies, still open** (findings whose proposed fix a delegate rejected with reasons; the defect is REAL and UNFIXED):
- (none)

**Deferred-Known-Issues** (Important PR-review findings the team consciously deferred):
- [Important] spec-to-pr's Review skip keys on commit subjects, not on multi-spec's per-change verdict. A change multi-spec graded RETHINK, or whose fixes were never re-reviewed, can skip the second review. A change graded READY in a batch merged with a merge commit gets reviewed twice. — rationale: the fix needs a new per-change verdict record from multi-spec's gate (for example, in the plan JSON). That is a design decision for the user, not a review-round edit. What the skip gives up is recorded in the archived design.md (`openspec/changes/archive/2026-10-07-lighter-openspec-packages/design.md`).

**Suggestions** (low-priority PR-review residue):
- [Suggestion] `probe_state.py` `_implement_done`: test a required artifact that is absent from `artifacts[]`, and a non-list `applyRequires` (for example `"tasks"`), each with a mutant.
- [Suggestion] `probe_state.py` `_implement_done`: warn on stderr when `openspec status --json` carries neither `isComplete` nor `applyRequires`, as the bad-JSON path already does.
- [Suggestion] `probe_state.py` `_implement_done`: filter `artifacts[]` entries to string `id`s, so a malformed id cannot raise `TypeError`.
- [Suggestion] `test_cla_init_rules_match_config.py`: also flag unquoted items containing ` #` or ending in `:`, which YAML misreads too.
- [Suggestion] multi-spec's per-change size gate ignores the batch's total claim load.
- [Suggestion] `multi-spec/SKILL.md:40` and `multi-spec/references/phases.md:33` mention a run-log commit that `multi-spec/SKILL.md` says does not exist (older than this PR).
