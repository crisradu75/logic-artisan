# Harness observations — 2026-08-14

Captured while running the straight-A remediation program end-to-end through the harness
itself (5 stacked PRs, #63–#67, at the time of writing; #68 joined the stack later the same day). These are defects and frictions observed *in the skills*,
not in the work they produced. Triage only — no fixes applied here.

## Defects with evidence

**`doc-sweeper` returned a false-negative sweep.** Asked to grep every
`skills/*/SKILL.md` for retired symbols, it reported zero hits under `skills/`. A direct
grep immediately found real ones: `sync-context/SKILL.md` (6), `cla-init/SKILL.md` (4),
`project-review/SKILL.md:37`, `project-review/scripts/mechanical-checks.mjs:9`. The
orchestrator only caught this because it re-ran the grep by hand. A sweep agent that
under-reports is worse than no sweep — the caller stops looking. Severity: high; this
agent's whole value is exhaustiveness. Worth pinning with a seeded-hit fixture.

**`git_state.py`'s `"clean"` field means "no in-progress git op", not "clean tree".**
`git_state.py:139` is `"clean": in_progress is None`. During Ship it reported
`{"clean": true, ...}` with 47 modified files staged. A model reading that JSON can
reasonably conclude the tree is clean. Rename to `no_in_progress_op`, or add a real
`tree_clean` field.

**`lib/log_run.py`'s docstring cited record counts that were wrong by two orders of
magnitude** ("132 records", "43") against actual 0 and 6. Fixed in this program by making
it count-free, but the lesson generalises: a hardcoded count in a docstring is a fact with
no guard.

**`openspec-propose` instructs the model to use `TodoWrite`**, a tool that does not exist
in this harness (it is `TaskCreate`/`TaskUpdate`). A stale tool reference in a shipped
skill body.

## Frictions

**`spec-to-pr` interpolates the full `$ARGUMENTS` string five times** into its
mode-detection section. With a long invocation that is roughly 1,500 wasted tokens per
load, every run. The detection prose should reference the argument once.

**`project-review`'s five dispatch prompts are consumer-repo-shaped** — they ask about
i18n layers, an allocation engine, multi-tenant isolation — and every `<inject:>`
placeholder is empty in this repo, because the overlay here is a neutral stub. The
orchestrator has to improvise the entire prompt set. A plugin-repo-shaped fallback would
make the source repo's own review turn-key.

**`review-change`'s size gate under-counts a docs-heavy change.** It counts files, tasks,
and capabilities; a change that is 3 files and 40 doc claims grades "small" and skips the
3-agent dispatch. The complexity-concentration override exists for the opposite case
(one file, many decisions). Consider a claim-count dimension.

## What worked, and is worth keeping

- **`mutate.py`'s preflight refused two mutants whose anchors had drifted** rather than
  reporting them killed. That refusal is the whole design working; a lesser tool would
  have reported 5/5 and meant 3/5.
- **`block-cd-in-bash` fired correctly** on a real violation, with a message that named
  the fix.
- **The `run_tests.py` near-miss rule caught a half-deleted scope** — `git rm -r` left
  untracked `__pycache__`/`.pytest_cache` behind, so `tests/` still existed on disk. The
  run failed loudly instead of silently skipping a scope. Worth knowing: `git rm -r` alone
  does not remove a scope.
- **The review agents caught three factual errors the author asserted as measured.** The
  opus-tier bug-hunters earned their tier on every round.
