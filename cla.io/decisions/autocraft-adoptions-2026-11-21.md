# Autocraft adoptions — 2026-11-21 (revised)

## Topic

Which ideas from the autocraft "software factory" (github.com/storytold/autocraft) CLA adopts, and in what
form. This revision replaces a first version of this file (uncommitted) after an independent Opus review
found it copied autocraft's mechanisms without the parts that made them safe or worth their cost. The
review measured the typical per-run prose load at 4,690 words for `lite-pr` and 22,074 for `spec-to-pr`
(`plugin-tests/scripts/measure_load.py`).

## Questions and decisions

| Q | Decision | Rationale |
|---|---|---|
| Q1 | In `lite-pr`'s Test phase, before spending the one fix, judge by reading whether a failing test was already failing on the base branch: the failing test and the code it exercises share no file with the change → label it "probably already failing on the base branch: <test>". No extra run, no `git stash`, no second worktree | Saves the fix budget and out-of-scope edits (autocraft `AGENTS.md` rule 36) without touching uncommitted work, which is still in the working tree at this point (`lite-pr/references/diagnose-escalation.md:3`) |
| Q2 | A labelled failure: attended → ask the user whether to ship with `Known failing before this change: <test>, not fixed here` in the PR body; unattended (`/cla:multi-lite`) → halt with the label as the reason | The label is a reading judgement, so a person decides when one is present; nothing ships red unattended (`lite-pr/SKILL.md:121`) |
| Q3 | (A) One consistency test in `plugin-tests/tests/consistency/`, both directions: every script has a row in DEVELOPER-GUIDE §11's script table, and every row names a script that exists. No generator, no header lines | Header lines would be comments nothing executes, so generation would not keep reasons true; some rows run 174-263 words (DEVELOPER-GUIDE.md:619, 617, 635). Zero per-run cost, no new script |
| Q4 | (B) `lite-pr` only, in a reference read only when a test fails: one rerun with no edit when the log shows no failed assertion, compiler or test error and names an unreachable network or service. No timeout trigger. It does not use the one-fix budget and is reported as a suspected flake. The long-log reading rule (over ~4,000 characters: read the first error and the final summary) lives in the same file | A green run pays only for a pointer sentence; `spec-to-pr` already retries infra flakes (`spec-to-pr/references/test-notes.md:5`); a local timeout hits the same wall again (`spec-to-pr/references/implement-delegate.md:27`) |
| Q5 | (C) Dropped: no review-diff exclusion list | Per-run cost in every repo for a rare, unmeasured saving; autocraft's safe version pairs exclusion with a lockfile check (`src/core/lockfiles.ts:1-9`), which would be a new script |
| Q6 | Correction re-dispatches continue the same agent via SendMessage when the tool is available, else a fresh dispatch as today. Covers: a reviewer that returned nothing (`spec-to-pr/references/revise.md:67`), an uncited enumeration (`revise.md:113`), an implementer with unfinished work (`implement-delegate.md:27`). Review rounds after a fix stay fresh | A correction is the same task with one gap named; continuing keeps context and the cached prompt (autocraft `src/prepush/resume.ts:10`). Fresh later rounds keep the review independent. Saving not measured |
| Q7 | Dropped: reviewers do not check diffs against `cla.io/decisions/` | Decision files are ephemeral inputs to the next step, not standing policy |
| Q8 | One duplicate-work search in `lite-pr`'s Plan (`gh pr list --state all --search "<key words>"` plus recent commits on the base branch; no-op without a GitHub remote). Likely match: attended → show it and wait; unattended → continue and name it in the PR body | Catches parallel sessions building the same change (autocraft `AGENTS.md` rule 5); a fuzzy match never halts a batch; a match is reported, never touched |
| Q9 | A `Checks:` line beside `lite-pr`'s `Risk:` line (`lite-pr/SKILL.md:152`): what ran, what was skipped and why, and the Q2, Q4 and Q8 notes | Makes skipped or lighter gates visible (autocraft `AGENTS.md` rule 33) and gives the new notes one home |
| Q10 | Not adopted: tracking which stage missed a post-merge bug | CLA has no post-merge step to surface such bugs, so the count would mostly read zero |

## Noted, not asked

- **Reversibility:** every item is prose or a dev-only test in one revertible commit.
- **Release:** every shipped item is a patch under the root `CLAUDE.md` versioning rule.
- **Build rule (cold check):** everything used only on a red gate goes in the failure-only reference, including Q2's attended/unattended handling and all of Q4. `lite-pr/SKILL.md` gains only the Q1 label sentence, the pointer to that reference, the Q8 search and the Q9 `Checks:` line — estimated ~145 words, about +3% of `lite-pr`'s 4,690-word run (estimate, not measured; measure before and after with `measure_load.py`).
- **Downstream consumers:** Q1, Q2, Q4, Q6, Q8 and Q9 change shipped behaviour in every installing repo — protected under `cla.io/project-facts.md` ("anything shipped to other repos"). Q3 is dev-only. Shipped never/always/must lines need `docs/rule-ledger.md` entries in the same change.
- **Dropped from the first version:** the generator and `Why a script:` header lines, the timeout trigger, the `spec-to-pr` copy of B, and C.
- **Considered earlier and set aside, not reopened:** a protected-files list for fix rounds, treating GitHub text as untrusted data, a single audited GitHub write path, a reviewer "unsure" flag gating escalation, skipping re-review on an unchanged PR head, and autocraft's server machinery (SQLite mirror, embeddings, merge batches, daily caps).

## Final axes

All Clear — Reversibility (Noted), Release (Noted), Smaller option (Q1, Q3, Q4, Q5, Q7, Q10), Per-run cost
(Q4 and the cold-check build rule), Edge cases (Q2, Q6, Q8), Invariants (Q1, Q2), Downstream consumers (Noted).

## Why it matters, and next step

The revised set keeps each adopted idea at the size where it pays for itself: a failing test is first
checked against the base branch, infra blips get one reported rerun on the failure path only, corrections
reuse the agent that holds the context, parallel sessions are less likely to build the same change twice,
and every PR says what was and was not checked.

Build paths (per `cla.io/project-facts.md` Stakes):

- **Q3, the script-table test** — `/cla:lite-pr`: dev-only, nothing ships.
- **Q1, Q2, Q4, Q6, Q8, Q9** — one `/cla:spec-to-pr` change: shipped behaviour in `lite-pr` and the review and implement references, a protected area. Measure `lite-pr`'s load with `measure_load.py` before and after.
