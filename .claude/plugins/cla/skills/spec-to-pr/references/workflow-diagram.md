# /cla:spec-to-pr workflow diagram

Phase order (Precheck → Propose → Review → Implement → Test → Ship → Revise → Archive → Handoff), post-checks, status glyphs, cap points. The conductor's mental model. Model/effort annotations inline below are a quick-reference only — `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md` is the single source of truth for routing; if the two ever disagree, that file wins.

```
                    $ARGUMENTS
                        │
              ┌─────────┴─────────┐
              │  Mode detection   │
              │  (3 modes)        │
              └─────────┬─────────┘
                        │
              ┌─────────┴─────────┐
              │  Bootstrap perms  │   HALT-on-decline (only)
              │  check_perms.py   │
              └─────────┬─────────┘
                        │
                        ▼
            ┌──────────────────────┐
            │  PROPOSE             │   post-check: openspec validate <name> --strict
            │  Skill(opensp-prop)  │   ✓ clean / ⚠ warnings
            │  (skipped in         │   sub-Opus session → opus Agent escalate-up
            │   existing-change)   │
            └──────────┬───────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │  REVIEW              │   cap: --review-rounds (default 1)
            │  (inline; Agent for  │   ✓ READY / ⚠ FIX FIRST after cap
            │   large changes)     │   sub-Opus + RETHINK-borderline → opus 2nd opinion
            │     ↓                │
            │  APPLY REVIEW FIXES  │   ✓ all-applied / ⚠ partial
            │  (Edit/Write loop)   │
            └──────────┬───────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │  IMPLEMENT           │   post-check: openspec status --change <name> --json
            │  openspec apply      │   ✓ isComplete:true / ⚠ gaps (big change → sonnet delegate)
            └──────────┬───────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │  TEST                │   cap: --test-rounds (default 3)
            │  npm run build       │   ✓ exit 0 / ⚠ failures after cap
            │  + npm run lint      │   ✗ skipped (no source-affecting paths)
            │  (discover by        │   (Playwright smoke = optional/manual)
            │   package.json)      │
            └──────────┬───────────┘
                       │
                       ▼      ─── HALT here in --gate-on-push or --interactive ───
                       │
            ┌──────────┴──────────┐
            │  SHIP               │   collision preflight (collision → skip phase)
            │  rev-parse+ls-remote│
            │       ↓             │
            │  inline git +       │   subject-only commit, single-line PR body
            │  gh pr create       │   post-check: gh pr view --json url state
            │                     │   ✓ OPEN / ⚠ gh failure (skips pr-review)
            └──────────┬──────────┘
                       │
                       ▼
            ┌─────────────────────┐
            │  REVISE             │   cap: --pr-rounds (default 2)
            │  R1 Workflow fan-out│   round 1: sliced per agent (opus/sonnet/haiku)
            │  R2+ Agent direct   │   round 2+: previous-fix diff, one tier down
            │     ↓               │            (bug-hunters exempt from demotion)
            │  APPLY PR FIXES     │   commit as `fix: review round N`
            │     ↓               │   (via git add + git commit)
            │  (push, re-review)  │   ✓ 0 Critical+Important after cap
            └──────────┬──────────┘   ⚠ residue after cap
                       │
                       ▼
            ┌─────────────────────┐
            │  ARCHIVE            │   openspec archive <name> --yes
            │     ↓               │   moves change → archive/, syncs spec
            │  inline commit +    │   commit as `chore: archive <name>`
            │  push + 3-check     │   (commits the already-staged set)
            │  push post-check    │   ✓ archive on PR / ⚠ failure
            └──────────┬──────────┘   (NB: runs while PR still OPEN)
                       │
                       ▼
            ┌─────────────────────┐
            │  HANDOFF            │   inline (synthesized from in-context phase
            │  + edit PR body     │   outcomes)
            │    (gh pr edit,     │   (mirror Issues into PR body — only if any)
            │     only if issues) │   includes routing telemetry in run-log JSONL
            │  + optional         │
            │    `docs: TODO.md`  │   only if Suggestion residue exists
            │    commit + push    │
            └─────────────────────┘

DEVELOPMENT-ONLY BOUNDARY — orchestrator stops here.
The user separately runs:
  gh pr merge <#> --squash --delete-branch
(archive is NO LONGER a user step — it ran in Archive)
```

## Status glyph quick reference

| Glyph | Meaning | When |
|---|---|---|
| ✓ clean | success criterion met | per-phase rule |
| ⚠ proceeded with issues | criterion failed but workflow continued (continue-on-everything) | every other failure |
| ✗ skipped | no work to do | e.g. doc-only change has no tests |
| ✗ aborted | orchestration failure (rare; halt) | only user-decline at gate or bootstrap |

## Cap quick reference

| Loop | Default | Override |
|---|---|---|
| review-change | 1 round | `--review-rounds N` |
| tests | 3 rounds | `--test-rounds N` |
| pr-review | 2 rounds | `--pr-rounds N` |

## Autonomy mode quick reference

| Mode | Halt points |
|---|---|
| `--auto` (default) | bootstrap-decline only |
| `--gate-on-push` | bootstrap-decline + before push/PR |
| `--interactive` | bootstrap-decline + after every phase |
