# Inbound findings — defects reported by consuming repos about this source

The reverse of a consumer's `cla-upstream.md`: things destination repos found in
**logic-artisan's** synced core. Collected and triaged before anything is fixed, because a
wrong fix here fans out to every consumer.

**Status:** `CONFIRMED` reproduced here · `REPORTED` claimed with evidence, not yet
reproduced here · `REJECTED` verified false positive · `PARTIAL` real but different in
scope from the report.

**Sources:** `market-distiller-mcp/cla-upstream.md` (7 items, fixes applied there),
`agentic-air/cla-upstream.md` (6 items, fixes applied there).

---

## The headline

**Three of these are code I shipped in this session, and two of those are guards whose
entire purpose is to stop an unauthorized action.** The pattern the consumers found is the
one already named in `lessons-learned`: the artifact was checked, the system it lands in
was not.

**Nearly every finding already has a written, tested fix in a consumer repo.** The plan
below pulls those fixes rather than re-deriving them — which is both cheaper and lower-risk
than me writing them a second time.

---

## CRITICAL — a guard that does not guard

### C1. `git.exe` walks past every git guard in the plugin `CONFIRMED`

**From:** market-distiller-mcp · **Fix exists there.**

`_dispatch_lib.GIT_GLOBAL_OPTS` and seven consumers anchor on `\bgit\s+`. `\s` cannot match
the `.` in `git.exe`. Reproduced here:

```
git push origin main       exit=2  blocked
git.exe push origin main   exit=0  ALLOWED
git.cmd push origin main   exit=0  ALLOWED
```

Affects **every git guard shipped**: `block-direct-push-to-main`, both `ask-*`,
`guard-worktree-isolation`, `warn-branch-base`, `warn-stray-scratch-artifact`.

Reachable by ordinary use, not evasion — PowerShell is a primary shell here and its
tab-completion emits `git.exe`.

The tell it is an oversight: `_GH_PR_MERGE` already spells the sibling tool as
`\bgh(?:\.(?i:exe|cmd|bat|com|ps1))?`, with a comment saying it exists "because Windows is
the primary platform". The identical reasoning was never applied to `git`.

**Their fix:** one shared `GIT_CMD` constant in `_dispatch_lib.py`, all seven call sites
switched. Lands once instead of in seven regexes.

### C2. The PR-merge confirmation can be disarmed by prose `CONFIRMED`

**From:** market-distiller-mcp · **Mine, PR #29, this session.** · **Fix exists there.**

`ask-destructive-git.py:298` checks `_ALLOW_MERGE_PREFIX.search(command)` — the **raw**
command. Every other matcher in the file scans `_strip_quoted_spans(command)`. So the
literal anywhere after a shell separator disarms the prompt, including inside a quoted
string bash never evaluates as an assignment. Reproduced here:

```
ASK     gh pr merge 123 --squash
SILENT  gh pr merge 123 --squash && echo "done ; ALLOW_PR_MERGE=1 was not used"
SILENT  echo "; ALLOW_PR_MERGE=1 " && gh pr merge 123 --squash
```

It also announces "DISABLED by ALLOW_PR_MERGE=1" when nobody set it. `multi-pr`/`multi-lite`
run unattended, and this hook exists precisely because two PRs were merged that the user had
asked to be *built*, not shipped.

**Their fix:** `_ALLOW_MERGE_PREFIX.search(_strip_quoted_spans(command))`. A genuine inline
prefix is unquoted, so it survives stripping.

### C3. The interpreter probe has three defects, one a regression `REPORTED`

**From:** agentic-air, with measurements · **Mine, PR #31, this session.** · **Fix exists there.**

1. **`PYEXE` is never cleared.** The loop only assigns on success, so `${PYEXE:-}` reads
   whatever the parent exported. Measured: with only stubs on PATH and
   `PYEXE=/definitely/not/a/python` exported, the probe selected it and printed no warning.
   **A regression** — the old `PYEXE=$(command -v …)` form always overwrote. Also drift from
   both launchers, which do clear it, and which the `_comment` claims parity with.
2. **Failure is `exit 0`.** The `_comment` says failure "is announced rather than silent".
   It is not — stderr from an exit-0 hook reaches the debug log only. This plugin's own
   `_dispatch_lib.py` states that contract and the dispatchers deliberately exit
   non-zero-non-2 so the transcript notice fires.
