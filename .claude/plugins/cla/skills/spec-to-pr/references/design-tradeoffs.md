# Design trade-offs accepted by `/cla:spec-to-pr`

Reference material for design rationale that doesn't change run-to-run. Claude does not need to re-read this every workflow run; it's here for human readers and for re-reading when the design itself is being revised.

## Ship — inline `git` + `gh pr create`, minimal messages

Ship runs path-scoped `git add openspec/changes/<name>/ apps/<app>/src/ packages/<package>/src/` (the specific app/package paths touched — there is no repo-root `src/`) → `git commit -m "feat: <change-name>"` → `git push` → `gh pr create --title "feat: <change-name>" --body "Closes openspec/changes/<name>/. Checks: build + lint passed."`. No commit-msg or pr-body file is written, and never `git add -A` (see `bash-discipline.md`).

**Trade-off accepted:** commit subjects and PR bodies are minimal — no Summary section, no Test-plan checklist, no body explaining "why". The proposal under `openspec/changes/<name>/` is the why; the diff is the what; commit/PR text is just a marker. This is appropriate for a single-developer project where nobody reads PR descriptions to decide whether to merge. If the project ever grows to multi-reviewer, replace the single-line `--body "..."` with a `--body-file` build-up call and add the structure back.

Earlier versions delegated this phase to `commit-commands:commit-push-pr`, which auto-generated a verbose commit + PR body from the staged diff. Removed because that plugin re-prompted Claude with the diff and asked it to run the same shell commands, costing turns of indirection for output nobody read.

## Archive — archiving while PR still OPEN

Archive runs `openspec-archive-change` and commits the result to the PR branch BEFORE the user merges. When the user merges the PR, the archive is applied atomically with everything else.

**Trade-off accepted:** the archive runs while the PR is still `OPEN`. If the user later substantially modifies or rejects the PR, the archived state in `openspec/specs/` and `openspec/changes/archive/` is stale (visible in the PR diff but not yet in main). To unwind: revert the `chore: archive` commit on the PR branch and (if any portion was merged) manually re-extract the change from `archive/` back into `changes/`. The risk is acceptable because, in the typical autonomous workflow, the PR opened by Ship is reviewed in Revise and approved (any blocking issues would have manifested as Critical/Important findings and been fixed before this point).

## Continue-on-everything escalation

The orchestrator never halts on a sub-step failure. Every failure becomes a `warn` phase and a line in the terminal report's "Issues encountered" section.

**Trade-off accepted:** a failing `openspec validate` propagates downstream and may produce a PR built on broken artifacts. The user is the only safety net; the report and PR-body callouts are the surface that makes the safety net usable. The user explicitly chose this escalation policy in the explore session.

## Layer-1 wildcard permissions

`Bash(git *)`, `Bash(python *)`, etc. trust *all* invocations of those tools by Claude in the project.

**Trade-off accepted:** broader trust scope than per-subcommand allowlisting (`Bash(git status *)`, `Bash(git add *)`, ...). The narrower set in `references/required-permissions-narrow.json` is documented for users who want stricter allowlisting, but the default is the wildcard set because the user is already trusting the orchestrator with autonomous push and PR-open authority.

## Revise fix-round commits stay manual

Revise (PR-review fix rounds) commits as `fix: review round N` via a direct `git commit` rather than delegating to `commit-commands:commit-push-pr`.

**Trade-off accepted:** the round-N subject is structurally meaningful — it drives `probe_state.py`'s round counter and the round-N-on-fix-diff scoping. The plugin would auto-generate a different subject and break that contract.

## Revise round 1 — Workflow fan-out (round ≥2 stays direct-Agent)

Round 1 dispatches the review agents via one `Workflow` script instead of parallel `Agent` calls (see SKILL.md Revise + `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`). Chosen because `Workflow`'s `agent()` exposes the two knobs `Agent` lacks — per-call **effort** (opus bug-hunters at `medium` instead of inherited session effort) and **schema-forced findings** (no prose re-parsing) — and the merge/dedup runs in code at zero token cost.

**Trade-off accepted:** a second orchestration mechanism inside one phase, with quieter failure semantics (a crashed reviewer becomes a `null` in the results array rather than an inline error). Mitigated by two mandatory rules in SKILL.md: the completeness check (`reported < launched` → Revise `warn`) and the whole-Workflow-failure fallback to direct `Agent` dispatches. Round ≥2 stays on plain `Agent` calls — 1-2 small scoped dispatches don't repay the script overhead.

