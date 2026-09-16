# phase4 — Phase 4 final summary (full mechanics)

The Phase 4 summary shape. `SKILL.md`'s stub carries the load-bearing invariant; this file carries the exact summary sections.

This file used to also hold a "Log the run" recipe appending to
`cla.io/retro/multi-lite-runs.jsonl`. That ledger held 4 records across five
repos and no skill ever read it, so it was deleted along with the two other
unread chain ledgers. Only `spec-to-pr-runs` and `codify-runs` remain, because
only those two have a retro skill that consumes them.

## Phase 4 — Final summary

After every candidate has been run, merged or left open per the confirmed policy, quarantined, or skipped, summarize in this order:

- **Merge policy**: `merge-each-clean` or `merge-dependencies-only`, and whether it was confirmed at the gate or applied by the explicit-autonomy override. If merging stopped because the host refused a merge, say so here and name the candidate it happened on.
- **Shipped & merged**: id + PR number + merged commit. Under `merge-each-clean` this is every clean candidate; under `merge-dependencies-only` it is the dependencies merged to unblock their dependents.
- **Shipped & left open**: id + PR URL + the reason, taken from the candidate's ledger `status`. Under `merge-dependencies-only` a plain `open` means an independent awaiting the user's merge. Every other reason is something the user must act on before the PR can merge: `unresolved <severity> finding`, `conflicts`, `head moved`, `mergeability unknown`, `merge refused`, `merge refused earlier in the run`. List those first.
- **Failed**: id + the specific failing check (Test-phase halt), the `failed-review` finding, or the `failed-merge` reason.
- **Blocked by an upstream failure**: id + which failed upstream candidate blocked it.
- **Review fix rounds run**: which candidates needed a Phase 3 step 7 enforcement round, and whether it resolved the findings.
- **Out of scope**: the non-lite items skipped in Phase 1a, with their suggested route (`/cla:spec-to-pr` / `/cla:multi-spec`).
- **Next steps**: for each PR left open, the one action it needs (resolve the finding, resolve the conflict, or merge it). Point at re-running `/cla:multi-lite` after fixing a failed candidate — including a `failed-merge` one — to pick up its blocked-downstream subtree.

## Commit the run-notes file (best-effort)

The per-run notes file (`cla.io/retro/multi-lite-run-notes-<date>.md`, created in
Phase 1) is the resume artifact — commit it so a later session and another
machine can read it back. Whenever the last candidate's PR was left open, under either policy,
Phase 3 ends with HEAD on that candidate's feature branch, so **return
to `<base-branch>` first, unconditionally, whatever branch HEAD is on**:

```
git checkout <base-branch>
git pull
python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py --expect-branch <base-branch>
git add cla.io/retro/multi-lite-run-notes-<date>.md
git commit -m "chore: multi-lite run notes"
git push
```

**Verify the push landed** — `git rev-parse HEAD` vs `git ls-remote origin <base-branch>`, compared in-context — since this is a direct push, not one delegated to `commit-push-pr`. Best-effort and non-fatal: skip it entirely if the run finished in a reactive-worktree pivot (it may not be able to reach `<base-branch>`; note it and move on).

**If the push is blocked** by the repo's `pre-push` guard — the whole point of this step is a direct commit to `<base-branch>` — don't reach for `ALLOW_PUSH_TO_MAIN=1` as a routine workaround; that escape hatch is for a genuine emergency, not scheduled housekeeping. Fall back to a small branch + PR for just the notes file: `git checkout -b chore/multi-lite-run-notes`, commit there, push, `gh pr create`, then report the PR URL in the final summary as a "log PR — merge whenever" item. Note in the summary that this run took the fallback path.
