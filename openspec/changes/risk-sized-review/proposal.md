## Why

Every PR gets both Opus bug-hunters, and a second round whenever round 1 committed any fix. The batch that prompted the token-diet program spent most of its tokens there and in orchestration (Opus everywhere, long chats, full suites re-run). Review effort should follow the risk of the diff, and orchestration skills should carry the same economy rules.

## What Changes

- The agent judges each PR's risk from its diff and writes one risk line in the PR body: level, reason, reviewers chosen. Generic signals; unsure means high. A prose-dominant diff is high and keeps the Opus `plugin-dev:skill-reviewer`.
- One review-sizing table in `model-routing.md` (low-risk docs, low-risk code, high risk). `spec-to-pr`, `lite-pr`, `multi-pr`, `multi-lite` and `multi-spec` cite it; none copies it.
- Round 2 runs only after a Critical finding was fixed in round 1.
- Every "never demoted" claim that contradicts the table is retired, including the phantom-finding section.
- One new shared reference holds the orchestration rules (explicit `model:` on every dispatch, complete briefs and short reports, tests once on the final commit, one PR at a time per area, handoff file, Opus for high-risk implementers, a one-command debris check). The three chain skills cite it.

## Capabilities

- Modified: `change-workflow` (the requirement for a change becoming a pull request, via REMOVED + ADDED).
- Not in this change: the consumer rules file (Brief 2), which will cite the shared reference created here.

## Impact

`skills/_shared/references/` (`model-routing.md`, one new file, `README.md`), `spec-to-pr` (`SKILL.md`, `references/revise.md`, `references/ship.md`, `references/design-tradeoffs.md`, `references/workflow-diagram.md`), `lite-pr/SKILL.md`, `spec-to-pr-retro` (`SKILL.md`, one script docstring and comment), `multi-pr`, `multi-lite`, `multi-spec` `SKILL.md`, the plugin `README.md`, and the live `change-workflow` spec. Behaviour change for consumers: fewer reviewers and rounds on low-risk PRs. Per `tasks.md`, the version bump is a separate release decision.
