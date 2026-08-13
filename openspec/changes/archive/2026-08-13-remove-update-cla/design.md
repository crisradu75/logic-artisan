# Design: remove-update-cla

## Context

`update-cla` is a pull-based, stdlib-only file-sync engine (discover → 3-way reconcile → apply, with a per-repo provenance lockfile) that predates the plugin's marketplace distribution. Since `0.9.x`, consumers install `cla` via `claude plugin marketplace add crisradu75/logic-artisan` — a whole-directory versioned snapshot with none of the per-file reconcile problem the sync engine solves. CLAUDE.md has marked the skill "being retired" with no removal date. The 2026-08-14 project review found the retirement exists only in prose: the skill itself carries no deprecation marker, and its `SCAN_FILES` still syncs the `cla`/`cla.cmd` launchers — the legacy mechanism actively propagating the thing that keeps consumers on it. The user decided (2026-08-14) to remove it now.

## Goals / Non-Goals

**Goals:**
- Exactly one distribution route: the GitHub marketplace, pinned to an exact release tag.
- The aggregate test suite stays fully green with the update-cla scope gone (9 pytest scopes + the Node suite).
- The conformance guards keep their teeth: floors re-measured, not guessed; no test left permanently skipping.
- Every remaining `update-cla` / `.cla-sync-lock` / `claw` reference in operative prose is resolved; historical records stay.

**Non-Goals:**
- No migration tooling for consumers still on file-sync — the two marketplace commands are the migration.
- No change to the overlay convention itself (`cla.io/overlays/<skill>.md`, `*.local.md`) — it survives without an enforcement engine because a marketplace install never writes into a consumer's repo.
- No launcher changes: `cla`/`cla.cmd` remain, as this repo's own dev-session entry point.
- No release cut in this change (the batch releases together as 0.10.0 later).

## Decisions

