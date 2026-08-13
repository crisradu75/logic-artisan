# Tasks: remove-update-cla

## 1. Delete the sync engine

- [x] 1.1 Delete `.claude/plugins/cla/skills/update-cla/` entirely (SKILL.md, references/, scripts/, tests/, pyproject.toml) via `git rm -r`
- [x] 1.2 Delete `.claude/plugins/cla/.cla-sync-lock.json`

## 2. Test ripples

- [x] 2.1 In `conformance-checks/tests/test_no_project_tokens.py`: delete `test_the_scan_roots_match_what_the_sync_tool_actually_syncs` (~:341-372); rewrite the inline explanatory block at ~:202-214 that justifies the hand-typed `SOURCE_SCAN_ROOTS` by pointing at the now-deleted test — replace it with the marketplace-ships-the-whole-dir rationale plus the recorded coverage gap; update the module docstring where it narrates the sync rationale
- [x] 2.2 In `conformance-checks/tests/test_no_hardcoded_plugin_paths.py`: remove the `update-cla` entry from `EXEMPT_SKILLS` (~:46) and the now-dead exemption check (~:62)
- [x] 2.3 Measure the real post-deletion counts for `test_the_scan_is_not_vacuous` (~:91, floor ≥95) and `test_the_replacement_is_actually_in_use` (~:105, floor ≥34). Expect both UNCHANGED (EXEMPT_SKILLS already excluded update-cla from the scan): correct only the stale inline "real count" comments to the measured values; change a floor only if a measurement contradicts that expectation
- [x] 2.4 Re-measure and re-baseline the third floor: `consistency-checks/tests/test_subprocess_encoding.py:161` (`len(names) >= 55`, comment "real count (55)" already stale) — 64 scanned `.py` files today, 9 of them update-cla's, so it lands at exactly 55 with zero margin. Set the floor with real headroom and fix the comment

## 3. Doc ripples — repo-root docs

- [x] 3.1 CLAUDE.md: rewrite the Portability section (~:313-319) marketplace-only; remove update-cla from the skills table (~:258) and the scripts table; fix the `.cla-sync-lock.json` line in the layout tree (~:216); fix `update-cla` mentions at ~:11, ~:13, ~:51, ~:201; fix the counts at ~:97 ("5 today" → 4), ~:99 ("10 in total" → 9), and ~:163 ("11th entry alongside the 10 pytest scopes" → 10th / 9)
- [x] 3.2 README.md (repo root): fix operative update-cla references at ~:5, ~:39, ~:63, and the adoption recipe at ~:69-71 (replace with the two marketplace commands); "(10 today)" → 9 (~:82); verify "18 workflow skills" (~:51) is correct at 19−1 and fix only if wrong
- [x] 3.3 DEVELOPER-GUIDE.md: fix the scope count (~:278) and the "7 skills with tests" count (~:285, already wrong — actual 5, becomes 4); fix the cheat-sheet rows (~:321-322). §10 (~:250-268) is wholly the file-sync adoption route, so replace steps 1-3 with the marketplace install + `cla-init` + `sync-context` chain and delete the "Re-run `update-cla` any time" line — a minimal correct rewrite, not the full §7/§8 overhaul deferred to a later change
- [x] 3.4 TODO.md: rewrite the operative pending action at ~:76-105 ("Run `/cla:update-cla` inside `market-distiller-mcp`") and the ~:67 / ~:101 migration notes as marketplace-migration notes; add the token-guard coverage gap (from design decision 2) as a tracked follow-up entry

## 4. Doc ripples — plugin-internal

- [x] 4.1 `.claude/plugins/cla/README.md`: remove the update-cla table row (~:34) and the "retired, kept only while repos migrate" sentence (~:127); fix its own scope counts ("5 today" ~:132, "10 in all" ~:134)
- [x] 4.2 `skills/sync-context/SKILL.md`: fix all six operative references — ~:14, ~:18 (onboarding order → marketplace install → `cla-init` → `sync-context`), ~:30, ~:148 (`SCAN_DIRS`), ~:210, ~:236
- [x] 4.3 `skills/cla-init/SKILL.md`: onboarding order (~:15, ~:21-22); the "Explicit exclusions" carve-out naming update-cla (~:129) now vacuous; the asset-core-sync sentence (~:189)
- [x] 4.4 Sweep-classify the remaining synced-core and state hits, fixing each or recording why it stays: `spec-to-pr/references/progressive-disclosure.md:33`, `project-review/SKILL.md:37`, `project-review/scripts/mechanical-checks.mjs:9`, `hooks/block-worktree-path-escape.py:33`, `conformance-checks/pyproject.toml:6-12`, `consistency-checks/tests/test_token_list_is_curated_here.py:11`, `cla.io/project-tokens.local.md:5`, `cla.io/overlays/codify-learnings.md:18` (`scope: skills/update-cla`), `.gitattributes:8`, and the boilerplate "never synced by update-cla" header in every `cla.io/overlays/*.md`

## 5. Gate

- [x] 5.1 `python .claude/plugins/cla/run_tests.py` fully green: 9 pytest scopes + the Node suite, zero near-miss warnings, zero new skips
- [x] 5.2 Confirm no orphan scope: no dir under the plugin with exactly one of {pytest-configured `pyproject.toml`, `tests/`}
- [ ] 5.3 Update `openspec/specs/cla-plugin/spec.md`'s `## Purpose` paragraph (~:3-16) — drop "distributes to other repos via `update-cla`" and the "cross-repo sync mechanism (discover → 3-way reconcile → apply…)" clause — at archive preflight, in the archive commit
- [x] 5.4 Final verification grep: `update-cla`, `.cla-sync-lock`, `claw` across the repo excluding `cla.io/decisions/`, `cla.io/lessons-learned/`, `cla.io/retro/`, `cla.io/inbound-*.md`, `openspec/changes/archive/`, and `.git/` — expect zero operative hits; list any survivor with its keep-rationale
