# mnemo benchmark for CLA spec writing

A fixed test of how CLA writes OpenSpec changes. The one case is mnemo, a one-user note-taking tool
whose owner's decisions (about 6.6k words) `/cla:multi-spec` once turned into about 20k words of
specs. Principle 7 of `cla.io/decisions/cla-foundation-2026-11-17.md` sets it up: any change to
spec writing or review must pass it before it ships. It lives in `plugin-tests/` and never ships.
Nothing here runs under pytest.

## Contents

- `inputs/`: the mnemo files the spec writer reads (`SOURCE.md` gives the mnemo commit).
- `rubric.md`: the 8 critical outcomes (a-h) and the scoring dimensions.
- `judge-prompt.md`: the blind-judge prompt, verbatim.
- `author-prompts.md`: the prompts for variants A (no guidance) and B (lean brief), verbatim.
- `baseline/`: the real CLA output for the two changes, and `score.md` with the scores.

## The two changes

- `add-check-scripts`: conventions base schema, `mnemo_check.py` (links, schema, deletions, secrets,
  save), unittest harness, version test. Covers architecture Q1, Q4, Q9, Q10, Q12-Q14 and structure
  Q3, Q6, Q7, Q8, Q13, Q14 plus the "Scaffold spec requirements" section.
- `add-mnemo-improve`: the on-demand improve loop, provenance, `[meta]` PRs, targeted scorecard,
  issue filing, deferred metadata. Covers recursive-self-improvement Q1-Q7, Q10 and structure Q14.

## How to run it by hand

1. In a scratch clone of mnemo as it was before any proposals, put the files from `inputs/` at the
   same paths (`cla.io/decisions/`, `cla.io/project-facts.md`, `README.md`). Give the version under
   test the same two scopes the author prompts name, and have it write the two changes.
   - To test today's spec writer, run `/cla:multi-spec` on the three decision files.
   - To test an edited one, run it from the edited plugin (`./cla`).
2. Count the output: `wc -w` over every file of both changes, and `grep -r '### Requirement:'`.
3. Blind it: copy each version's two change folders to `X`, `Y`, `Z` in a random order. Keep the key
   aside. Include variant A's output from the baseline run as a comparison point; only its numbers
   are kept in `baseline/score.md`, so re-author A with `author-prompts.md` if you need the files.
4. Run `judge-prompt.md` on an Opus agent. Take the critical outcomes a-h from its report, and the
   rough invented-item count.
5. Compare with `baseline/score.md` and apply the pass rule. Report failures; do not auto-fix.

A judge's single run is noisy. Re-run only to settle a close call, with the same judge prompt.

## The pass rule

A change to spec writing or review passes only if, judged blind:

- (a) it covers ALL 8 critical outcomes, a to h. The list is fixed; it is not relative to any earlier run.
- (b) its output is smaller than the no-guidance variant A, in total words (12,243) and in requirements (59).
- (c) it has fewer invented items than variant A (about 35, the judge's rough count).

Owner's rule (2026-11-17): for an outcome whose full coverage would contradict a decision, "kept the
decision and raised the conflict as an open question with a proposed fix" counts as passing.

Current baseline to beat: brief v3 (`baseline/brief-v3/`, the brief shipped in
`multi-spec/references/authoring-brief.md`): 8,860 words, 45 requirements, 7 of 8 outcomes. Outcome g
is a known gap: covering it conflicts with the decision "a `[meta]` PR is never batched with content
changes", and no version raised that conflict. Revisit g when the owner settles that decision.

Brief v3 fails rule (a) as written, on outcome g, and shipped under the owner's exception: g is
recorded as a known gap, not passed.

Packaging items that depend on decisions Q11-Q14 are left out of the baseline; see
`baseline/score.md`. No pre-v3 baseline version passes: all three miss h, and the CLA of that day
(before brief v3), which covers a-g, is 20,510 words and 96 requirements.

Variant A's size is 12,243 words everywhere. Its files were not kept, so it cannot be re-counted;
`baseline/brief-v3/score.md` once said 12,235, and now says 12,243 to match the first measurement.
