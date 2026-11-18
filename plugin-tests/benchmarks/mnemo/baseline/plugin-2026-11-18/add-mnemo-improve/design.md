# Design

Stock triggers: **security** (what a loop PR may touch, and what may leave a domain in an issue) and **real ambiguity** (what a scorecard pass is, which log lines a run reads, how a loop PR is found).

## Context

`mnemo-improve` runs in a domain session, next to the owner's notes and uncommitted captures, and its output goes to GitHub. The requirements are in `specs/`; this file records only the choices a reviewer must agree on.

## Decisions

### A helper script holds every guard

`mnemo-plugin/mnemo/scripts/mnemo_improve.py`, standard library only, with subcommands the skill calls: `start` (schema guard, open-PR and leftover-branch check, stale worktree prune), `signals` (read the log window, skip and count bad lines, drop a candidate that cites no line), `guard` (check a loop branch's diff against the note-body, `sources/`, `attachments/`, Mnemo-copy and `[meta]` rules), `score` (build the question set, tally answers into the scorecard), `open-pr` (render the provenance, run `mnemo_check.py` `links`, `schema` and `secrets` on the branch's changed files, then push the loop branch and open its PR in one step, refusing without a complete scorecard and provenance), `issue-check` (counts-only check) and `issue-file` (search, comment or create, on the stamped target only).
- Why: the skill's prose cannot be tested; each protected outcome needs a guard a unittest can make fail.
- Rejected: new subcommands in `mnemo_check.py`, whose contract and exit statuses belong to `add-check-scripts` and whose callers are hooks.
- Rejected: rules in `SKILL.md` only.

It reuses the base schema and YAML-subset reader that `add-check-scripts` ships, setting `sys.dont_write_bytecode` before that import, and its exit statuses: 0 done, 1 refused (a guard failed, the run names why), 2 cannot run. "Note" means what `add-check-scripts`' note-checks defines.

### The run works outside the session's folder

The loop branch and each scoring side live in temporary git worktrees outside the domain folder, removed when the run ends; `start` prunes any left by a killed run. The session's folder is never checked out, staged or committed by the run.
- Why: the Stop hook's `save` commits the session's folder; a loop edit there would be saved to the owner's branch, and a capture made on a loop branch would be lost from main.
- Rejected: `git checkout -b` in the session folder, even with a stash.

### Finding a loop PR

Loop branches are named `mnemo-improve/<YYYY-MM-DD>-content` or `-meta`. `start` lists PRs in any state and remote branches through the REST API; an open PR whose head has the prefix, or a prefixed branch with no PR ever opened, stops the run. A branch is pushed only once its scorecard is complete, and the PR is opened in the same step.
- Rejected: a label, which Q5 replaced with the `[meta]` title prefix and which no reader needs (proposal Open question 4).

### Which log lines a run reads

Lines whose `date` is on or after the day the newest loop PR (any state) was opened; with no loop PR yet, every line. Files are `_meta/query-log/*.jsonl` read from the session's working tree, uncommitted lines included. Proposal Open question 1.

### Scorecard

- **Answers:** each answer is a fresh recall run, as a subagent told to read only one side's worktree. Recall's log line lands in that worktree and is discarded with it. The restriction is an instruction, not an enforced limit, and recall is not built yet: unit tests tally canned answers, and an owner-run live check covers the rest.
- **Sides:** main is the branch's starting commit, named by hash with the branch head.
- **Expected note:** for a test question, its answering note; for the triggering question and its paraphrases, the note the change edits for that signal; when the change edits no note (a conventions PR), a pass is any answer that is not `not-found` and cites at least one note.
- **Figures:** per question and side, passes out of 3. Per side, the total over all questions, with the lowest and highest of the 3 runs' totals. A side with any failed answer shows "missing" for that question and no total. Proposal Open question 2.
- **Test-set edits:** both sides answer the union of both test sets; added and removed questions are listed apart, so the loop cannot quietly make its exam easier.

### Test set format

Two-level block style, fitting the YAML subset, one block per question:

```
q1:
  q: "What did the March plan decide?"
  note: projects/march-plan.md
```

### Counts-only check

`issue-check` refuses text that holds, ignoring case and runs of spaces: any logged `q` of three or more words; any path of a file in the domain's working tree, tracked or not; any run of 40 or more characters copied from a note. Shorter questions and fragments pass it and rest on the owner's approval. It checks the final approved text, so an edit after approval is checked again.
- Rejected: trusting the approval alone, because counts-only is an owner-only rule the owner asked the loop to enforce.

### REST calls

Every GitHub call is `gh api` (REST) with `GH_PROMPT_DISABLED=1` and a 30-second limit per call. Issue matching: open issues on the target, all pages, title equal after trimming and folding case. Domain PRs are opened the same way. `gh issue` and `gh pr` are never used, because GraphQL is blocked in cloud sessions.

### `mnemo_schema_version`

A top-level key in the base schema, outside its `required` and `optional` lists, starting at `1`, raised by any change that adds a field. Proposal Open question 5.

## Risks / Trade-offs

- [The 40-character rule misses short quoted fragments] → the owner still approves every text; the check is a floor, not the gate.
- [Recall in a worktree behaves differently from recall in the session] → both sides run the same way, so the comparison stays fair.