**The Workflow choice is NOT diff-size-gated (revised after a 7-change chain).** An early version of this guidance told the orchestrator to prefer direct `Agent` calls over `Workflow` for *large* diffs, reasoning that embedding a big diff in the script string risked backtick/quote breakage. Across a measured 7-change `multi-pr` run this diagnosis proved wrong on the causal variable: the first 3 changes avoided `Workflow` citing diff size and used direct `Agent` calls; the last 4 used `Workflow` cleanly on similarly-sized diffs — the only thing that changed was **how the diff reached the agent**. When the prompt *describes* the diff by file/symbol and tells the agent to read the hunks itself (`git diff <base-branch>..feature/<name>`), the script string carries no diff text at all, so its size is irrelevant and there is nothing to escape. When the diff is *pasted verbatim*, even a small one can corrupt the template literal. SKILL.md's Revise "Diff-embedding discipline" rule now makes describe-not-paste the mandatory technique and drops the size-based fallback framing entirely: `Workflow` is the default for round 1 at any diff size, and the direct-`Agent` fallback fires only on an actual `Workflow` failure, never pre-emptively on a size heuristic.

## Background moved out of SKILL.md

Rationale behind rules `SKILL.md` states in short form. Not read per run.

### Run logs and the PR-body scratch file

## Per-run scratch directory (created on demand)

Only created when Handoff needs to mirror multi-line issues into the PR body. Path:

```
temp/spec-to-pr-issues-<change-name>.md
```

(Single fixed name per change; overwritten on re-run. No timestamped directory.) Written only when the Issues section is non-empty AND too long to fit a single-line `--body`. Then `gh pr edit <#> --body-file temp/spec-to-pr-issues-<change-name>.md`.

If you find yourself wanting to write a multi-paragraph commit or PR body anyway — don't. The proposal.md and the diff are the spec; the commit/PR are markers.

**No per-phase JSON logs.** The orchestrator synthesizes the Handoff report directly from in-context phase outcomes. Mid-run resume across separate Claude sessions still works via `probe_state.py` (which reads repo state, not log files); the previous session's per-phase summaries are not recoverable, but resume picks up at the right phase regardless.

**One per-RUN JSONL line is fine and required.** After printing the Handoff report, Handoff step 5 appends a single counts-only JSON line via `${CLAUDE_PLUGIN_ROOT}/lib/log_run.py` to the repo's `cla.io/retro/spec-to-pr-runs.jsonl`, and Handoff step 6 commits that line onto the feature branch (`chore: spec-to-pr run log`) so it merges with the PR and syncs across machines via git — never left dangling as an uncommitted file (override the dir with `CLAUDE_RETRO_DIR`, in which case the commit is skipped). This is the data source for `/cla:spec-to-pr-retro`, which proposes orchestrator improvements based on patterns across runs (cap-exhaustion rates, agent dispatch frequency, ask choice distribution, recurring warn reasons). Per-phase mid-run logs remain forbidden; per-run terminal logs are the explicit exception.

### Task tracking

Do NOT use `TaskCreate` for per-phase progress — phase outcomes live in the orchestrator's working context and are emitted in the Handoff terminal report.

**Use `TaskCreate` when sub-work is parallel, gated by external state, or recoverable across sessions** — for example, applying 4 PR-review fixes from independent agents that the user might want to inspect mid-run, or diagnosing N test failures where the next session needs to know which were fixed. **Skip when sub-work is linearly sequential** (e.g. a 25-subtask Implement implementation that flows top-to-bottom from `tasks.md` — the tasks.md checkboxes ARE the task list; duplicating them in `TaskCreate` adds noise without adding signal). When in doubt, skip.

The harness may emit `<system-reminder>` nudges to use `TaskCreate`. These are generic; the rule above takes precedence.

### When not to use Skill()

Many sub-skills don't *execute* — they re-prompt Claude with their workflow text and ask Claude to run the same tool calls it would have run anyway. This costs 1–2 turns of indirection per invocation with no extra capability. Specifically:

- `Skill(pr-review-toolkit:review-pr)` — itself a dispatcher that calls `Agent` with `code-reviewer`/`silent-failure-hunter`/etc. Skip the hop and dispatch the agents directly.
- `Skill(commit-commands:commit-push-pr)` — re-prompts with the diff and asks Claude to run the same 4 shell commands. Inline them in Ship.
- `Skill(openspec-archive-change)` — wraps a single CLI call. Run `openspec archive --yes` directly in Archive.

Use `Skill()` only when the sub-skill genuinely encapsulates capability the orchestrator lacks (e.g. an MCP tool integration, a stateful workflow with its own internal probes). For review/commit/PR work, prefer `Agent(...)` (parallel, isolated context) or inline execution.

