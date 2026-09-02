# multi-lite run notes — 2026-09-02

Doc: `cla.io/decisions/open-issues-lane1-2026-09-02.md`
Base: `main` @ `b1bcd93`
Plan confirmed: run all three, A → B → C. No dependency edges — nothing is merged, all PRs left open.
Post-chain: the decisions doc + this ledger land on their own branch as a fourth PR.

| id | issue | status | branch | pr_number |
|---|---|---|---|---|
| killed-mutant-not-a-pass | #193 | open (clean, left for user) | docs/killed-mutant-not-a-pass | 194 |
| label-skill-invocation-model | #180 | open (clean, left for user) | docs/label-skill-invocation-model | 195 |
| end-check-label-collision | #177 | open (clean, left for user) | chore/end-check-label-collision-class | 196 |

## Notes

- Phase 0: permissions complete (0 missing), `git_state.py` exit 0, on `main` up to date, pre-push hook installed.
- C carries an ordering constraint: `mutate.py` on `mutants/consistency/test_check_labels_agree.py` must not overlap its own review agents.

## Candidate A — killed-mutant-not-a-pass (#193)

- Commit `fc499e0`, branch `docs/killed-mutant-not-a-pass`, PR #194. 5 files, +68/-2.
- Scope grew by one file beyond the issue: `lite-pr/SKILL.md:154` carries the mutation gate
  verbatim and the issue named only two sites. Left unedited it would brief its reader against
  the old two-outcome contract.
- Issue location corrected: the mirror belongs in `spec-to-pr/references/revise.md`, not
  `SKILL.md`. `grep -rn 'confirm it FAILS'` returns revise.md only.
- Spec touched because two live requirements bind this text (Review-fix evidence gate,
  Planting doctrine). 3 scenarios added. `openspec validate --specs --strict` passes.
- Gates: conformance+consistency 313 passed, skills/spec-to-pr 54 passed, token scanner 0
  violations. No test added — see PR body for why.
- Review: `code-reviewer` + `comment-analyzer` dispatched in parallel, read-only, both told
  not to run `mutate.py` (it rewrites files in place and the other agent would misread the tree).

### Candidate A review outcome

Two agents, one pass. Both independently found the same two structural defects.

Applied (no deferrals at Critical/Important):
- Section preamble + closing enumeration still framed the section as did-it-land, the framing
  the new rule declares insufficient. Both agents. Fixed, incl. the "last two entries" recount.
- `CLAUDE.md` said the defect "survived" 5 lines above the SURVIVOR paragraph; the mutant was
  killed. Term inversion. Fixed.
- Supremacy claim ("the trap that survives every check") contradicted by the issue's own
  account. Removed.
- Both mirrors had drifted apart (byte-identical before fc499e0). Normalized.
- The new spec SHALL had no mechanism. Added `test_mutation_gate_sites_agree.py` + its mutant
  batch (5/5 killed). Discovery is derived, so a third site is demanded when it appears.
- `mutate.py` docstring now states a kill is not a pass — where the belief is formed.

Deferred with reasons: 25-word ceiling on the mirrors is house pattern not a regression;
the "highest risk" ranking is n=1 and left attributed to the issue; the heading
cross-reference from 3 files has no guard, which belongs with #177's marker-discovery work.

Fix commit `6d34558`: 235 insertions vs the reviewed commit's 68. UNREVIEWED.

Pre-existing failure found, NOT caused by this branch: 9 tests in
`plugin-tests/tests/hooks/test_log_commit_provenance.py` fail with
`FileNotFoundError: 'python'` (only python3 on PATH). Confirmed identical at b1bcd93.

## Candidate B — label-skill-invocation-model (#180)

- Branch `docs/label-skill-invocation-model`, PR #195. 3 files.
- Measurement reproduced before writing: 20 skills with a SKILL.md, 2 set
  `disable-model-invocation: true` (multi-lite, multi-pr). Table is 22 rows — the 2 extra are
  `opsx:explore` (vendored) and `(agents)` (dispatched, not invoked), both marked n/a.
- No spec change: grep for phase table / life cycle / invocation model / disable-model-invocation
  in spec.md returns nothing. Recorded as a Measured-by trailer rather than asserted.
- Guard added to the existing `test_doc_facts.py` rather than a new file, so no new mutant batch
  was needed — the existing batch was extended instead (11 mutants, all killed).
- Compared as a SET not a count: a count agrees whenever the right NUMBER of rows are marked,
  including when the marks sit on the wrong skills.
- The guard failed on first run and the failure was the guard's, not the table's: `found` doubled
  as the past-the-opening-delimiter signal, so every file after the first match broke on its own
  opening `---` and went unread. Fixed per-file; that bug is mutant 11.