1. **Delete outright, not deprecate-in-place.** A banner would keep dead code (a ~1,900-line sync engine + its test scope) alive indefinitely with no removal trigger. The marketplace route has been live for three releases; consumers who haven't migrated get a clean, documented cliff instead of silent divergence. (User decision; alternative — banner + double-registration check — was offered and declined.)
2. **Delete `test_the_scan_roots_match_what_the_sync_tool_actually_syncs` — but its forcing function is NOT superseded; it inverts.** The test AST-parses `discover.SCAN_DIRS` and already `pytest.skip`s when `discover.py` is absent, so with the engine gone it can never run again, and a permanently-skipped guard is worse than none (the suite's summary flags skips as "a guard that has not run"). Deleting it is right because it asserts against the *dead* mechanism. But the earlier claim that the forcing function is superseded was wrong, and the review caught it: the marketplace `path` is `.claude/plugins/cla` — the **whole directory** — so what ships now *includes* `lib/`, the three `*-checks/` scopes, `run_tests.py`, and `mutate.py`, every one of them outside the token guard's four `SOURCE_SCAN_ROOTS`. Distribution got *wider* than the guard, not narrower. **Widening the roots is deliberately out of scope here**: the `*-checks/` scopes legitimately contain project tokens as test fixtures (e.g. `test_token_list_is_curated_here.py`), so widening would fail immediately and needs a fixture-aware exemption designed first. This change therefore records the gap explicitly — in the modified spec requirement, in `TODO.md`, and as a Deferred-Known-Issue on the PR — rather than deleting the hint and saying nothing.
3. **Fix the stale floor comments; only one floor actually moves.** The earlier plan to "re-measure all the floors" rested on a false premise, corrected by review: `test_no_hardcoded_plugin_paths.py:62` already skips every path whose second segment is in `EXEMPT_SKILLS`, and `update-cla` is that set's only member — so deleting the skill removes **zero** scanned files and **zero** `${CLAUDE_PLUGIN_ROOT}` uses. Measured today: 99 files / 36 uses, identical after deletion. Those two floors (≥95, ≥34) stay as they are; only their stale inline comments ("real count is 97") are corrected to the measured values. The floor that *does* move is a third one nobody listed: `consistency-checks/tests/test_subprocess_encoding.py:161` asserts `len(names) >= 55` over 64 `.py` files today, 9 of which are update-cla's — landing at exactly 55, passing with zero margin, with an already-stale "real count (55)" comment. Re-measure and re-baseline that one.
4. **Onboarding order becomes `cla-init` → `sync-context` → marketplace install.** The spec requirement currently pins `cla-init` → `update-cla` and requires the order documented in both skills' SKILL.mds; it is modified to the new chain, documented in `cla-init` alone (the marketplace commands are CLI, not a skill).
5. **In-place activation narrows to this repo.** The spec's "activated in place via `--plugin-dir` (not a cached marketplace install)" requirement is modified: in-place activation is the *development* mode for the canonical repo (live working tree, repo-local state); a consuming repo activates the marketplace-installed snapshot. Repo-local state (`cla.io/`) lives outside the plugin dir, so a read-only cached install works unchanged.
6. **Sweep policy: operative vs historical.** References in skills, hooks, tests, README/CLAUDE.md/DEVELOPER-GUIDE prose are operative — rewritten or removed. References inside `cla.io/decisions/`, `cla.io/lessons-learned/`, `openspec/changes/archive/`, and dated retro records are historical — left intact (they record what was true when written). **`TODO.md` is explicitly operative, not historical**: lines 67 and 76–105 hold a *pending action* ("Run `/cla:update-cla` inside `market-distiller-mcp`") plus consumer migration notes, which become unrunnable — they are rewritten as marketplace-migration notes, not preserved as history.
7. **Main-spec Purpose prose is updated at Archive preflight.** Delta specs carry requirement operations only, so the Purpose paragraph naming `update-cla` as the distribution route cannot be expressed as a requirement operation; it is corrected during the archive-preflight retired-path cleanup, in the same commit as the archive. Review flagged the risk that a deferral like this silently never happens, so it is carried as an explicit task (5.3) rather than left to preflight convention alone.
8. **The launchers lose their distribution route, and that is accepted.** `cla`/`cla.cmd` sit at the repo root, outside the marketplace `path` (`.claude/plugins/cla`), and reached consumers only via `discover.SCAN_FILES`. With the engine gone they are this repo's own dev-session entry point and nothing else; a consuming repo that wants one copies it by hand. The same deletion also ends the `claw`/`claw.cmd` `deleted-in-source` detection that let a consumer's leftover copy surface. Both consequences are recorded in Impact rather than solved here — solving them means either moving the launchers inside the plugin directory or shipping a bootstrap command, each its own change.

## Risks / Trade-offs

- [Consumers still on file-sync stop receiving updates] → Accepted explicitly by the user; README/CLAUDE.md state the marketplace commands as the only route, so the migration is one copy-paste.
- [Floors set too tight/loose after re-measure] → Measured from the real tree in the same change that deletes the files; `run_tests.py` green is the gate.
- [A hidden operative reference to update-cla survives] → Whole-repo grep sweep for `update-cla`, `.cla-sync-lock`, `claw` is an explicit task with a per-hit resolve-or-keep decision; the conformance suite plus `run_tests.py` catch import-level residue.
- [The deleted engine is needed again] → Git history preserves it wholesale; `discover.py` was designed for deletion ("Deleted wholesale when distribution moves to a marketplace plugin" — CLAUDE.md's own script table).

## Migration Plan

Single PR. No deploy steps. Rollback = revert the PR (the engine is self-contained; nothing else imports it). Consumer migration is documented, not tooled: `claude plugin marketplace add crisradu75/logic-artisan` + `claude plugin install cla@cris-logic-artisan --scope project`.

## Open Questions

(none — the two judgment calls, removal-vs-deprecation and floor policy, are decided above)
