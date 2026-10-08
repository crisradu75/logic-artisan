# phase4 — Phase 4 final summary (full mechanics)

The Phase 4 summary shape. `SKILL.md`'s stub carries the load-bearing invariant; this file carries the exact summary sections.

This file used to also hold a "Log the run" recipe appending to
`cla.io/retro/multi-lite-runs.jsonl`. That ledger held 4 records across five
repos and no skill ever read it, so it was deleted along with the two other
unread chain ledgers. The ledgers that remain, and what reads each, are listed
in `cla-init`'s scaffold step.

## Phase 4 — Final summary

After every candidate has been run, merged or left open per the confirmed policy, quarantined, or skipped, summarize in this order:

- **Merge policy**: `merge-each-clean` or `merge-dependencies-only`, and whether it was confirmed at the gate or applied by the explicit-autonomy override. If merging stopped because the host refused a merge, say so here and name the candidate it happened on.
- **Shipped & merged**: id + PR number + the ledger's `merge_commit`. Under `merge-each-clean` this is every candidate that passed step 8. Under `merge-dependencies-only` it is every candidate that needed merging before a later one. Flag any that merged because step 8a found shared-state paths Phase 1a did not predict, and list the paths. Also flag any merged with `gate skipped: no source-affecting paths`, `behind base: merged tree not tested`, or `base not updated`.
- **Shared-state changes not merged** (only when present, and before every other section below): id + reason. Say that every later candidate was quarantined because the shared environment no longer matches the base.
- **Shipped & left open**: id + PR URL + the reason, taken from the candidate's ledger `status`. Under `merge-dependencies-only` a plain `open` means an independent awaiting the user's merge. Every other reason is something the user must act on before the PR can merge. List those first. Steps 2, 7 and 8 can write: `unresolved <severity> finding`, `fix not committed`, `push not verified`, `enforcement fix unverified`, `findings lost on resume`, `deferred findings not determinable`, `head moved`, `head moved since review`, `head unverifiable (ledger lost)`, `local head mismatch`, `uncommitted changes`, `full gate red: <failing check>`, `full gate unavailable`, `checks still pending`, `checks not green`, `checks not readable`, `conflicts`, `blocked by branch protection`, `draft`, `mergeability unknown`, `shared-state check failed`, `shared-state change not merged`, `queued: merges later outside this run`, `merge not confirmed (state <state>)`, `merge error: <first line of the error>`, `merge refused`, `merge refused earlier in the run`. A `queued` PR needs no action: say it will merge on its own once GitHub's queue or auto-merge runs.
- **Failed**: id + the specific failing check (Test-phase halt), the `failed-review` reason, the `failed-merge` reason, `failed — PR closed without merging`, or `failed — recorded PR not found`.
- **Blocked by an upstream failure**: id + which failed upstream candidate blocked it.
- **Review fix rounds run**: which candidates needed a Phase 3 step 7 enforcement round, and whether it resolved the findings.
- **Out of scope**: the non-lite items skipped in Phase 1a, with their suggested route (`/cla:spec-to-pr` / `/cla:multi-spec`).
- **Next steps**: for each PR left open, the one action it needs. A PR whose problem the user fixes by pushing commits (a finding, a conflict, a red gate) is theirs to review and merge by hand afterwards: a re-run never merges commits it did not test and review, and leaves that PR open as `head moved since review`. Point at re-running `/cla:multi-lite` for what a re-run does handle: finishing candidates an interruption left undecided, retrying merges that failed for a passing reason (pending checks, a host refusal in an earlier session), and picking up a blocked-downstream subtree once its upstream has merged.

## Commit the run-notes file (best-effort, the run's last action)

The per-run notes file (`cla.io/retro/multi-lite-run-notes-<date>.md`) is the resume artifact,
read from the working tree, and stays uncommitted while the run goes. At the end it rides the
chain's last open PR, never `<base-branch>`:

- **A PR from this run is still open** → on the branch of the last one in chain order:
  ```
  git checkout <branch>
  git pull
  python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py --expect-branch <branch>
  git add -- cla.io/retro/multi-lite-run-notes-*.md
  git commit -m "chore: multi-lite run notes"
  git push
  ```
  The glob also picks up an earlier run's notes left uncommitted. Verify the push landed
  (`git rev-parse HEAD` against `git ls-remote origin <branch>`, compared in-context), stay on
  that branch, and name the PR in the summary as carrying the notes. A re-run takes them back out
  of it first (`references/bootstrap-and-tracking.md`, Phase 2).
- **None is open** (every PR merged, or none was opened) → leave the file uncommitted and say so
  in the summary: nothing is left to resume, and the next run's Phase 4 glob commits it onto that
  run's last open PR.

Never commit or push the notes to `<base-branch>`, open a PR for them alone, or reach for
`ALLOW_PUSH_TO_MAIN=1`. Skip this step if the run finished in a reactive-worktree pivot, and say
so.
