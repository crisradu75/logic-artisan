# Design

Triggers: security and personal data (what may leave a domain, and what the loop may edit), a new data model (the test set), and real ambiguity (how answers are scored).

## Context

`add-check-scripts` provides `mnemo_check.py` with `save` and the secret patterns; `add-mnemo-setup` writes the stamp file and the domain `CLAUDE.md` exception; recall writes the JSON-lines query log (self-improvement Q8). This skill is the only part of Mnemo that proposes changes to Mnemo.

## Goals / Non-Goals

**Goals:** a run that never edits a note body, never leaks note content, and leaves the owner one merge or one approval per change.

**Non-Goals:** a schedule, cross-domain signals, any write to `mnemo` beyond issues and comments, PR labels.

## Decisions

### Deterministic steps live in one helper script
The body and path guards, the leak filter, the scorecard table and issue matching live in one stdlib script in the skill's own folder; `SKILL.md` calls it, and tests call it directly with a fake `gh`.
- Rejected: prose-only steps. The guards protect note bodies and privacy, so they need tests.

### Work happens in a temporary worktree
The run creates a worktree in the system temp folder for the loop branch `mnemo-improve/<date>-<hhmm>`, and one detached worktree at a freshly fetched `origin/main` for scoring; both are removed at the end, including on failure. The session's own working tree and branch are never switched.
- Rejected: `git switch` in the session's tree. A crash mid-run would leave the owner on the loop branch.

### Loop PRs are found by branch prefix
A loop PR is an open PR whose head branch starts with `mnemo-improve/`. The run lists open PRs through `gh api repos/{owner}/{repo}/pulls?state=open` and stops on any match. PRs are opened through the built-in GitHub tools or `gh api`, never `gh pr` (structure Q5).
- Rejected: a label. Q14 marks PRs by title prefix only, and labels are not added (Open question 2).

### Commits go through `save`
Each change is committed in the loop worktree with `mnemo_check.py save --message "improve: <summary>"`, after the branch is pushed once with an upstream. A failed check drops that change and the run reports it.
- Rejected: plain `git commit`. It would skip the secrets check.

### Body and path guards run before each commit
For every changed note, the text below the frontmatter on the branch must be byte-identical to `main`'s, and only `aliases`, `summary`, `questions` and `links` may differ in the frontmatter. Any change under `sources/`, `attachments/`, `.claude/skills/mnemo-*`, `.claude/mnemo/`, or to `.claude/settings.json`, is dropped from the PR; the last three are turned into an issue draft.
- Rejected: trusting the skill's instructions alone. A byte comparison is cheap and cannot be argued with.

### Test set format
`_meta/tests/questions.yml`, in the schema grammar of `note-checks`: one top-level key per question id, holding `question:` (the text) and `answer:` (the answering note's path, from the repo root). An empty or missing file is an empty test set.
- Rejected: one file per question. The loop and the owner edit the set as one list.

### Scoring
Each answer comes from a fresh subagent that follows recall's search steps against one scoring worktree, with logging off, and returns the paths it cites. An answer is correct when it cites the question's answering note; for the triggering question and its paraphrases, that is the note the change edits. Each figure is "k of 3", and the spread is the three per-run results in order (for example `✓✗✓`). The `main` worktree uses `origin/main` fetched at scoring start.
- Rejected: an LLM judge grading answer text. It adds a second source of variation the scorecard cannot show.
- Rejected: reusing the session's own answers. They saw the change being made.

### Issue filing
The target is the stamp's `repository`. Titles take the form `[mnemo-improve] <cause category>: <rule title>`. The run lists open issues with `gh api repos/{target}/issues?state=open&per_page=100` (paging on), treats an exact title match as a duplicate and posts to `.../issues/{n}/comments`, else posts to `.../issues`. Every `gh api` call has a 60-second limit; a timeout files nothing and reports it.
- Rejected: `gh issue`. It uses GraphQL, which cloud sessions block (decision Noted).

### Leak filter on drafts
A draft is built from a fixed template whose only free text is the rule text. Before it is shown, any span of the rule text matching a logged question (`q`), a note title or a note path is removed, and the whole draft is run through the secret patterns imported from the copied check script; a hit stops filing.
- Rejected: relying on the owner's approval alone. A long draft is easy to approve unread.

## Risks / Trade-offs

- [A paraphrase drifts from the triggering question] → the scorecard lists the paraphrase texts, so the owner sees what was asked.
- [A leftover `mnemo-improve/` branch with no PR] → accepted (proposal, Risks noted); the dated branch name keeps a new run from colliding with it.

## Migration Plan

Ships in `mnemo-plugin/`; domains get it through a `mnemo-setup` refresh PR. The base-schema additions are add-only, so existing notes pass unchanged.