3. **Liveness is `-c "import sys"`**, which succeeds on Python 2.7 and on any wrapper that
   swallows `-c`.

**Their fix:** `PYEXE=;` first; `exit 1` not `exit 0`; assert the version **via stdout**
(`print(1 if sys.version_info >= (3,8) else 0)`) so a silent stub and a Python 2 are both
rejected. Plus: `_pyexe` in `hooks.json` is decoration — nothing reads it, JSON has no
interpolation — and their `test_hooks_wiring.py` now **executes** the probe under `sh`
across five PATH states. Every probe test here is a substring assertion.

---

## HIGH — silent data loss, or a guard dead in the common path

### H1. `warn-wholesale-rewrite` is dead for any write outside the launch dir `REPORTED`

**From:** agentic-air · **Mine, PR #39, merged today.** · **Fix exists there.**

`CLAUDE_PROJECT_DIR` is the **launch** directory, not "the repo being edited". A session
that enters a worktree after launch writes every file outside it, `relative_to` raises, and
the hook returns 0 for the rest of the session with no output. In a plugin whose own tooling
is worktree-based (`guard-worktree-isolation`, `claw`, `/cla:new-worktree`) that is the
common path, not an edge case.

**Their fix:** resolve the work tree from the FILE (`git -C <dir> rev-parse --show-toplevel`)
when the path falls outside `CLAUDE_PROJECT_DIR`, and only then.

### H2. …and its stderr diagnostic fires when it should not `REPORTED`

**From:** agentic-air · **Mine, PR #39.**

The "git ran but could not resolve" filter matches two English phrases. Neither
`fatal: not a git repository` nor `fatal: invalid object name 'HEAD'` contains them, so the
diagnostic printed on **every Write in a scratch directory**. Its test asserted silence but
read only stdout, so it passed throughout. Phrase-matching English stderr also breaks under
a non-English `LANG` for every case.

**Their fix:** ask git the question instead of parsing its prose — `rev-parse --verify HEAD`
failing means no baseline, an environment condition rather than a path this hook built wrong.

### H3. `log_run.py` (×4) corrupts the ledger via locale decoding `REPORTED`

**From:** market-distiller-mcp · **Fix exists there, applied to all four copies.**

Present in `spec-to-pr`, `codify-learnings`, `multi-lite`, `multi-spec`.

- **Silent corruption.** `sys.stdin.read()` decodes with the ambient encoding (cp1252 on a
  stock Windows box) while the write path re-encodes UTF-8. `{"change":"café-fix"}` was
  appended as `cafÃ©-fix`; `日本` became `æ—¥æœ¬`. Exit 0, success path, ledger path echoed.
  `spec-to-pr-retro` then aggregates the corrupted record.
- **Uncaught traceback.** A UTF-8 byte in cp1252's undefined set decodes to a lone surrogate;
  the later `.encode("utf-8")` raises `UnicodeEncodeError` outside every `try`, breaking the
  module's documented exit-code contract.
- **Output side.** `print(..., file=sys.stderr)` encodes with the ambient locale too. Fixing
  only stdin is half a contract.

`update-cla/scripts/orchestrate.py:28-39` already carries `_force_utf8_stdout()` for exactly
this reason — the pattern is known here, it just was not applied.

### H4. The tests that should have caught H3 passed for the wrong reason `REPORTED`

**From:** market-distiller-mcp

`test_log_run.py` (×2) calls `subprocess.run(..., text=True)` with no `encoding=`, so the
parent encoded with the locale and the script decoded with the same locale — **both sides
agreed on cp1252**. `test_preserves_unicode` and `test_non_ascii_round_trips_utf8` went green
while asserting UTF-8 in their names and testing cp1252 in fact. Setting
`PYTHONIOENCODING=utf-8` desynchronized the pair and failed both instantly.

A test whose result flips on an ambient environment variable is not hermetic.

### H5. `apply.py` — five ways a sync damages or misreports itself `REPORTED`

**From:** agentic-air · **Two of these stopped that sync.** · **Fixes exist there.**

- **(a)** `_write_lock` omits `newline="\n"` while `_write_file` pins it → the committed
  lockfile lands CRLF on Windows, LF elsewhere; a repo pinning `eol=lf` re-dirties it every apply.
- **(b)** `_read_lock` silently discards all prior provenance on a corrupt-but-*present*
  lockfile, downgrading every future `discover` to judgment-only. *Absent* should be the only
  silent case.
