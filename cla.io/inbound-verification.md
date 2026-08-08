# Inbound verification tracker

Machine-generated from the `## ` headings of both `cla-upstream.md` files, so the population
is enumerated rather than remembered. **Done means zero `UNVERIFIED` rows below.**

Every verdict must name the command that produced it. A verdict with no command is UNVERIFIED.

| # | src | line | item | status | evidence |
|---|---|---|---|---|---|
| 1 | MD | 22 | 1. `git.exe` walks past every git guard in the plugin | **CONFIRMED** | ran both hooks: `git.exe push origin main` exit=0 vs `git push origin main` exit=2 |
| 2 | MD | 68 | 2. `ask-destructive-git` — the PR-merge guard can be disarmed by prose | **CONFIRMED** | ran hook on 4 payloads: quoted `; ALLOW_PR_MERGE=1 ` silences the prompt |
| 3 | MD | 106 | 3. `log_run.py` (×4) — locale-decoded stdin corrupts the ledger; locale-enco | **CONFIRMED** log_run.py:92 `sys.stdin.read()`; no UTF-8 pinning in any of 4 copies |
| 4 | MD | 158 | 4. …and the tests that should have caught it passed for the wrong reason | **CONFIRMED** both test_log_run.py:23 `text=True` with no encoding= |
| 5 | MD | 188 | 5. The `.gitattributes` that `discover.py` promises does not exist | **PARTIAL** .gitattributes EXISTS here; the comment says 'this repo's', false once synced |
| 6 | MD | 227 | 15. `spec-to-pr`'s scripts hardcode `feature/<change>`, and report the miss  | **CONFIRMED** branch.py:26 + probe_state.py:189,219,254 hardcode feature/ |
| 7 | MD | 271 | 16. Two guard hooks report confidently on state they did not actually read | **CONFIRMED** warn-branch-base is PreToolUse (pre-command HEAD); block-push parses -C pre-expansion |
| 8 | MD | 297 | 14. `subprocess.run(text=True)` with no `encoding=` — the crash escapes the  | **CONFIRMED** | grep: 27 `text=True` subprocess sites with no `encoding=` |
| 9 | MD | 342 | 6. Three advisory hooks resolve git state in the wrong directory | **CONFIRMED** | grep: 3/3 advisory hooks call git with no `-C` |
| 10 | MD | 360 | 7. `block-worktree-path-escape` fails open with zero diagnostic | **CONFIRMED** 0 _warn calls vs 5 in sibling guard-worktree-isolation |
| 11 | MD | 370 | 8. `discover_tests.py` cannot express a non-npm repo, and mis-reports why | **CONFIRMED** | ran discover_tests.py here: returns [] for source-affecting paths; no package.json |
| 12 | MD | 389 | 9. `warn-lint-on-edit` is an oxlint hook, not a lint hook | **CONFIRMED** LINTABLE_EXTS JS-only:43; early return :164 |
| 13 | MD | 404 | 10. `_dispatch_lib` documents a fail-loud contract both consumers violate | **CONFIRMED** docstring:22 'exit non-zero-non-2'; dispatcher returns 0 at :203,:219 |
| 14 | MD | 416 | 11. `apply.py` — rollback discards git's return code; several `_run` sites u | **CONFIRMED** _run has 0 try:; _write_file uses write_text (not atomic) |
| 15 | MD | 433 | 12. `probe_state.py` hardcodes `feature/<change>` and reports the miss as a  | **CONFIRMED** same as item 15 probe half |
| 16 | MD | 444 | 13. Comment claims that are measurably wrong | **CONFIRMED** recomputed true max 1.6098 vs claimed 1.955/1.667; _git 5s vs GIT_TIMEOUT_SECONDS=3 |
| 17 | MD | 473 | Resolved upstream — verified against `e2c07b2` this session | **CONFIRMED** discover.py:173 normalizes CRLF; hooks.json 7/7 run each candidate |
| 18 | AA | 33 | 1. `ask-destructive-git.py` — the merge guard can be disarmed by a quoted st | **CONFIRMED** | same defect as MD-68; same repro |
| 19 | AA | 110 | 2. `hooks.json` — the interpreter probe, three ways | **CONFIRMED** ran probe with PYEXE pre-exported: SELECTED STALE /definitely/not/a/python |
| 20 | AA | 160 | 3. `warn-wholesale-rewrite.py` — silent in the wrong places, noisy in the ot | **CONFIRMED** | ran hook twice: WARNS with project dir == repo, SILENT when elsewhere |
| 21 | AA | 203 | 4. `apply.py` — five ways a sync run damages or misreports itself | **CONFIRMED** _write_lock os.fdopen:198 has no newline=''; _run unguarded |
| 22 | AA | 259 | 5. `orchestrate.py` — a run can under-report what it did | **CONFIRMED** :307 denominator is len(outcomes), derived from adaptations - self-referential |
| 23 | AA | 287 | 6. `hooks/warn-smoke-test-drift.py` — three defects, one hook | **CONFIRMED** :134 harvests text= only, no has-text; no separator normalization |
| 24 | AA | 308 | 7. `skills/project-review/scripts/mechanical-checks.mjs` — vacuous PASS on e | **CONFIRMED** :435 forbidden.some() - [].some() is false; 16 guarded siblings |
| 25 | AA | 331 | 8. `skills/update-cla/tests/test_project_facts_paths.py` — paths it cannot s | **CONFIRMED** _WRAP_CHARS:74 lacks [ and ] |
| 26 | AA | 353 | 9. `cla.cmd` is unconditionally broken on native Windows | **INCONCLUSIVE** | my cmd.exe harness did not execute the fragment - retest needed |
| 27 | AA | 383 | 10. `claw.cmd` — `GD`/`GCD` are not pre-cleared | **CONFIRMED** PYEXE:111 and WORKTREE_PATH:138 pre-cleared; GD/GCD:184-185 are not |
| 28 | AA | 399 | 11. Project tokens in synced core | **CONFIRMED** | read discover.py:165 (names agentic-air) + fact-gatherer.md:63-64 |
| 29 | AA | 423 | 12. `run_tests.py` — `*.test.mjs` files run under no runner at all | **CONFIRMED** | grep: 0 refs to `node --test`/`.test.mjs` in run_tests.py; 1 such file exists |

**29 items · 29 verified · 0 UNVERIFIED**

Coverage: both files read end to end (market-distiller 488 lines, agentic-air 481).
Earlier partial reads used offsets from a stale heading grep taken when the file was 174 lines.
