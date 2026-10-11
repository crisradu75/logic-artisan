# Token diet — multi-lite candidates (2026-10-11)

Source: `cla.io/decisions/token-diet-program-2026-10-11.md` (decisions final). Spec-bound items 2 and
5 are NOT here: they are in `token-diet-spec-to-pr-briefs-2026-10-11.md` (decision 12) and are
out of scope for multi-lite. Next step for every item below: `/cla:lite-pr`. None moves shared
environment state (all edit files in this repo; no migration, seed or provisioning).

**Order and dependencies.** Candidates run in the order listed. Dependencies that are real:
- Everything depends on `meter` (baseline first, decision 7 and "Open before execution").
- `sonnet-launcher` depends on `meter` (it needs a before number) and on the spec-to-pr brief 2
  having landed, since that brief writes the dispatch rule the launcher change relies on.
- `caps-and-tasks` edits `cla-setup/SKILL.md`, which brief 2 also edits: land brief 2 first.
- `lite-pr-lazy-load` edits `lite-pr/SKILL.md`, which brief 1 also edits (the never-demoted review
  wording, `lite-pr/SKILL.md:148`): land brief 1 first.
- `commands-first` edits `spec-to-pr` and chain prose that brief 1 also touches: land brief 1 first.
- `reviewer-agents` edits `model-routing.md`, which brief 1 rewrites: land brief 1 first.
- `lessons-archive` and `local-path-skip` have no dependency beyond `meter`.
- `review-sizing-followups` edits files brief 1 rewrote: brief 1 has landed (PR #324).
- `docs-refresh` runs last, after every other candidate and brief 2.
Merge policy suggestion: `merge-each-clean`, so each candidate's tests run on the combined tree.

## Candidates

### 1. meter — dev-only transcript meter (decision 7)
Add a script in `plugin-tests/scripts/` (beside `measure_load.py`, whose docstring at `:1-5` states
the "run before and after" purpose) that reads per-message `usage` (model, input, cache-read,
cache-write, output tokens) from Claude Code session transcripts, main chat and `subagents/`
files, and prints totals split by model. Nothing ships; register it in the DEVELOPER-GUIDE §11
script table with its one-line reason, per `CLAUDE.md` "Where things go".
Acceptance: run against a copy of one real transcript folder, it prints a per-model table whose
totals equal a manual sum over the same file; it writes nothing outside the output it prints, and
it exits non-zero with a clear message when the transcript lacks `usage` fields.

### 2. sonnet-launcher — Sonnet default session, escalate-up verified (decision 6)
depends_on: meter, spec-to-pr brief 2.
First, in a Sonnet session, show that the escalate-up rule fires: a Propose run dispatches authoring
to an Opus agent, and a FIX FIRST/RETHINK-borderline review is seconded by Opus
(`model-routing.md:115-129`), recording the observed dispatches. Then make the `cla` launcher start
on Sonnet (`cla:34`, `cla.cmd:39` pass `--model opus` today; the echo lines `cla:33`, `cla.cmd:38` repeat it) and say so in CLAUDE.md's
session-start bullet. If escalate-up does not fire, stop and report; change nothing.
Acceptance: `./cla` and `cla.cmd` print a command containing `--model sonnet`; a recorded Sonnet
session shows the two Opus dispatches; the meter shows main-chat tokens by model before and after.

### 3. caps-and-tasks — artifact caps and behaviour-stated tasks (decision 10)
depends_on: spec-to-pr brief 2.
Authoring rules say a task is at most about 40 words, a design about 800, a proposal about 400, and
each task states one behaviour with a testable acceptance criterion and no file:line. Put them in
the rules `cla-setup` seeds (`cla-setup/SKILL.md:128-`) and `openspec/config.yaml` (`rules.tasks`
at `:27-`) in one commit, so `test_cla_setup_rules_match_config.py` stays green. In the
`review-change` checklist, the line-drift check (`checklist.md:50`) becomes a finding "a task names
a line", and over-cap artifacts are findings. An optional out-of-scope note per task is allowed.
Acceptance: a tasks.md with a 60-word task or a `file.py:12` reference gets a finding from the
checklist; the consistency test passes.

### 4. lite-pr-lazy-load — lazy-load three lite-pr blocks (decision 8)
depends_on: spec-to-pr brief 1.
In `lite-pr/SKILL.md`, replace the `Measured-by:` rules (`:127-134`), the mutation gate
(`:157-181`) and the `/cla:diagnose` escalation (`:98`) with one-line triggers that read the moved
text from a reference file when the trigger applies. Move every rule verbatim; add none, drop none.
Acceptance: `measure_load.py` shows `lite-pr` SKILL.md words fall and reachable words stay equal
(its documented evidence of no loss); `test_mutation_gate_sites_agree.py` passes; a diff of
old against new shows only moves.

### 5. commands-first — mechanical phases (decision 9)
depends_on: spec-to-pr brief 1.
For each mechanical phase of `spec-to-pr` and the chains (CI wait, merge, archive), state the
command to run (for example `gh pr checks --watch`, `gh pr merge --match-head-commit`,
`openspec archive`) in place of prose steps. Add a script only where a command plus one sentence
fails, and cite the failure in the script table entry.
Acceptance: each rewritten phase names one command and its expected outcome; no new script lacks a
cited failure; `measure_load.py` `spec-to-pr` typical-run words do not rise.

### 6. lessons-archive — archive old lessons-log entries (decision 11)
Move older entries of `cla.io/lessons-learned/lessons-learned.md` (13,016 words per `wc -w`, with
newest-first entries per `codify-learnings/SKILL.md:96`) to an archive file in the same folder,
keeping the newest entries and the title. `codify-learnings` still greps the log
(`SKILL.md:38-40`), so it must also search the archive.
Acceptance: `wc -w` on the live log falls by at least half; entry count live plus archive equals the
original; a grep for an archived entry's keyword is found by the documented search step.

### 7. reviewer-agents — fixed read-only reviewer agents (decision 11, #296 item 3b)
depends_on: spec-to-pr brief 1.
Add plugin agent definitions for the reviewers the new table names, each with `model:` set and
read-only tools, beside the two existing agents (`doc-sweeper`, `fact-gatherer` in
`.claude/plugins/cla/agents/`). The table cites them instead of per-dispatch overrides.
Acceptance: each new agent file has `model:` and a tool list without Edit/Write/Bash; the
conformance tests for agents pass; `model-routing.md` names each by file.

### 8. local-path-skip — fact-path check ignores machine-local paths (decision 11)
In `cla-setup/scripts/check_fact_paths.py`, `_keep_if_path` (`:358`) has no rule for machine-local
files such as `*.local.*`; a path naming one is skipped, not reported missing.
Acceptance: a project-facts file naming `.claude/settings.local.json` that is absent exits 0; an
absent ordinary path still exits 1; run the mutation batch for this checker once after the fix.
Same checker, same PR: `_keep_if_path` (`:381-383`) skips any path whose first segment is not a
tracked top-level name, so when a top-level directory is renamed, every path under its old name
goes unreported. That falls short of "every repo path" in `repo-context` ("Checking recorded
paths"). Report such a path as stale instead; the pinning tests in
`plugin-tests/tests/conformance/test_project_facts_paths.py` (unknown top-level, repo-derived
top-level set, untracked top-level, skip reasons) change with it.
Added acceptance: a facts file naming `old/src/x.ts` after `old/` was renamed exits 1.

### 9. review-sizing-followups — PR #324 review residue (risk-sized-review)
depends_on: spec-to-pr brief 1 (landed as PR #324).
Five small prose fixes left from the risk-sized-review review rounds:
- `_shared/references/orchestration-economy.md` debris check: ignore interpreter caches
  (`__pycache__/*.pyc`) in the before/after diff, and delete half-written `*.pyc.<pid>` files
  that parallel workers leave.
- `spec-to-pr/references/revise.md`: repeat the resume fail-safe (a resumed run that cannot tell
  whether the previous round fixed a Critical runs the next round) at the exit gate.
- `spec-to-pr/references/handoff.md` §2: the one-line body rewrite keeps the original one-liner
  verbatim, so a stacked child keeps its "Stacked on #N." clause.
- `_shared/references/model-routing.md` (rubric-checks paragraph) and the plugin `README.md`
  skill-reviewer row: cite "Review sizing by risk" instead of restating skill-reviewer's model.
- `model-routing.md`: give "as `revise.md` describes" its plugin-root path; split the new
  sentences in `model-routing.md`, `revise.md` round-1 selection and `lite-pr` Review that run
  past 25 words.
Acceptance: `test_review_sizing_single_source.py` and its mutation batch still pass; a debris
check on a clean run reports nothing.

### 10. docs-refresh — repo docs match the program's end state (runs last)
depends_on: every candidate above, and spec-to-pr brief 2.
Update the repo's own docs for what the token-diet program changed: `README.md`,
`DEVELOPER-GUIDE.md` (the developer guide, including §11 layout and script table) and root
`CLAUDE.md` (rules and the release line only if a release landed). Cover: risk-sized review and
the PR `Risk:` line, `orchestration-economy.md`, the consumer `.claude/rules/cla-economy.md`, the
Sonnet launcher, the token meter, and any skill, script or agent added or removed.
Acceptance: every shipped path the docs name exists (`test_docs_name_shipped_paths.py` passes);
no doc still describes "never demoted" reviewers or round 2 after any fix.
