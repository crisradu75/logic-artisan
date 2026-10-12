## Deferred from the former-top-level-names PR (check_fact_paths) — 2026-10-12

**Suggestions** (low-priority PR-review residue):
- [Suggestion] `check_fact_paths.py` `_former_top_level_names`: `rev-parse --is-shallow-repository` fails on git older than 2.15 and is reported as "not a git repository"; probe `rev-parse --git-dir` first.
- [Suggestion] `_former_top_level_names`: a case-only rename (`Docs` to `docs`) on a case-insensitive filesystem yields a former name that matches nothing (fails safe).
- [Suggestion] `_former_top_level_names`: the two git calls can spend up to 60s each on a huge history, on every run; consider one shared time budget.
- [Suggestion] `agentic-air`: bare package-relative shorthand that starts with a once-top-level name (`src/index.ts`, `public/data/`) is now reported (3 new in legacy overlays); no generic rule separates it from a stale path.

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

## Deferred from PR #326 (cla-economy-rules-file) — 2026-10-11

**Suggestions** (low-priority PR-review residue):
- [Suggestion] `plugin-tests/tests/conformance/test_no_hardcoded_plugin_paths.py`: the scan floor is `>= 101` against a real count of 103 files, so two files could vanish unnoticed (the gap is partly older than this PR). Left unchanged here; raise the floor to the real count in its own change.

## Deferred from PR #327 (meter) — 2026-10-12

**Suggestions** (low-priority PR-review residue):
- [Suggestion] `plugin-tests/scripts/meter.py:72-76`: when the last copy of a streamed message lacks `model`, it is filed under `<unknown>`; keep the earlier copy's model instead.
- [Suggestion] `plugin-tests/scripts/meter.py:59-60`: an unreadable transcript raises a traceback instead of the documented exit 1 with a stderr message.
- [Suggestion] `plugin-tests/scripts/meter.py:53-56`: a resumed or forked session that replays history into a new file double-counts those messages; say so in the docstring.
- [Suggestion] `plugin-tests/tests/consistency/test_meter.py`: add a same-id same-model case across two files; assert per-model rows and sort order in the table; compare `--json` to the full literal dict.

## Deferred from PR #328 (caps-and-tasks) — 2026-10-12

**Suggestions** (low-priority PR-review residue):
- [Suggestion] `test_artifact_caps_agree.py`: assert the tasks rules in the tasks block specifically, check "one page" gone from config.yaml too, and give the `next()` lookups a clear failure message.

## Deferred from PR #330 (one retry budget in lite-pr Test) — 2026-10-12

- [Suggestion] `lite-pr/SKILL.md` paragraph after Test step 4: "the second hypothesis is better-informed than the first" and "halt at step 4" for a symptom fix predate the one-budget wording; a retry that fails on a different cause halts without a diagnose step (confirm that is intended).

## Deferred from PR #329 (lite-pr-lazy-load) — 2026-10-12

**Suggestions** (low-priority PR-review residue):
- [Suggestion] `mutation-gate.md:7,27`: "a real fix here" and "two commits in this repo" read wrongly in a shipped file; say "in the CLA source repo".
- [Suggestion] `lite-pr/SKILL.md`: the trailer-block rule is still stated in the Ship hand-off paragraph and in `measured-by.md`; the review-fix-weight pointer uses a relative path; the paragraph after Test step 3 is not indented under the numbered steps.
- [Suggestion] `plugin-tests/tests/consistency/test_mutation_gate_sites_agree.py` docstring still names `lite-pr/SKILL.md` as the gate site.
- [Suggestion] `spec-to-pr/references/archive.md:21`: the post-check names `<YYYY-MM-DD>`; if midnight passes between `openspec archive` and the check it gives a false warning. `ls -d openspec/changes/archive/*-<change-name>/proposal.md` avoids it (pre-existing).

## Deferred from PR #334 (review-sizing-followups) - 2026-10-12

**Suggestions** (low-priority PR-review residue):
- [Suggestion] `lite-pr/SKILL.md` Review: "Route each per the same file" now sits two sentences after the file is named; name `model-routing.md` there.
- [Suggestion] `model-routing.md` rubric-checks sentence says the skill reviewer runs on Sonnet, then the next sentence overrides it; add "except as noted next".
- [Suggestion] `handoff.md:13` omits "names an unknown level" from the Risk-line fallback that `revise.md` covers.
- [Suggestion] `orchestration-economy.md` debris rule: limit the ignore to `__pycache__` folders beside tracked `.py` files; no guard or mutant covers the new Handoff and resume sentences.
- [Suggestion] `README.md` skill-reviewer row: the Sonnet case (frontmatter change or new skill) is not in the sizing table; point to lite-pr and `revise.md`.
- [Suggestion] `DEVELOPER-GUIDE.md` `check_fact_paths.py` row restates `_is_machine_local` (`check_fact_paths.py:382`) as prose; consider pointing to the function instead.
- [Suggestion] `test_chain_merge_shared.py` CI-wait test: name says "everywhere" but scans skills, README and DEVELOPER-GUIDE only (not `openspec/specs`); assert each `checks still pending` arm separately instead of counting two.
