# handoff — terminal report, PR-body mirror, run-log, discipline audit (full mechanics)

The Handoff phase's step-by-step procedure. `SKILL.md`'s Handoff stub carries the load-bearing invariants (the next-steps gating rule, the run-log-must-be-committed-not-dangling rule, the feature-branch-only guard); this file carries the report shape and the recipes.

## 1. Emit the terminal report inline

From the orchestrator's working memory of each phase. Use this exact shape (one section per row, in this order):
- Header: `## <change-name> — workflow complete` (or `… completed with issues` if any phase is `warn` or `fail`).
- PR URL + branch + mode + caps.
- Phases table: one row per phase with glyph (`✓` / `⚠` / `✗`), phase name, and the one-line summary you held in context for that phase.
- Counts at a glance: ✓/⚠/✗ phase tally; Critical/Important/Suggestion remaining; failing test names if any.
- Issues encountered: bulleted list of `warn`/`fail` outcomes from any phase. Empty section when there are none — print "(none)".
- **Deferred Known Issues:** bulleted list of every Critical/Important PR-review finding triaged as Deferred-Known-Issue in Revise, each with its one-line rationale. This section is the durable record of "we saw it, we chose not to fix it now, here's why." Empty section when there are none — print "(none)".
- Deferred to TODO.md: bulleted residue list (Suggestion-level only, plus any cap-exhausted untriaged residue). Empty when none.
- Next steps for you (see step 4 for the gating rule).

Render directly as Markdown text in the assistant turn. Do not write to a file or invoke a script.

## 2. Mirror the Issues encountered list into the PR body

Skip entirely when there are no issues.
- **Few short issues:** edit the body inline as one line — e.g. `gh pr edit <#> --body "Closes openspec/changes/<name>/. Checks: build + lint passed. Known issues: <comma-separated brief list>."`.
- **Long or multi-line issues:** write a single short Markdown body to `temp/spec-to-pr-issues-<change-name>.md` (one fixed file, overwritten on re-run — no per-run timestamped dir), then `gh pr edit <#> --body-file temp/spec-to-pr-issues-<change-name>.md`. The file body is intentionally terse: original one-liner + a `## Known issues` section with one bullet per issue. No restated test plan, no closing summary.

## 3. Persist Deferred-Known-Issues + Suggestions to TODO.md

Durable record beyond PR-body staleness. The PR body goes stale once the PR merges; `TODO.md` is the load-bearing follow-up tracker per repo CLAUDE.md ("Deferred ideas and follow-ups, organized by plugin"). When the Revise output has any Deferred-Known-Issues OR Suggestions:
- Append a single section to `TODO.md` at the repo root (create the file if absent) with the shape:
  ```
  ## Deferred from PR #<N> (<change-name>) — <YYYY-MM-DD>

  **Deferred-Known-Issues** (Important PR-review findings the team consciously deferred):
  - [Important] <issue> — rationale: <one line>
  - ...

  **Suggestions** (low-priority PR-review residue):
  - [Suggestion] <issue>
  - ...
  ```
- Stage + commit as `docs: TODO.md`. Push to the same feature branch (the user merges it with the rest of the PR; TODO.md becomes part of history).
- Skip entirely if BOTH lists are empty.
- This commit lands AFTER the archive commit, so the TODO.md edit reflects the final state. The pr-review agents do NOT re-review it (mechanical doc edit).

## 4. Next-steps gating (INVARIANT — also stubbed inline in SKILL.md)

The terminal report's "Next steps for you" section is gated on the overall phase tally:
- **All ✓:** print `gh pr merge <#> --squash --delete-branch` as the next step. Single line, no preamble.
- **Any ⚠ (warn):** print a "**Review warnings before merging.**" line FIRST, then list each ⚠ phase's one-line summary indented. Only after that — and on a new line — name `gh pr merge` as the eventual command. The intent: the user should not type `gh pr merge` without first reading what warned.
- **Any ✗ (fail):** print "**This PR is NOT ready to merge.**" and DO NOT name `gh pr merge` at all. List the failing phases. The user can override by typing merge themselves, but the report does not endorse it.

Do NOT name `openspec archive` in any case (Archive already did it).

## 5. Append the per-run record to the JSONL log

After the terminal report has been printed, serialize the in-context phase outcomes as a single JSON object and pipe it to `lib/log_run.py` (with `spec-to-pr-runs.jsonl` as its argument). **The exact JSON schema (every field `aggregate.py` reads, counts-only, under 4 KiB) and the per-field obligations live in `references/run-log-schema.md`** — follow that shape exactly; it is the contract `/cla:spec-to-pr-retro` consumes. **Include the `routing` object** (the per-dispatch model tally, `implement_delegated`, `escalate_up_fired`, and `revise_findings_by_tier` — keyed **per agent**, `found`/`phantom` counting Critical+Important only, Suggestions excluded) — it is the telemetry that lets the retro validate the routing table AND drives its per-agent yield heuristic; assemble it from the models you dispatched, whether Implement delegated, whether escalate-up fired, and the Revise triage outcome per agent.

**Failure is non-fatal.** If `log_run.py` exits non-zero (disk full, perms, oversize record), capture the stderr in the Handoff Issues section but do NOT mark the overall run as warn — a missing log line is a small loss; halting at the very end of a successful workflow is a large one.

## 6. Commit the run-log line to the feature branch (INVARIANT — so it ships with the PR, never dangles)

Step 5's `log_run.py` append leaves `cla.io/retro/spec-to-pr-runs.jsonl` dirty on the working tree. Commit that one-line append onto the feature branch so it merges atomically with the change instead of lingering as an uncommitted file. Committing it here on the feature branch avoids both the dangling file and a `block-direct-push-to-main.py` block on a later direct-to-main attempt.
- **Guard — feature branch only.** Do this ONLY when Ship opened a PR (HEAD is `<branch>`). If Ship was `skip` (still on `<base-branch>`, branch collision, or the autonomy gate was declined), SKIP this commit: a direct-to-base-branch push would be blocked, so leave the append as a local uncommitted change and note it in the Handoff Issues section for the user to place.
- **Skip when the log is out-of-repo.** If `CLAUDE_RETRO_DIR` points outside the repo, there is nothing tracked to stage — skip.
- Verify git-state, then path-scoped stage + commit + push (never `-A`):
  ```
  python3 ${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/scripts/git_state.py --expect-branch <branch>
  git add -- cla.io/retro/spec-to-pr-runs.jsonl
  git commit -m "chore: spec-to-pr run log"
  git push
  ```
- This commit lands AFTER the archive and optional `docs: TODO.md` commits and is NOT re-reviewed by the pr-review agents (mechanical, like the archive commit). It is the LAST commit of the run.

Steps 5 and 6 are the run's last two actions. If either was skipped, say so in the terminal report — a missing run-log line, or one left uncommitted, is a loose end the user should see now rather than a gap discovered later by `/cla:spec-to-pr-retro` finding a run absent from the ledger.
