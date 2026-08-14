# Proposal: remove-update-cla

## Why

The `update-cla` file-sync mechanism is superseded by the GitHub marketplace install (`claude plugin marketplace add crisradu75/logic-artisan`), which distributes the whole plugin directory as a versioned snapshot without any per-file reconcile machinery. Keeping both routes alive is actively harmful: the sync engine still syncs the `cla`/`cla.cmd` launchers that keep consumers on the legacy route, a consumer using both routes gets every `/cla:*` skill registered twice with nothing detecting it, and the 2026-08 project review flagged the skill as the portfolio's one remove-candidate ("being retired" per CLAUDE.md, with no removal date). The user has decided to remove it now rather than deprecate in place.

## What Changes

- **BREAKING** — delete the `update-cla` skill entirely: `.claude/plugins/cla/skills/update-cla/` (SKILL.md, references/, scripts/ including the discover→classify→apply sync engine, tests/, pyproject.toml). Consuming repos on file-sync must adopt the marketplace install to receive future updates.
- Delete the plugin-root sync-provenance lockfile `.claude/plugins/cla/.cla-sync-lock.json` (meaningful only to the sync engine).
- `conformance-checks/tests/test_no_project_tokens.py`: delete `test_the_scan_roots_match_what_the_sync_tool_actually_syncs` (it AST-parses `discover.SCAN_DIRS` and skips when `discover.py` is absent — dead weight once the engine is gone) and update the module docstring where it narrates the sync rationale.
- `conformance-checks/tests/test_no_hardcoded_plugin_paths.py`: drop the `update-cla` entry from `EXEMPT_SKILLS`; re-measure both non-vacuity floors (currently ≥95 files scanned, ≥34 `${CLAUDE_PLUGIN_ROOT}` uses) from actual post-deletion counts, keeping small headroom in the existing style.
- Docs in the same change: CLAUDE.md Portability section rewritten marketplace-only; pytest scope count 10→9 in CLAUDE.md and DEVELOPER-GUIDE.md; README.md "(10 today)" → 9; verify (not blindly edit) README.md's "18 workflow skills" claim, which becomes correct again at 19−1.
- Whole-repo sweep for residual `update-cla` / `.cla-sync-lock` / `claw` references (candidates: `report-upstream`, `sync-context`, `cla-init` skills, hook comments, `cla.io/`), each resolved or consciously kept (e.g. historical narration in decision docs stays).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `cla-plugin`: the sync-mechanism requirements are removed and the distribution/onboarding requirements change. Specifically: the update-cla overlay-preservation requirement, the sync-provenance lockfile requirement, the two-ancestor divergence classification, the source-side deletion detection, and the source-agnostic multi-source sync requirement are REMOVED; the onboarding-order requirement (currently `cla-init` then `update-cla`) is MODIFIED to `cla-init` → `sync-context` → marketplace install; the spec's purpose/header text describing distribution via `update-cla` is MODIFIED to name the marketplace as the sole distribution route. The overlay-preservation *convention* (fixed `cla.io/overlays/<skill>.md` paths, `*.local.md` markers) survives — it no longer needs a sync engine to enforce it, because a marketplace install never writes into `cla.io/`.

## Impact

- **Consumers still on file-sync** stop receiving updates until they run the two marketplace commands. Accepted trade-off (user decision, 2026-08-14).
- **Tests**: the aggregate suite drops from 10 pytest scopes to 9 (+ the Node suite). One conformance test is deleted, one has a dead exemption removed, and three non-vacuity floor comments are corrected — of which only `test_subprocess_encoding.py`'s floor actually moves (64 scanned `.py` files → 55, exactly its current threshold).
- **The repo-root launchers lose their distribution route.** `cla`/`cla.cmd` live outside the marketplace `path` and reached consumers only via `discover.SCAN_FILES`; after this change they serve this repo alone, and `launcher-checks/` tests files no consumer receives. The `claw`/`claw.cmd` `deleted-in-source` detection that surfaced a consumer's leftover copy also ends. Recorded, not solved here.
- **A known guard-coverage gap widens.** The marketplace ships the whole plugin directory, so `lib/`, the three `*-checks/` scopes, `run_tests.py`, and `mutate.py` now reach consumers while sitting outside the token guard's scan roots. Widening those roots needs a fixture-aware exemption first (those scopes hold project tokens as deliberate test fixtures), so this change records the gap in the spec, in `TODO.md`, and as a Deferred-Known-Issue rather than closing it.
- **No runtime behavior of any other skill changes** — remaining references to update-cla in other skills' prose are documentation, swept in this change. Verified: nothing outside `skills/update-cla/` imports its scripts, and no surviving plugin code writes into the plugin directory, so a read-only marketplace snapshot works unchanged.
- Acceptance gate: `python .claude/plugins/cla/run_tests.py` fully green post-change, plus a zero-hit grep for operative `update-cla` / `.cla-sync-lock` / `claw` references outside historical directories.
