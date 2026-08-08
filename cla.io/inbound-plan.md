# Consolidated fix plan — inbound findings from market-distiller-mcp + agentic-air

Verification: `cla.io/inbound-verification.md` — **29 items, 29 verified, 0 unverified**, each
row naming the command that produced its verdict. Both source files read end to end
(488 and 481 lines).

Scope: those two repos only. `claude-plugins` deliberately excluded for now.

---

## Judgment on the reports themselves

**Both are high quality, and better than my own review of the same code.** Concretely:

- Every claim I could reproduce, reproduced. Zero false positives among the 29 — the only
  adjustments are two *reframings* (below), not corrections.
- They supply reproductions, not assertions. Their numbers hold: I recomputed the
  newline-ratio maximum independently and got **1.6098** against a comment claiming 1.955
  and 1.667 — their figure exactly.
- Their fixes land in the right place. `GIT_CMD` is one shared constant in `_dispatch_lib.py`
  wired to **7 call sites**, not seven parallel regex edits.
- Their tests are heavier than mine: 25–40 tests per touched file, and they execute the
  thing (the probe runs under `sh` across five PATH states) where mine assert substrings.
- They caught defects in their own fixes before shipping — market-distiller's note that a
  first draft of the temp-dir cleanup used `shutil.rmtree` and deleted an entire synthetic
  repo in test is exactly the disclosure that makes the rest credible.

**Two reframings, neither a correction:**

- **MD-5 (`.gitattributes`)** — the file *does* exist here, so the source is not missing it.
  The real defect is that the comment says "*this repo's* `.gitattributes`", which is true in
  the source and false in every consumer the moment it syncs. Fix the claim's portability,
  not the file.
- **MD-8 / AA (`discover_tests.py`)** — their proposed fix is **better than mine**. I had
  proposed a new `cla.io/gates.json` convention landing in every consuming repo. Theirs —
  discriminate the empty outcome into `no-package-json` / `no-check-scripts` /
  `no-source-affecting-paths` and map the first to a *warn* pointing at
  `cla.io/project-facts.md` — is smaller, introduces no new convention, and fixes the actual
  harm (a false reason) rather than the stack assumption. **Adopting theirs, dropping mine.**

**Three of the 29 are defects I introduced in the previous session**, all in guards:
`ALLOW_PR_MERGE` bypass (PR #29), `PYEXE` never cleared (PR #31, a regression from the code
it replaced), `warn-wholesale-rewrite` dead outside the launch dir (PR #39, merged hours
before the report). A fourth is my own test being vacuous.

---

## Method: pull, do not re-derive

Nearly every item already has a written, tested fix in a consumer. `update-cla` runs in
reverse — this repo, consumer as source, scoped per asset. Given the record above, me
rewriting these would be the worst available option.

Two rules for every pull:

1. **Rule 3 in reverse.** Their copy is a re-specialized fork. Pull the *fix*, never their
   repo-specific adaptation around it. Scope every pull to the named asset.
2. **Reproduce, pull, re-reproduce.** Each fix has a supplied repro. Run it here before, and
   again after. A pulled fix that cannot be shown to close its own repro does not land.

Items marked **hand-carry** sit outside `SCAN_DIRS`/`SCAN_FILES` — `update-cla` moves them in
neither direction.

---

## Batch 1 — live authorization bypasses

agentic-air's own instruction: *"Port item 1 first. It is the only live authorization
bypass, and unlike everything else here it was introduced BY the code this sync brings in."*

| # | Item | Source |
|---|---|---|
| MD-2 / AA-1 | `ALLOW_PR_MERGE` disarmed by a quoted string | both |
| MD-1 | `git.exe` walks past **every** git guard | market-distiller |
| AA-2 | `hooks.json` probe: `PYEXE` uncleared, `exit 0`, weak liveness | agentic-air |

These compound: the bypass is silent *partly because* AA-2 keeps the notice out of the
transcript. Ship together.

**My calls:**
- Take `GIT_CMD` as written — shared constant, 7 call sites.
- **Do not** bundle base-name case folding (`GIT.EXE`) into this. It is a behaviour change,
  it belongs in its own change with its own test, and mixing it into a critical fix is how
  the last three regressions happened. market-distiller pinned the current limit as a
  contract test — keep that, widen deliberately later.
- Replace my vacuous
  `test_the_prefix_must_sit_where_a_shell_would_treat_it_as_an_assignment`, which passes
  because the token before the variable is `set`, not a separator.
- Adopt AA-2 in full including `exit 1`. It matches `_dispatch_lib`'s own documented
  contract; the current `exit 0` is the one place that regressed away from it.

## Batch 2 — guards that stopped guarding

