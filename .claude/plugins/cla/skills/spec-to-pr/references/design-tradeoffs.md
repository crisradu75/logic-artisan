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

Revise (PR-review fix rounds) commits as `fix: review round N` via `commit.py` rather than delegating to `commit-commands:commit-push-pr`.

**Trade-off accepted:** the round-N subject is structurally meaningful — it drives `probe_state.py`'s round counter and the round-N-on-fix-diff scoping. The plugin would auto-generate a different subject and break that contract.

## Revise round 1 — Workflow fan-out (round ≥2 stays direct-Agent)

Round 1 dispatches the review agents via one `Workflow` script instead of parallel `Agent` calls (see SKILL.md Revise + `references/model-routing.md`). Chosen because `Workflow`'s `agent()` exposes the two knobs `Agent` lacks — per-call **effort** (opus bug-hunters at `medium` instead of inherited session effort) and **schema-forced findings** (no prose re-parsing) — and the merge/dedup runs in code at zero token cost.

**Trade-off accepted:** a second orchestration mechanism inside one phase, with quieter failure semantics (a crashed reviewer becomes a `null` in the results array rather than an inline error). Mitigated by two mandatory rules in SKILL.md: the completeness check (`reported < launched` → Revise `warn`) and the whole-Workflow-failure fallback to direct `Agent` dispatches. Round ≥2 stays on plain `Agent` calls — 1-2 small scoped dispatches don't repay the script overhead.

**The Workflow choice is NOT diff-size-gated (revised after a 7-change chain).** An early version of this guidance told the orchestrator to prefer direct `Agent` calls over `Workflow` for *large* diffs, reasoning that embedding a big diff in the script string risked backtick/quote breakage. Across a measured 7-change `multi-pr` run this diagnosis proved wrong on the causal variable: the first 3 changes avoided `Workflow` citing diff size and used direct `Agent` calls; the last 4 used `Workflow` cleanly on similarly-sized diffs — the only thing that changed was **how the diff reached the agent**. When the prompt *describes* the diff by file/symbol and tells the agent to read the hunks itself (`git diff <base-branch>..feature/<name>`), the script string carries no diff text at all, so its size is irrelevant and there is nothing to escape. When the diff is *pasted verbatim*, even a small one can corrupt the template literal. SKILL.md's Revise "Diff-embedding discipline" rule now makes describe-not-paste the mandatory technique and drops the size-based fallback framing entirely: `Workflow` is the default for round 1 at any diff size, and the direct-`Agent` fallback fires only on an actual `Workflow` failure, never pre-emptively on a size heuristic.
