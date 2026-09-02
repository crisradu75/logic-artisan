# multi-lite run notes — 2026-09-03

Input: `cla.io/decisions/open-issues-lane2-2026-09-03.md`
Base: `main` at `98e4d37`
Plan confirmed: all three candidates, A merged before B.

Task tracking via `TaskCreate` is unavailable in this session's toolset, so this
file is the sole progress record for the run.

| id | issue | status | branch | pr_number |
|---|---|---|---|---|
| test-interpreter | #198 | merged (`2d046ba`) | `fix/sys-executable-in-provenance-tests` | 202 |
| head-did-not-move | #199 | open, reviewed, fixes applied | `fix/provenance-hook-head-did-not-move` | 204 |
| trailer-block | #200 | open, reviewed, fixes applied | `docs/measured-by-trailer-block` | 203 |

## Notes

- **Live reproduction of #199 before the chain started.** While measuring for the
  decision doc, `git -C <scratch-repo> commit` in a scratch repository caused the
  PostToolUse hook to write two rows for `98e4d37` — this repo's HEAD, which did
  not move. Reverted with `git checkout -- cla.io/retro/commit-provenance.jsonl`.
  `git reflog -1 --format='%gs'` returned `pull --ff-only: Fast-forward` at that
  moment, so candidate B's reflog check would have suppressed both rows.

- **A third instance appeared during A's test run**, from
  `git diff -U0 cla.io/retro/commit-provenance.jsonl` — `\bcommit\b` matches
  inside the filename `commit-provenance`. Same fix covers it.

- **Deviation from the skill's contract, taken deliberately.** Candidate C ran as
  a delegated agent doing Implement/Test/Ship in a git worktree, in parallel with
  A and B, rather than as a nested `/cla:lite-pr` run in the primary clone. The
  user asked for the run to be sped up and C shares no files with A or B. Its
  Review phase was run from the orchestrator as normal, so the review layer was
  not weakened. Worth weighing before making it the default: a subagent cannot
  drive `lite-pr`'s phases, so the skill's Test-phase halt did not apply to C.

- **Two defects found while verifying, neither in scope, neither filed yet.**
  `_is_commit_command` returns False whenever a `git log` appears anywhere in the
  same Bash call, so a commit made in such a call is never recorded — the
  under-recording mirror of #199. And `mutants/hooks/` still does not exist, so
  B's fix shipped without a batch; re-creating that area would demand batches for
  12 further hook guards at once (#176).