**Implement is the exception.** `Skill(openspec-apply-change)` carries non-trivial workflow logic (read tasks.md → for each subtask, locate the implementing module/test → edit → tick the checkbox → re-validate). The work is not a thin shell wrapper, so the indirection is worth it. **When to inline instead:** use direct `Edit`/`Write` calls when you already hold the relevant artifact + source text in context from Review and adding a `Skill()` hop would be pure indirection, OR when the work needs repo-specific side knowledge the skill doesn't carry (e.g. a packaging gotcha you need to apply mid-flight). Use judgment, not a subtask-count threshold.

### Session-model routing

The routable dispatches (Implement/Revise agents) follow `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`. The **inline** judgment moments — Propose authoring, the Review verdict, Revise triage — run at the session model, which the skill cannot change mid-run. To protect quality on a **sub-Opus session**, escalate the two highest-leverage of those *up*:

- **Propose authoring** (description / explore-result modes): dispatch the proposal/design/tasks authoring to an `opus` `Agent`, then continue inline.
- **RETHINK-borderline Review verdict**: when the inline review lands at the FIX-FIRST/RETHINK boundary, second it with an `opus` `Agent` fed the context brief before committing to the verdict.

On an **Opus session this is a no-op** (inline already is Opus). No flag — read the session model from the environment context. Record whether it fired in the run log (`routing.escalate_up_fired`, Handoff step 5). Full rationale + table: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`.

### Ticked-but-open tasks: the withdrawn scan

A mechanical scan for that shape was built and withdrawn — over this repo's own corpus it reached 6 lines of 173 ticked tasks and produced 0 true positives against 4 false ones, because the prose here sits on the task line rather than beneath it. Evidence and what a rebuild would need: issue #105.

### Why turn liveness is a check, not a prohibition

This is stated as a check rather than a prohibition deliberately: the rule above asks you to notice mid-flow that what you are writing *reads* as an ending, which is a judgement, and a real chain lost a round-trip to exactly that judgement going wrong — the author wrote the banned shape and then behaved like its reader. "Is there a tool call in this message?" needs no judgement. Dated incident: `cla.io/overlays/spec-to-pr.md` "Incident / offense history".

### Revise is part of the continuous flow

**Revise (PR review) is also in scope of "continuous".** The Revise Round 1 agent dispatch happens automatically after Ship's PR opens. Do NOT skip Revise when the user said "merge and clean" — that phrase is about post-Archive cleanup (merge + branch delete), not a directive to bypass review. If the user wants to skip review explicitly, they will say `--skip-review` or `no review`. (Past sessions have over-interpreted "merge and clean" as "skip review" — that was an error; review is part of the default flow.)

**Revise always runs the full agent dispatch per the agent-selection table** below. There is no "degraded" mode and no PR-count threshold that reduces agent count. The table is the source of truth: pick every row whose "Diff contains" condition matches the PR — `code-reviewer + silent-failure-hunter` for any logic / behavior code; `+ pr-test-analyzer` when tests are added; `+ type-design-analyzer` when new types are added; `+ comment-analyzer` when new comments / docs are added; `+ plugin-dev:skill-reviewer` when a `${CLAUDE_PLUGIN_ROOT}/skills/*/SKILL.md` frontmatter changes or a new skill is created. Sub-agents have their own context windows, so dispatching them consumes far less of the parent context than reading the diff inline would — the parent only sees each agent's final summary. If you find yourself drafting a "to save budget I'll only run 1 agent" rationale, delete it and dispatch every row the table says applies.

### History behind rules SKILL.md states briefly

- `<inherits>`: GitHub issues #98, #100, #102 — one chain in which three consecutive changes dropped the same obligation, each one internally consistent and silently wrong.
- Implement post-check: Issue #111 records three ticked tasks in one chain that asserted things that were false — including a mutation test that could not have failed anything — with every mechanical check passing all three.
- Test source-affecting list: `.py` is called out because it was once missing, and in a Python repo a real source change then did not register as source-affecting at all — the run reported a clean docs-only skip having gated nothing. A closed list reproduces that defect for every language it omits.
- Autonomy gate: a phase-boundary confirmation prompt is a regression against the documented contract — past sessions have lost ~5 minutes per pause to model-side gating that the SKILL.md never authorized.
- Handoff's three named subsections: measured — a fix round returned four items under one "not applied" heading — three legitimate holds and one genuinely cheap fix nobody had done.
- Review's multi-spec skip lives in spec-to-pr, not the checklist, because it decides which checklist parts run, not how any check behaves.
