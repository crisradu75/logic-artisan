# Proposal

## Why

Every PR-review dispatch sets its model per call and borrows `pr-review-toolkit` agents that hold
every tool, Bash and Edit included. Token-diet decision 11, candidate 7
(`cla.io/decisions/token-diet-multi-lite-2026-10-11.md`, "7. reviewer-agents") asks for fixed,
read-only reviewer agents that carry their own model, so the review-sizing table can cite them by
file. No saving is claimed; any cost figure comes from `plugin-tests/scripts/meter.py`.

## What Changes

- Three new agents in `.claude/plugins/cla/agents/`, beside `doc-sweeper` and `fact-gatherer`:
  `code-reviewer`, `silent-failure-hunter` and `comment-analyzer`. Each has `model:` set and a
  `Read`, `Grep`, `Glob` tool list. Their prompts are written for CLA, not copied from the toolkit.
- Reviewers get the diff as a file. The dispatching skill writes `git diff` output to a file outside
  the working tree and names its path in the brief. The rule "tell the agent to read the hunks
  itself with `git diff`" in spec-to-pr's Revise reference, lite-pr's Review step and slots 3 and 4
  of the sub-agent brief, and Revise round 2's pasted fix diff, become "pass the diff file".
- `model-routing.md` names each reviewer by its agent file. The high-risk `code-reviewer` dispatch
  passes `model: opus`, overriding the file's Sonnet (design.md, Decision 2).
- A conformance test pins every shipped agent's frontmatter: `model:` is set, and the tool list holds
  no Edit, Write, NotebookEdit or Bash.
- The README's dependency row says that the three reviewers now ship with CLA. `pr-review-toolkit`
  stays required for `pr-test-analyzer` and `type-design-analyzer`.

Not in scope: `pr-test-analyzer`, `type-design-analyzer` and `plugin-dev:skill-reviewer` keep their
current dispatch. `review-change` and `project-review` dispatches are unchanged.

## Capabilities

### New Capabilities

- `review-agents`: the reviewers the plugin ships, what they can do, how they receive the change,
  and how review sizing names them.

### Modified Capabilities

None. `change-workflow` already holds 8 requirements, and its "A change becomes a risk-reviewed
pull request" requirement does not change.

## Impact

- New: three files in `.claude/plugins/cla/agents/` and one conformance test in
  `plugin-tests/tests/conformance/`, which also needs a mutation batch because conformance tests
  count as checkers.
- Edited: `skills/_shared/references/model-routing.md`, `skills/spec-to-pr/references/revise.md`,
  `skills/spec-to-pr/references/subagent-brief.md`, `skills/lite-pr/SKILL.md`,
  `skills/_shared/references/run-log-schema.md`, a comment in `lib/log_run.py`, the plugin and
  root `README.md`, and `DEVELOPER-GUIDE.md`. One new consistency test and its mutation batch.
- Run-log ledger keys keep the bare names `code-reviewer`, `silent-failure-hunter` and
  `comment-analyzer`, so `routing.revise_findings_by_tier` keeps comparing like with like.
- Minor version bump: the change adds agents.
