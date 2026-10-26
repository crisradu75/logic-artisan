# Proposal

## Why

The owner decided (2026-10-26, final) to stop shipping CLA's own `code-reviewer`,
`silent-failure-hunter` and `comment-analyzer` and to rely on the `pr-review-toolkit` ones, which CLA
already requires for `pr-test-analyzer` and `type-design-analyzer`. The copies claimed no token saving
(`openspec/changes/archive/2026-10-12-reviewer-agents/proposal.md`), and a per-call `model` overrides an
agent file's model (`cla.io/decisions/reviewer-agents-live-check-2026-10-12.md`), so the files added
only a read-only tool list.

**Accepted risk, stated plainly.** The toolkit reviewers hold Bash and Edit, and the toolkit's
`code-reviewer` defaults to reviewing `git diff` itself. The brief becomes the only safeguard. Peer
repos recorded the harm: market-distiller-mcp (a `code-reviewer` reverted 7 files) and claude-plugins
(`git checkout --` on about 344 uncommitted lines). The owner chose a prose-only mitigation, so the
rule is specified and tested here.

## What Changes

- Delete the three reviewer agents and their three Copilot copies. `doc-sweeper` and `fact-gatherer`
  and their read-only conformance test stay; the Copilot sync and agreement tests keep covering them.
- Every dispatch of the three reviewers uses `pr-review-toolkit:<name>` and passes `model:` each time
  (the toolkit files name `opus` for `code-reviewer` and `inherit` for the other two). Tiers are
  unchanged: `code-reviewer` sonnet (opus at high risk), `silent-failure-hunter` opus,
  `comment-analyzer` sonnet.
- One sentence, the diff-review rule, goes verbatim into `subagent-brief.md`, `lite-pr` Review and
  `revise.md`: review only the named diff file, run no git command (the state-changing verbs are
  named), edit nothing, and the `line` field's meaning.
- Run-log ledger keys keep the bare names; `log_run.py` and the aggregation are unchanged.
- Docs: both READMEs, `DEVELOPER-GUIDE.md`, `model-routing.md`, `run-log-schema.md` and a `log_run.py`
  comment stop describing CLA reviewers.

## Capabilities

### Modified Capabilities

- `review-agents`: its three requirements about CLA's own reviewer files, diff-file reading and
  sizing names are REMOVED; one requirement on how any reviewer is dispatched is ADDED.

## Impact

- Removing agents is a minor version; the release is a separate step and this change does not bump it.
- New consistency test `test_reviewer_dispatch.py`; the old sizing-names test, its mutation batch and
  the reviewer parts of the conformance test and its batch go.