- **(c)** `_write_file` is not atomic (unlike `_write_lock` one function below). A failure
  mid-write leaves the asset truncated, recorded as `failure`, kept out of the commit message,
  PR body and lockfile — and then `git add -A` ships it anyway. Related:
  `UnicodeEncodeError` is a `ValueError`, not an `OSError`, so it escaped per-file isolation
  and aborted the run, skipping `_update_lock` and losing provenance for everything already
  written.
- **(d)** The generated PR body exceeds GitHub's 65536-char limit; a 154-asset sync failed
  `gh pr create` **after** commit and push, and the rollback says nothing about the surviving
  remote branch — so it reads as "nothing happened" and a re-run creates a second branch.
- **(e)** `temp/sync-<run-id>/` is never cleaned up, and `apply_pr` opens with a whole-tree
  clean check — so the second `--mode pr` run in any repo refuses to start and blames the
  user. The documented ignore pattern is `temp/sync-state/`, a different path.

**Note from their fix:** do **not** use `shutil.rmtree` for (e) — `temp_dir` is
caller-supplied and their first draft deleted an entire synthetic repo in test. `rmdir` fails
harmlessly. Staging is now explicit (`git add -- <written> <lockfile>`), which is what makes
(c) safe rather than merely recorded.

### H6. `orchestrate.py` under-reports what a run did `REPORTED`

**From:** agentic-air · **Fix exists there.**

- **An asset discovered but omitted from `adaptations.json` is never written and can never
  surface.** The summary's denominator is `len(adaptations)` — self-referential — so the run
  reports "wrote N of N" and exits 0 while the asset keeps its pre-sync content. A live risk
  precisely because Phase 2 is done by an LLM: dropping one file from a 150-entry list is the
  most likely mistake in the whole flow.
- A stale `adaptations.json` from a different run applies wholesale.
- `_print_pr_summary` has no bucket for `skipped_binary` *and* lists it in `known`, so a
  refused binary vanishes from the PR report entirely.

**Their fix:** diff `divergences.json` against the adaptation entries, report `NOT ADAPTED`
on stdout, exit 1 even when other files wrote; refuse a `run_id` mismatch (exit 2); give
`skipped_binary` its own bucket; print `Wrote N of M`. Ships with `SKILL.md`'s exit-code
contract updated in the same change.

### H7. `warn-smoke-test-drift.py` is entirely dead on Windows `REPORTED`

**From:** agentic-air (three defects, one hook)

`file_path` is compared without separator normalization. Edit/Write supply an *absolute*
path, whose native Windows form is backslashed, so a substring test against a POSIX-authored
`src/i18n/` never matches. No edit on that platform reaches the locator comparison.

---

## MEDIUM

### M1. A test helper rounded its own argument, so boundary tests tested nothing `REPORTED`

**From:** agentic-air · **Mine, PR #39.**

`_words(n)` emits `ceil(n / 8) * 8` words. The two parametrized values naming the ratio
boundaries (`340`, `321`) actually wrote 344 and 328 — the boundary was never exercised. A
fixture helper that rounds its own argument makes every threshold test a claim about a number
the file never contained.

### M2. Consumer tokens in synced core `CONFIRMED`

- `skills/update-cla/scripts/discover.py:165` names `agentic-air` literally. **Mine, PR #32.**
- `agents/fact-gatherer.md:63-64` uses `packages/engine` / `packages/design-system` in its
  worked example. Pre-existing. agentic-air **cannot adopt this file** — its guard scans
  `agents/` and would flag its own tokens arriving from upstream.

### M3. The source cannot detect M2 at all `CONFIRMED`

`test_no_project_tokens.py` skips when `project-tokens.local.md` is absent, and it is absent
here deliberately — the guard argues the token-list model "only fits a CONSUMING repo". That
reasoning has a hole: the source does not need to protect its own tokens, it needs to keep
*consumers'* tokens out. Without that list a consumer audit is the only detector, which is why
M2's first item surfaced hours after I wrote it.

### M4. Synced core carries a JS-monorepo shape `PARTIAL`

**From:** market-distiller-mcp. Verified true, and wrong in *this* repo too — logic-artisan has
no `package.json` and `discover_tests.py` returns `[]` here for source-affecting paths.

