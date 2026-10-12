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
