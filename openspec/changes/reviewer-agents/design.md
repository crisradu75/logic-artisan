# Design

Trigger: cross-cutting change, and real ambiguity (three blockers stopped the earlier lite-pr attempt).

## Context

- Reviewers are told to read the hunks themselves with `git diff`: `spec-to-pr/references/revise.md`
  ("Describe the diff; never paste it"), lite-pr `SKILL.md` (Review), and slots 3 and 4 of
  `subagent-brief.md`. Revise round N ≥ 2 instead pastes the fix diff into each prompt. The same
  `revise.md` section says raw diff text breaks the `Workflow` script's template literal.
- Checked against primary sources this session:
  - The Agent tool's schema says its `model` parameter "takes precedence over the agent
    definition's model frontmatter".
  - The `workflow-authoring` reference says `agent()`'s `model` option "overrides the model for this
    agent call" and that `agentType` resolves "from the same registry as the Agent tool". It does not
    say whether that beats frontmatter, or which model an `agentType` call without `model` gets.
    Task 1.1 settles both by running one. Not yet run: verify by running, in the first live review
    round, before relying on the high-risk row's `model: opus` over the file's Sonnet.
  - Both shipped agents set `tools: ["Read", "Grep", "Glob"]`, and the session registers them as
    `cla:fact-gatherer` and `cla:doc-sweeper` with exactly those tools.
- No test under `plugin-tests/` pins an agent's `model` or `tools`.
- `cla-setup` copies the "Review sizing by risk" span of `model-routing.md` into each repo's rules
  file, and two tests pin its rows as written.

## Goals / Non-Goals

**Goals:** read-only reviewers that cannot run git, each model stated once, and the existing ledger
keys kept.

**Non-Goals:** replacing `pr-test-analyzer`, `type-design-analyzer` or `plugin-dev:skill-reviewer`,
and changing the risk call or the tiers.

## Decisions

### 1. The caller writes the diff to a file and passes its path (blocker 1)

Before dispatching, the orchestrator saves `git diff <base>...<branch> -- <paths>`, or the round-N
fix diff, to one file per reviewer scope: in the session scratchpad when one is listed, otherwise a
`mktemp` file, never inside the working tree. The brief names the absolute path beside the file +
symbol + focus-question description. The orchestrator deletes the file when the round ends. A path
is a plain string, so the template literal stays safe.
- Why: read-only agents can still `Read` a file. Only the caller can run git.
- Rejected, giving reviewers Bash: it fails the acceptance and invites `checkout`, `stash` and
  edits while the tree holds uncommitted work.
- Rejected, pasting the diff inline: it breaks `Workflow` scripts and bloats every brief.
- Rejected, a file inside the tree: `git status` shows it, and a `git add` can sweep it in.

### 2. One agent file per reviewer; the high-risk row overrides `code-reviewer`'s model (blocker 2)

- `code-reviewer.md` sets `model: sonnet`, its low-risk tier.
- `silent-failure-hunter.md` sets `model: opus`. It runs only on high risk.
- `comment-analyzer.md` sets `model: sonnet`.

The high-risk row dispatches `cla:code-reviewer` with `model: opus` passed explicitly on each
dispatch, overriding the file's Sonnet. This is the only override left. The user decided this.
- Why: one prompt body cannot drift between copies.
- Rejected, one file per tier (`code-reviewer` on Sonnet and `code-reviewer-high` on Opus): two
  copies of one prompt, which need a test to keep them equal.

### 3. CLA defines three reviewers and writes its own prompts (blocker 3)

CLA defines the three reviewers the sizing table names. The toolkit agents are inherited only as a
focus list: bugs and guideline breaks; swallowed errors and silent fallbacks; comment accuracy and
rot. No toolkit prompt text is copied: a plugin cannot ship another plugin's agents, and copying
raises a licence question. Each prompt states the diff-file input, no shell, report-only output in
the existing `FINDINGS_SCHEMA` shape, and confidence filtering.
- Rejected, mirroring all six Revise agents: the table names only three.
- Rejected, keeping the toolkit agents: they hold Bash and Edit.

### 4. Same bare names, dispatched as `cla:<name>`, files named outside the copied span

Bare names keep the run-log keys and the sizing-table cells unchanged. Dispatch uses the full `cla:`
type, so the names do not collide with `pr-review-toolkit:<name>`. The agent files are named in the
"Routing table" of `model-routing.md`, beside `fact-gatherer`, so the span `cla-setup` copies gains
no plugin path.
- Rejected, new names such as `diff-reviewer`: a ledger migration, and harder comparison with past
  runs.

### 5. One conformance test over all of `agents/`

Every `agents/*.md` must have `name`, `description`, and a `model` of haiku, sonnet or opus. Its
`tools` must be a list that excludes Edit, Write, NotebookEdit and Bash. This covers the existing
two agents too. A mutation batch goes under `plugin-tests/mutants/conformance/`.

## Risks / Trade-offs

- [Reviewers cannot run tests] → Revise already has the orchestrator verify each Critical finding.
- [A large diff file exceeds one `Read`] → The prompt says to page with offset and limit.
- [A diff file is left behind] → Deleted at round end, and never in the tree.
- [New prompts, untested findings] → `routing.revise_findings_by_tier` tracks found versus phantom
  per agent.
