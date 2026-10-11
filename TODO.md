## Deferred from PR #294 (lighter-openspec-packages) — 2026-10-07

**Rejected remedies, still open** (findings whose proposed fix a delegate rejected with reasons; the defect is REAL and UNFIXED):
- (none)

**Deferred-Known-Issues** (Important PR-review findings the team consciously deferred):
- (none)

**Suggestions** (low-priority PR-review residue):
- [Suggestion] `probe_state.py` `_implement_done`: test a required artifact that is absent from `artifacts[]`, and a non-list `applyRequires` (for example `"tasks"`), each with a mutant.
- [Suggestion] `probe_state.py` `_implement_done`: warn on stderr when `openspec status --json` carries neither `isComplete` nor `applyRequires`, as the bad-JSON path already does.
- [Suggestion] `probe_state.py` `_implement_done`: filter `artifacts[]` entries to string `id`s, so a malformed id cannot raise `TypeError`.
- [Suggestion] `test_cla_setup_rules_match_config.py`: also flag unquoted items containing ` #` or ending in `:`, which YAML misreads too.
- [Suggestion] multi-spec's per-change size gate ignores the batch's total claim load.
- [Suggestion] `multi-spec/SKILL.md:40` and `multi-spec/references/phases.md:33` mention a run-log commit that `multi-spec/SKILL.md` says does not exist (older than this PR).

## Deferred from PR #324 (risk-sized-review) — 2026-10-11

**Rejected remedies, still open** (findings whose proposed fix a delegate rejected with reasons; the defect is REAL and UNFIXED):
- (none)

**Deferred-Known-Issues** (Important PR-review findings the team consciously deferred):
- (none)

**Suggestions** (low-priority PR-review residue):
- [Suggestion] `orchestration-economy.md` debris check: the before/after `git status --ignored` diff also lists interpreter caches (`__pycache__/*.pyc`) on every Python run; say to ignore them, and to delete half-written `*.pyc.<pid>` files that parallel workers leave.
- [Suggestion] `spec-to-pr-retro`: `round_2_yield` now counts only rounds after a fixed Critical (plus re-entry and resume fail-safe rounds), so a threshold across pre- and post-change runs mixes two populations; note it, or tag those rounds.
- [Suggestion] `revise.md`: repeat the resume fail-safe ("cannot tell whether round 1 fixed a Critical → run the next round") at the exit gate, where the round-2 decision is made.
- [Suggestion] `handoff.md` §2 one-line body rewrite starts at "Closes…", so a stacked child loses its "Stacked on #N." clause (older than this PR); keep the original one-liner verbatim.
- [Suggestion] `model-routing.md` restates skill-reviewer's model outside "Review sizing by risk" (around the rubric-checks paragraph), and plugin `README.md`'s skill-reviewer row does too; cite the section instead.
- [Suggestion] `model-routing.md` "as `revise.md` describes" has no path; use the plugin-root path. Several new sentences in `model-routing.md`, `revise.md` round-1 selection and `lite-pr` Review run past 25 words.
- [Suggestion] `test_review_sizing_single_source.py` pins exact round-2 sentences; acceptable for a prose guard, but a reword with the same meaning fails it.
