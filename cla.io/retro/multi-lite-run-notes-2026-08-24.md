# multi-lite run notes — 2026-08-24

Source doc: `cla.io/decisions/open-issues-2026-08-24.md` (Lane 1 of the eight-item open-issue plan).
Base branch: `main`, primary clone, started at `66969df`.
Plan confirmed: yes — all four candidates as derived, document order, **zero merges** (no candidate
depends on another, so every PR is left open for the user).

| id | status | branch | pr_number |
| --- | --- | --- | --- |
| `mutation-batch-adoption` | open (clean, 1 enforcement round) | `fix/mutants-area-adoption-and-path-check` | 147 |
| `guard-operating-point` | open (clean, 1 enforcement round) | `docs/alarm-operating-point` | 148 |
| `phase1-non-source-edges` | open (clean, 1 enforcement round) | `fix/phase1-non-source-edges` | 149 |
| `live-spec-validate` | open (clean, 1 enforcement round) | `fix/validate-live-spec-set` | 150 |

## Candidates as dispatched

1. **`mutation-batch-adoption`** (closes #138, #139) — in
   `plugin-tests/tests/consistency/test_guards_have_mutant_batches.py`: let a mutants area be
   adopted one guard at a time instead of demanding a batch for every guard in it at once
   (`_guard_areas()`, :30), and narrow `test_no_batch_hardcodes_an_absolute_path` (:229) from bare
   `:\` to a drive-letter shape so a regex like `(?:\s` is not flagged as a Windows path. Dev tree
   only — ships nothing to a consuming repo.
2. **`guard-operating-point`** (closes #143) — add a lens to
   `.claude/plugins/cla/skills/_shared/references/test-quality.md`: any new alarm, threshold or
   minimum-sample precondition states the volume it will see in ordinary steady-state operation.
   Prose only; this file ships, so no dev-tree tooling may be named.
3. **`phase1-non-source-edges`** (closes #142, #99) — in
   `.claude/plugins/cla/skills/multi-pr/references/discover-and-gate.md`: Phase 1 records two edges
   beyond `depends_on` — shared mutable environment state (a migration/seed/provisioning step forces
   merge-before-next), and capability overlap (a capability touched by >1 in-scope change forces a
   re-base check before that change's review).
4. **`live-spec-validate`** (closes #144) — run `openspec validate --specs --strict` where the live
   spec set has just been written: `spec-to-pr/references/archive.md` and `multi-pr`'s per-change
   close-out in `references/change-loop.md`. Verified present in openspec 1.5.0 before dispatch.

## Outcome

All four shipped as open PRs. **Zero merges** — no candidate depended on another, so the
confirmed plan authorised none, and every PR is left for the user.

**Every one of the four needed an enforcement round**, and the plan predicted none. Candidate 1
needed a design rebuild, not a patch: a mutant that turned its mechanism into the blanket exemption
its own comment denied being passed all five tests written for it.

What the review rounds actually caught, by class:

| class | instances | example |
|---|---|---|
| a claim the repo's own files deny | 4 | "`/cla:multi-spec` authors a batch in parallel" — its SKILL.md says "never parallel", in bold |
| a record with no reader | 2 | a re-base finding written to a "sequence table" that does not exist |
| the check absent from the site it named | 2 | `lite-pr` edits live specs with no delta and no archive; candidate 4's own requirement claimed to cover exactly that |
| a check that passes vacuously | 2 | `openspec validate --specs` returns rc=0 `No items found to validate.` |
| tests that cannot distinguish the fix from its opposite | 1 | candidate 1's five tests, all passing under the M1 mutant |
| self-contradiction within one commit | 1 | candidate 4's prose placed one incident on both sides of the archive |

**The plan's Lane 1 classification was wrong.** `open-issues-2026-08-24.md` called all four
"mechanical — the change is knowable from the issue". For candidate 1 that was flatly untrue: issue
#138 said "possible directions, not a prescription", which is a design question, and it was read as
a specification. The Lane 1/Lane 2 split needs a sharper test than "does the issue name a fix" —
the question is whether the issue names a fix *or a direction*.

**One correction propagated forward, which is the thing chains usually fail at.** Candidate 2's
review caught "Measured:" claiming a consuming repo's numbers as this change's own. The same slip
was made in candidate 3 and caught at Ship, before any reviewer saw it, and candidate 4 was written
with the attribution from the start.

## Cross-PR collisions, for whoever merges

| file | PRs |
|---|---|
| `multi-pr/references/change-loop.md` | #149 (step 2), #150 (step 4b) |
| `multi-pr/SKILL.md` | #149 (~30/64/82), #150 (~78) — closest pair |
| `openspec/specs/cla-plugin/spec.md` | #148, #149, #150 |

Hunks were kept apart deliberately. Whichever lands second may need a rebase.

## Notes

- Working tree at start carried two untracked retro ledgers (`commit-provenance.jsonl`,
  `right-model-runs.jsonl`), unrelated to this run. `git_state.py` exited 0. Every stage is
  path-scoped, so neither is ever swept in.
