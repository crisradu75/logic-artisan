## Renamed top-level paths are not reported stale (needs a rule that tells plugin-relative shorthand from a renamed directory; idea: git rename history) — 2026-10-12

Split out of PR #333 (local-path-skip). `check_fact_paths.py` `_keep_if_path` skips any path whose first segment is not a tracked top-level name, so when a top-level directory is renamed, a path under its old name (`old/src/x.ts`) goes unreported. That falls short of "every repo path" in the `repo-context` requirement "Checking recorded paths".

**Why the PR dropped it.** No generic shape rule separates a renamed directory from a plugin-relative reference. The versions tried:
- A path-shape rule (path-safe characters, plain first segment, then a file extension or a trailing slash) kept 278 more tokens than main over this repo's own markdown, most of them plugin-relative shorthand such as `skills/cla-setup/scripts/x.py` and `_shared/references/x.md`. Requiring three or more segments for an extension cut that to 181 and kept two-segment repo names such as `vercel/next.js` out. Without a segment count, prose lists (`Edit/Write/Bash`, `PASS/FAIL/SKIP`) also matched.
- Build output (`dist/index.js`, `node_modules/.bin/`) needed a `git check-ignore` exemption.
- A wrong root or a wrongly small top-level set made the "zero candidates" exit-2 guard unreliable once shape-only paths counted.

**Evidence from three other repos** (read-only copies of tracked layout, facts file and overlays, run with main's checker and with the shape rule; the 3-segment rule):
- claude-plugins: main exit 0, shape rule exit 1: `skills/cla-setup/scripts/check_fact_paths.py` (`cla.io/project-facts.md:5`), `skills/savefile/SKILL.md` (`cla.io/overlays/review-change.md:269`). Both plugin-relative.
- market-distiller-mcp: main exit 0, shape rule exit 1: `skills/_shared/scripts/check_no_project_tokens.py`, `skills/cla-setup/scripts/check_fact_paths.py` (`project-facts.md:76-77`), and `yahoo_news/earnings/dividends/quote/indicators.py` (`overlays/project-review.md:52`, brace shorthand written out as a list).
- interoga-ro: main exit 1 (`docs/mission.md`), shape rule exit 1 with four more: `skills/cla-setup/scripts/check_fact_paths.py`, `ux/mvp-mock/` and `ux/brand/` (`project-facts.md:174`; `ux/` is not in the repo, so these are genuine stale references main misses), and `landing/exemplu/` (`project-facts.md:278`; possibly a URL route in prose).

**Idea.** Use git rename history (`git log --diff-filter=R --name-status`) to report a path only when its first segment was a tracked top-level name at some earlier commit. That separates `ux/mvp-mock/` (once tracked) from `skills/x/y.py` (never a top-level name of this repo), at the cost of a history walk.

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
