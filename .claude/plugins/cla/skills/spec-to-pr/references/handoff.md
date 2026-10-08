# handoff — terminal report, PR-body mirror, TODO.md, run record

The Handoff phase's procedure. Why its gates are shaped as they are: `design-tradeoffs.md` "Handoff".

## 1. Emit the terminal report inline

From your working memory of each phase, as rendered Markdown in the assistant turn — never a file or a script. Sections in this order, "(none)" under an empty one:

- Header: `## <change-name> — workflow complete` (`… completed with issues` if any phase is `warn` or `fail`).
- PR URL + branch + mode + caps. When `<inherits>` was non-empty: one verdict line per supplied entry, `HONOURED` ones included, here ahead of the phase table, even on a resumed run that skipped Review.
- Phases table: one row per phase — glyph (`✓` / `⚠` / `✗`), phase name, the one-line summary you held for it.
- Counts at a glance: the ✓/⚠/✗ tally; Critical/Important/Suggestion remaining; failing test names, if any.
- Issues encountered: every `warn`/`fail` outcome from any phase.
- **Deferred Known Issues:** every Critical/Important Revise finding triaged Deferred-Known-Issue, each with its one-line rationale, **split into three named subsections, always, even when empty:**

  ```
  **Blocked on a missing artifact** — cannot be resolved now; name the artifact.
  **Trigger condition not yet fired** — the case it guards has not arisen yet.
  **Skipped** — no reason above applies.
  ```

  The first two are legitimate holds; **a non-empty `Skipped` fails Handoff.** Keep the headings verbatim so the check is a grep.
- **Rejected remedies, still open:** every Critical/Important finding a fix delegate rejected **citing the remedy** that the run did not close — one line each: the finding and the delegate's reason. Not a Deferred Known Issue (nobody chose to defer it) and not Suggestion residue: a live defect whose obvious fix was rejected. A finding closed by disproof does not appear here.
- Deferred to TODO.md: Suggestion-level residue, plus any cap-exhausted untriaged residue.
- Next steps for you (§4).

## 2. Mirror the issues into the PR body

Skip when there are no issues and no rejected remedies.
- **Few short issues:** one line — `gh pr edit <#> --body "Closes openspec/changes/<name>/. Checks: <the checks that ran>. Known issues: <comma-separated brief list>."`.
- **Long or multi-line:** write `temp/spec-to-pr-issues-<change-name>.md` (one fixed file, overwritten on re-run): the original one-liner plus a `## Known issues` section, one bullet per issue, then `gh pr edit <#> --body-file temp/spec-to-pr-issues-<change-name>.md`.

**Mirror "Rejected remedies, still open" first** — one line per finding with the delegate's reason. It is the most severe thing the body carries.

## 3. Persist to TODO.md

When there is ANY Deferred-Known-Issue, ANY rejected remedy still open, OR ANY Suggestion, append one section to the repo-root `TODO.md` (create it if absent):

```
## Deferred from PR #<N> (<change-name>) — <YYYY-MM-DD>

**Rejected remedies, still open** (findings whose proposed fix a delegate rejected with reasons; the defect is REAL and UNFIXED):
- [Critical] <issue> — remedy rejected because: <the delegate's reason>
- ...

**Deferred-Known-Issues** (Important PR-review findings the team consciously deferred):
- [Important] <issue> — rationale: <one line>
- ...

**Suggestions** (low-priority PR-review residue):
- [Suggestion] <issue>
- ...
```

Stage + commit as `docs: TODO.md` and push to the feature branch. Skip only when all three lists are empty — a run whose only residue is rejected-open findings still writes the section. This lands after the archive commit and is not re-reviewed.

## 4. Next-steps gating

Gated on the phase tally **and on "Rejected remedies, still open" being empty.** A non-empty one takes the **✗ branch** below even when every glyph is ✓, listing each open rejected finding with the delegate's reason in place of the failing phases. (It reaches Handoff with Revise `warn` — re-attempt or cap exhaustion — and the ⚠ branch would name `gh pr merge` over a live Critical; the section, not the glyph, tells the two apart.)
- **All ✓:** print `gh pr merge <#> --squash --delete-branch`, one line, no preamble. **Stacked child (`--pr-base` passed):** never a bare merge command — print "lands with its chain — see the multi-pr report"; the chain lands parents-first with merge commits.
- **Any ⚠:** print "**Review warnings before merging.**" FIRST, then each ⚠ phase's one-line summary indented, and only then, on a new line, `gh pr merge` as the eventual command.
- **Any ✗:** print "**This PR is NOT ready to merge.**", list the failing phases, and do NOT name `gh pr merge`.

Never name `openspec archive` (Archive did it).

## 5. Append the per-run record to the JSONL log

After the report, serialize the run as one JSON object and pipe it to `${CLAUDE_PLUGIN_ROOT}/lib/log_run.py` with `spec-to-pr-runs.jsonl` as its argument. **Build it from the example in `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/run-log-schema.md`, re-read now — not from memory.** `flags` comes from the invocation, `escalated_to_diagnose` from the count Test kept, `routing.revise_findings_by_tier` from each Revise agent's triage outcome, and Revise's `findings_by_round` from the entries written as each round closed — never reconstructed here.

**`log_run.py` refuses a record off the shape**, printing one line naming every field that is off. **Rebuild it from the example, fixing every field named, and pipe it again — once.** Refused again, or any other failure (disk, permissions, the 4 KiB ceiling) → the stderr line goes in Issues and the run finishes; it never marks the run `warn`.

**Then print the retro nudge**, whether or not the append succeeded:

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr-retro/scripts/spec_to_pr_aggregate.py --nudge
```

Print what it prints, verbatim, after the report: one line suggesting `/cla:spec-to-pr-retro`, or nothing. It never fails, never blocks, and changes nothing about the run's status.

## 6. Commit the run-log line to the feature branch

The append leaves `cla.io/retro/spec-to-pr-runs.jsonl` modified. Commit it onto the feature branch so it merges with the PR instead of dangling, or being pushed to the base branch later.
- **Guard — feature branch only.** Do this ONLY when Ship opened a PR (HEAD is `<branch>`). If Ship was `skip` (still on `<base-branch>`, a branch collision, a declined gate), leave the append uncommitted and say so in Issues.
- **Skip when the log is out-of-repo** (`CLAUDE_RETRO_DIR` outside the repo): nothing tracked to stage.
- Verify git state, then stage the one path, commit and push:
  ```
  python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py --expect-branch <branch>
  git add -- cla.io/retro/spec-to-pr-runs.jsonl
  git commit -m "chore: spec-to-pr run log"
  git push
  ```
- It is the LAST commit of the run, after the archive and optional `docs: TODO.md` commits, and is not re-reviewed.

Steps 5 and 6 are the run's last two actions. If either was skipped, say so in the report — a run-log line missing or left uncommitted is a loose end the user should see now.
