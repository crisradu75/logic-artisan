## Trigger

Cross-cutting change: one rule (the review table and the orchestration economy rules) lands in about eight skills and references. Design fixes where the text lives so the skills cite it rather than copy it.

## Decisions

1. **The review table lives once, in `model-routing.md`; every skill cites it.** One place to change; the file already holds the routing table and is the declared single source.
2. **The risk call is the agent's, per PR, from the diff, recorded as one PR-body line.** No per-repo risk list means no setup, and the line can be audited by grepping PR bodies.
3. **Unsure means high; a prose-dominant diff is high and keeps the Opus `plugin-dev:skill-reviewer`.** Doubt fails safe, and in this plugin prose ships like code.
4. **Round 2 only after a fixed Critical.** Cheapest rule that still re-reviews the fixes most likely to be wrong.
5. **The orchestration rules live in one new shared reference; each chain skill cites it from its existing "run thin" rule.** Brief 2's rules file will cite the same text, so it exists once.
6. **The phantom-finding section is rewritten, not deleted.** It keeps the argument for Opus on high-risk diffs and states that low-risk diffs accept a weaker reviewer.

## Rejected

- A hook that blocks an `Agent` call without `model:`: a forgotten `model:` inherits the session model, which is the default anyway; prose is enough.
- A `--tiny` tier or a size check inside `lite-pr`: the workflow was already chosen, so a size gate changes nothing; risk sizing handles large diffs at review.
- Keeping "never demoted": it contradicts the table and makes every PR pay for both Opus bug-hunters.
- A per-repo risk list: needs setup in every repo and drifts.
- Copying the table into each skill: the copies would drift, as the routing table did before it was made single-source.

## Accepted risk

A diff misjudged as low gets one Sonnet reviewer, and Sonnet also triages findings, so it alone decides whether a Critical exists and round 2 runs. The unsure-means-high rule and the signal list are the only mitigation.