| # | Item |
|---|---|
| AA-3 | `warn-wholesale-rewrite` dead outside the launch dir + noisy stderr (mine, #39) |
| MD-6 | three advisory hooks resolve git state with no `-C`, ignoring `payload["cwd"]` |
| MD-7 | `block-worktree-path-escape` fails open with zero diagnostic (0 `_warn` vs 5 in its sibling) |
| MD-16 | `warn-branch-base` warns off pre-command HEAD; `block-push` lifts a literal `$VAR` as a path |
| AA-6 | `warn-smoke-test-drift` entirely dead on Windows; harvests `text=` only |
| AA-7 | `mechanical-checks.mjs` — empty `forbidden` is a confident PASS |
| AA-8 | `test_project_facts_paths` `_WRAP_CHARS` lacks `[` `]` |

**My call on MD-10** (`_dispatch_lib` documents a fail-loud contract both dispatchers
violate): make an errored **non-advisory** hook emit `permissionDecision: "ask"` rather than
correcting the docstring downward. An enforcing guard that failed to load currently reads as
*allow*, on every call, through a channel nothing forces anyone to read. `ask` is the one
channel that cannot be ignored. This is a behaviour change and gets its own review.

## Batch 3 — data integrity

| # | Item |
|---|---|
| MD-3 | `log_run.py` (×4) — locale-decoded stdin corrupts the ledger; locale-encoded stderr breaks the exit-code contract |
| MD-4 | the two tests that should have caught it agreed with it on cp1252 |

The four copies must stay byte-identical — re-run `consistency-checks/` after. Then apply
MD-4's wider instruction: grep the whole test surface for `subprocess.run(... text=True ...)`
without `encoding=`, since any such test measures agreement between two processes rather
than conformance to a format.

## Batch 4 — the sync engine

Highest blast radius. Alone, last among the fixes, with `SKILL.md`'s exit-code contract moved
in the same change.

| # | Item |
|---|---|
| AA-4 (a–e) | lockfile CRLF · provenance discarded on a corrupt-but-present lock · non-atomic `_write_file` + `ValueError` escaping isolation · PR body over GitHub's 65536 limit after push · `temp/sync-<run-id>/` never cleaned, blocking the next `--mode pr` run |
| MD-11 | rollback discards git's return code; `_run` has no exception handling (verified: 0 `try:`) |
| AA-5 | a discovered-but-unadapted asset is never written and never surfaces; denominator is self-referential |

**Heed their warning:** do not use `shutil.rmtree` for (e) — `temp_dir` is caller-supplied.
`rmdir` fails harmlessly on anything it should not remove.

## Batch 5 — branch-convention hardcoding

| # | Item |
|---|---|
| MD-15 / MD-12 | `branch.py:26` and `probe_state.py:189,219,254` hardcode `feature/`, and `--quiet` makes the miss read as a clean negative |

Their design is right and consistent with this plugin's own conventions: a
`branch-prefix.local.md` overlay (never synced), `CLA_BRANCH_PREFIX` override, unambiguous
suffix fallback that announces what it adopted and refuses to guess between several. Take
their autouse-`conftest.py` fixture too — 11 of their tests otherwise inherit the running
repo's configuration, the same ambient dependency as MD-4.

## Batch 6 — hand-carry (outside the synced trees)

| # | Item |
|---|---|
| AA-9 | `cla.cmd` unconditionally broken on native Windows — verified `was was unexpected at this time.` |
| AA-10 | `claw.cmd` `GD`/`GCD` not pre-cleared, unlike `PYEXE` and `WORKTREE_PATH` in the same file |
| AA-12 | `run_tests.py` discovers no `*.test.mjs` — one file, 66 assertions, run by nothing |

AA-12 carries three traps worth honouring exactly: a missing `node` must be a **failure**,
not a skip; do not anchor the skip regex with `\W` (node's `ℹ` is category `Ll`); and
`if not scopes and not node_test_files` opens a false green — add `if not results: return 1`.

## Batch 7 — accuracy and hygiene

| # | Item |
|---|---|
| MD-13 | four measurably wrong comment claims (ratio recomputed 1.6098; `_git 5s` vs `GIT_TIMEOUT_SECONDS = 3`; six/four/three; a "pytest-era version" that never existed) |
| MD-5 | the `.gitattributes` claim is true here and false once synced — reword, don't delete |
| AA-11 | consumer tokens in synced core (`discover.py:165`, `fact-gatherer.md:63-64`) |
| — | arm a source-side `project-tokens.local.md` so AA-11 stops recurring |

Adopt MD-13's containment rule: an undated present-tense cross-repo measurement is
unverifiable from inside any one repo. Carry the observation date and past tense.

## Deferred, with reasons

- **MD-14** — `subprocess.run(text=True)` with no `encoding=` at **27 verified sites**,
  several in enforcing guards. They diagnosed it and deliberately left it: too broad to land
  unreviewed, and it wants a test that actually crosses the byte boundary, which the current
  suite structurally cannot (everything feeds `str`/`io.StringIO`). **Agreed — its own batch,
  after Batch 4.** Use `errors="replace"`: a guard should degrade to a mojibake'd path it can
  still reason about, never to `None`.
- **MD-9** — `warn-lint-on-edit` is an oxlint hook, not a lint hook. Degrades cleanly; the
  cost is a wasted process spawn per Edit and the appearance of coverage that does not exist.
  Their data-driven-overlay fix is right; not urgent.
- **MD-8** — adopt their reason-discrimination fix (above), sized with Batch 5.

## The pattern worth keeping

agentic-air's own porting note, which I think is the most valuable line in either file:

> Six of these twelve are the same defect shape: a guard that stops guarding without saying
> so. Each was found by asking *"what would this look like if it had silently switched off?"*
> rather than by reading for correctness.

That question belongs in the review procedure, not just in these fixes.
