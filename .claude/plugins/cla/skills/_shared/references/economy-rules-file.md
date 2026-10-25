# Economy rules

Tokens are money. These rules keep an agent's cost down without dropping quality. They apply to any
agent working in this repo, inside a skill or not. The setup step that wrote this file (`/cla:cla-setup`) replaces it
on every run, so edit nothing here: a change belongs in the repo's own instruction file (`CLAUDE.md` or `AGENTS.md`).

## Model by task

Pass an explicit `model:` on every dispatch, and pick it by the task.

- **A cheap model (Haiku):** sweeps and mechanical work. That means doc sweeps, renames, version
  bumps, greps and inventories, and issue comments drafted from text already in hand.
- **Sonnet:** the default for authoring, implementing a decided fix, writing and strengthening
  tests, applying review findings, and small fix PRs. Implementing a high-risk task is the
  exception: it goes to Opus.
- **Opus:** only where judgement carries real risk. That means the independent review of a
  high-risk batch (the review-sizing table below sets each review's model), implementing a
  high-risk task, money logic, writes to files a user owns, and score or gate changes, plus one
  focused re-check when a fix round adds production code in those areas.

## Quality floor

Never cut these to save tokens.

- A claim about existing code cites a file and line read in this session.
- Protected rules (money, security, personal data, honesty claims, accessibility) are never dropped in a rewrite.
- Real-file check: every reader or parser a change touches is also run read-only on copies of real
  input files, never writing to a user's folders. Fixtures copy the real layout with personal data
  redacted.
- Real fixture first: capture a real response or input file before setting a threshold or marking
  a field optional. An inferred rule can fire on every healthy record.
- Mirror-model contract tests (a local model copied from an external schema) run one way: a field that is optional upstream must be optional in
  the local mirror, list elements and `X | None` included. Never strip optionality from both sides
  before comparing.
- Debris check: after the final test run, nothing the tests created remains outside the test
  framework's temp directory. The debris rule below gives the command. A test that writes there is
  fixed in the same change.
- A score- or gate-moving change ships only after the owner approves a before/after comparison on
  real inputs.
- A change that claims not to move a score, ranking or gate proves it: run the old and new code on
  the same inputs, including NaN, infinite and null ones, and compare the results.
- A refactor of code that writes user files carries a byte-identical proof: extract the base
  revision with `git archive`, run old and new code on identical copies of the fixtures, and assert
  the same output bytes and exit codes.
- When the work lands, remove merged worktrees, scratch copies of real files and temp debris, after
  one yes/no from the owner.

<!-- include: cost-rules -->

<!-- include: review-sizing -->