- Mutant 11's FIRST form died of UnboundLocalError — a crash reported as a kill. Rewritten to
  restore the real accumulator logic so it fails on detection. Verified by hand: the assertion
  now names the wrong derived set. This is candidate A's own rule catching a defect in candidate B.

### Candidate B review outcome

Two agents. The guard I wrote was materially weaker than it read, and its 11-mutant batch
passed while missing all of it. Applied, no unresolved Critical/Important:

- CRITICAL: frontmatter matcher accepted 1 of 6 legal YAML spellings; the inline-comment form
  is the likely one and fails SILENTLY (both sets stay at 2). Now reuses the repo's existing
  `test_skill_lint.parse_frontmatter` rather than a second hand-rolled parser.
- The guard never read the column it guards (`mark in line`, not `in cells[3]`).
- Only the 2 marks were asserted; the other 22 cells had no assertion.
- The non-vacuity test had never been shown able to fail; helpers now take a root param and
  4 tests feed them synthetic trees.
- Floor was 1 against a population of 2.
- Mutant 11's anchor was multi-line -> `mutate.py` refuses on CRLF -> ALL 15 mutants silently
  disarmed on Windows. No CI here, so that would never have surfaced.
- README:42 and CLAUDE.md:394 both asserted the opposite of the new column.

The relabel mutant SURVIVED the first fix round and forced a further assertion (`n/a` was a
way to opt a real skill out of the column). Final: 15/15 killed.

Deferred: multi-lite/multi-pr `description:` fields still say "or natural language like…",
contradicting the column. Frontmatter edits are out of scope per #180. Worth its own issue.

Fix commit `12a7abd`. UNREVIEWED.

## Candidate C — end-check-label-collision (#177)

- Branch `chore/end-check-label-collision-class`, commit `f3735db`, PR #196. 3 files.
- 0m -> B1. B1 verified free before the edit. The parenthetical was rewritten to explain the
  prefix rather than re-tell the 0j history, keeping the 0a-0l range the marked-line rule needs.
- The issue named ONE thing the rename would break (the mutant batch anchor). There was a
  SECOND: the guard's own `_REQUIRED_MARKED_LINES` anchors on "not `0j`:", which the rewrite
  removed. The guard caught it itself and named the line to re-anchor on.
- Discovery by marker replaced the 4-path hand list. Two corrections discovery alone would have
  got wrong: it would have DROPPED the 2 unmarked entry points (narrowing while appearing to
  widen), and it would have silently started policing fact-gatherer.md.
- Ordering constraint honoured: mutate.py ran BEFORE the review agents were dispatched, never
  overlapping. 12/12 killed, tree restored, no leftover backups.

## Run-level note

`mutate.py` was run three times across this chain, each time with no agent reading the tree.
The CLAUDE.md rule against overlapping them held throughout.

### Candidate C review outcome

Two agents. The code was right; the tests defending it were not. Every finding measured
against an isolated copy, then re-measured after the fix.

| defect | before fix | after fix |
|---|---|---|
| structural entry points emptied | 18 passed | 1 failed |
| production scanner gutted | 24 passed | 2 failed |
| scan root narrowed to skills/ | 24 passed | 1 failed |
| exemption dict emptied | 24 passed | rule, not filter — recorded unkillable |

- The synthetic-tree test re-implemented the scan inline and never called production. Fixed by
  the ROOT PARAMETER — the same pattern used correctly in candidate B and not carried into C.
- `_STRUCTURAL_ENTRY_POINTS` unguarded was the exact "narrowed while appearing to widen"
  failure C's own commit message claimed to have handled. Handled in code, undefended in tests.
- I reintroduced a multi-line mutant anchor here, the same defect a reviewer found on
  candidate B. Caught before running this time.
- One mutant deliberately not installed: widening the frontmatter scan to the body survives and
  cannot do otherwise. Mutated the INPUT instead per CLAUDE.md — moving the range out of
  frontmatter fails the rule (1 failed, 25 passed), so the distinction is load-bearing.

Fix commit `bdeccff`. UNREVIEWED.

## Chain summary

3 candidates, 3 PRs, 0 merges (no dependency edges — all left open for the user).
6 review agents across 3 candidates; every candidate's review found real defects in the
tests rather than the code, and in two of three the guard was weaker than its own commit
message claimed.

Every fix round is UNREVIEWED — that is lite-pr's stated one-pass boundary, not an oversight.

| candidate | reviewed | fix | ratio |
|---|---|---|---|
| A #194 | 68 ins | 235 ins | 3.5x |
| B #195 | 164 ins | 318 ins | 1.9x |
| C #196 | 156 ins | 179 ins | 1.1x |

Pre-existing, NOT from this chain: 9 failures in
`plugin-tests/tests/hooks/test_log_commit_provenance.py`, `FileNotFoundError: 'python'`
(the hook shells out to `python`; only `python3` is on PATH). Confirmed identical at b1bcd93.
Worth its own issue.
