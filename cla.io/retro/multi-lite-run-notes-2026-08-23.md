# multi-lite run notes — 2026-08-23

Source doc: `cla.io/decisions/open-issues-p1-p3-2026-08-23.md` (Lane 1 of the P1–P3 open-issue batch).
**Deleted 2026-08-24 and NOT recoverable — that doc was never committed.** Its Lane 1 candidates
all shipped (PRs #134, #135, #136, #140, #141); its Lane 2 grouping was carried forward into
`cla.io/decisions/open-issues-2026-08-24.md`, which supersedes it.
Base branch: `main`, primary clone, started at `84d12a1`.

Phase 1 confirmed: run all five candidates as derived. `chain-obligation-carry` **stacks on
`chain-never-ends-idle`'s branch** rather than merging it first — the dependency is a file collision
in `multi-pr/SKILL.md`'s hoisted block, not a code dependency, and the user chose to keep every PR
open for review. **No merges happen in this run.**

Task tracking: `TaskCreate` is unavailable in this session, so this ledger is the sole tracker.

## Candidates

| id | status | branch | pr_number |
|---|---|---|---|
| `chain-never-ends-idle` | open (clean, reviewed) | `fix/chain-turn-liveness` | 134 |
| `branch-delete-ask-hook` | open (clean, reviewed) | `fix/ask-on-force-branch-delete` | 135 |
| `completeness-gate-reads-claims` | pending | — | — |
| `prove-a-gate-traps` | pending | — | — |
| `chain-obligation-carry` | pending | — | — |
| `consistency-scope-import` | pending (added mid-run) | — | — |

## Unattended mandate (user left the session; answers given explicitly)

1. **Scope: finish Lane 1, then STOP.** Amend #136, then candidates 4, 5, 6. Do not start Lane 2 —
   it needs `/cla:multi-pr`, which is `disable-model-invocation: true` and cannot be invoked here.
2. **Merge authority: standing, for any PR that passes.** Use `ALLOW_PR_MERGE=1` prefixed on the
   merge command only — never exported, never `ALLOW_DESTRUCTIVE_GIT`. "Passes" means ALL of:
   every dispatched reviewer returned; zero unresolved Critical/Important; `pytest plugin-tests`
   green on that branch; `node --test` green; push verified against `git ls-remote`. Any one of
   those missing → do not merge, leave the PR open, say so.
3. **On a Critical: fix it, however long it takes.** Do not withdraw a sub-change the way #136's
   part (a) was withdrawn. **Reading of the tension:** #136's strip-(a) decision was answered
   specifically and stands; the fix-it-anyway policy governs NEW Criticals in candidates 4–6.
4. **Candidate 4 scope: the gate traps AND the five-checks work.** Extend `test-quality.md` with
   #114/#116/#122's three planting traps plus the two mutation-scope rules, file the two
   mutation-tooling defects — and additionally address why CLAUDE.md's checks 1, 3 and 5 did not
   fire today, since all three serious defects of this run were cases where the check existed, was
   specific, and was not run.

**Never without asking:** cut or move a release tag, push to `main`, force-push, touch the
consuming repo. **Avoid:** `git branch -D` for local cleanup — it now trips this run's own new
ask-hook and would hang an unattended turn. Use `-d`, or leave local branches alone.

**Merge-order consequence:** once #134 merges, #136 needs a rebase — both insert a requirement at
the same anchor in `openspec/specs/cla-plugin/spec.md`, immediately before
`### Requirement: Shipped-asset boundary`. Adjacent-insertion conflict, resolve by keeping both.
Candidate 5 then branches off `main` rather than stacking on #134.

## Notes

**Candidate 6 added mid-run, user-approved.** `python -m pytest plugin-tests/tests/consistency/`
is 1-failed on `main`: `test_overlays_are_reachable.py:51` imports the staleness guard from
`.claude/plugins/cla/conformance-checks/tests`, a directory PR #131 deleted. The module now lives at
`plugin-tests/tests/conformance/test_project_facts_paths.py`. The full-scope gate
(`pytest plugin-tests`) is green only because pytest has already imported a module of that name from
the conformance area — so the guard resolves by luck, not by the path it names. CLAUDE.md's
documented shipping gate passes; its documented edit loop (`pytest plugin-tests/tests/<area>`) does
not. Fix: repoint the import and make it resolve by path, plus a mutant proving it fails when the
path is wrong. Runs last, own PR.

**Agent dispatch authorized** by the user as standing for all candidates in this run, after the
session's default "no Agent tool unless requested" instruction blocked `lite-pr`'s Review phase.

### Candidate 1 — `chain-never-ends-idle`

- PR #134, branch `fix/chain-turn-liveness`. Closes #130, #101.
- Gates: `pytest plugin-tests` 1158 passed / 1 skipped; `node --test` 70 pass / 0 fail.
- Mutation: 5/5 killed — but only after two corrections worth carrying:
  1. The batch first targeted the whole `tests/consistency/` area, which is unconditionally
     1-failed, so all five reported "killed" on an unrelated failure. Re-scoped to the single test
     file. This is exactly the failure mode issue #116 catalogues.
  2. Re-scoped, mutant 5 SURVIVED: it tried to delete multi-pr's no-pause promise, but that phrase
     occurs twice in the file and `mutate.py` replaces one occurrence, so the mutation never landed
     on the value under test. Re-aimed at the guard's own derivation key.
- Review: 5 agents dispatched (code-reviewer, pr-test-analyzer, silent-failure-hunter,
  comment-analyzer, plugin-dev:skill-reviewer). Pending.