**Narrower than reported:** the Test phase has a working non-JS path in the same paragraph
(`See cla.io/project-facts.md` for the command set) plus a `--test-cmd` override, so a non-JS
repo is not gate-less — it loses automatic tiering and gets a **wrong status label**.

**Wider than reported:** `lite-pr` and `multi-lite` also reference `discover_tests.py`.

**The actual defect looks like two adjacent sentences contradicting each other** — one asserts
the gates *are* the root package's scripts, the next defers to `project-facts.md`. Downstream,
`discover()` returning `[]` is reported as `skip: docs-/openspec-only change`, a false reason.

**Needs an audit before any code.** A `cla.io/gates.json` convention was proposed and pulled
back — it would land in every consuming repo on three verified facts and a lot of inference.

---

## REJECTED

### R1. `test_no_project_tokens.py` "leaks ~45 tokens"

Not a leak — it is the test **for** the token scanner, so it necessarily contains sample
tokens. `C:/Code/funnel-demo` at line 708 carries an explicit `# path-fixture-ok` marker: the
guard sees it and exempts it deliberately. **Recorded so the next consumer does not re-report it.**

Worth considering separately: the fixtures use *real* consumer names, so every consumer that
audits us re-flags these forever. Synthetic names would kill the recurring noise.

### R2. `test_project_facts_paths.py` leaks `packages/engine`

Same shape — fixture strings inside assertions.

---

## OPEN, not yet assessed

- **O1.** `mechanical-checks.mjs` cannot express a check for a non-JS repo (market-distiller).
- **O2.** Hooks consumers want to contribute up: `validate-commit.py` (staged-content policy
  engine reading rules from `cla.io/project-facts.md`) and `warn-python-encoding.py` exist only
  in claude-plugins, so every sync silently unwires them.
- **O3.** Command-name case folding: `GIT push` / `git.EXE` still unmatched. market-distiller
  pinned it as a CONTRACT test so changing it is deliberate; agentic-air proposes widening.
- **O4.** `warn-lint-on-edit.py` runs `oxlint`, a JS linter, in synced core. Degrades cleanly
  when absent — untidy, not harmful.

---

# The plan

## Principle: pull the fixes, do not re-derive them

Both repos **already wrote and tested** fixes for nearly every finding. `update-cla` supports
the reverse direction — run it here with the consumer as source, scoped per asset. That is
dramatically cheaper and lower-risk than writing them a second time, and this session's record
argues strongly against my writing them a second time.

Two cautions that apply to every pull:

- **Rule 3 in reverse.** A consumer's copy is a re-specialized fork. Pull the *fix*, not their
  repo-specific adaptation around it. Scope every pull to the specific asset.
- **Verify each fix reproduces the defect first**, then that the pulled version resolves it.
  Both consumers supplied reproductions; re-run them here rather than trusting the write-up.

## Batches, in order

**Batch 1 — guards that do not guard.** C1, C2, C3.
Highest severity and mutually independent. Every one is "the guard is off and nothing says so".
C1 and C2 are one-line changes with a shared-constant refactor; C3 is a `hooks.json` edit plus
a real executing probe test. Pull C1/C2 from market-distiller, C3 from agentic-air.

**Batch 2 — the hook I merged today.** H1, H2, M1.
All in `warn-wholesale-rewrite.py` and its tests, all from agentic-air, all one file plus its
test. H1 makes it work in worktrees, which is the common path in this plugin.

**Batch 3 — ledger integrity.** H3, H4.
Four copies of `log_run.py` plus two test files. The drift checker in `consistency-checks/`
must be re-run after, since the four copies must stay byte-identical.

**Batch 4 — the sync engine.** H5, H6.
Largest and most dangerous — `apply.py` and `orchestrate.py` are the highest-blast-radius code
in the plugin. Do it last among the fixes, alone, with the exit-code contract in `SKILL.md`
updated in the same change.

**Batch 5 — hygiene.** M2, M3, H7.
M3 arms an existing guard here for the first time and stops M2 recurring; do them together.

**Deferred, deliberately:** M4 (audit first), O1–O4 (unassessed), and the R1 fixture-renaming
(real but low value, and it touches the file most likely to conflict).

## What this does not fix

The meta-problem. Three of these are mine from this session, and two are in guards whose whole
purpose is to stop an unauthorized action. The pre-ship checks added to `CLAUDE.md` in #39
target exactly that pattern and are unproven. Worth watching whether Batch 1–5 produce a
consumer report of their own.
