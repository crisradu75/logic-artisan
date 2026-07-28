# phase4-and-log — Phase 4 final summary + the run-log recipe (full mechanics)

The Phase 4 summary shape and the "Log the run" recipe. `SKILL.md`'s stubs for these carry the load-bearing invariant (log-only, best-effort, never blocks the run); this file carries the exact summary sections and the log/commit commands.

## Phase 4 — Final summary

After every candidate has been run, merged-if-a-dependency, quarantined, or skipped, summarize in this order:

- **Shipped & merged** (dependencies that were merged to unblock dependents): id + PR number + merged commit.
- **Shipped & left open** (independents awaiting the user's merge): id + PR URL. Flag any that carry an `open — unresolved <severity> finding` note from Phase 3 step 7.
- **Failed**: id + the specific failing check (Test-phase halt) or `failed-review` finding.
- **Blocked by an upstream failure**: id + which failed upstream candidate blocked it.
- **Review fix rounds run**: which candidates needed a Phase 3 step 7 enforcement round, and whether it resolved the findings.
- **Out of scope**: the non-lite items skipped in Phase 1a, with their suggested route (`/cla:spec-to-pr` / `/cla:multi-spec`).
- **Next steps**: point at merging the open PRs, and at re-running `/cla:multi-lite` after fixing a failed candidate to pick up its blocked-downstream subtree.

## Log the run (best-effort, log-only)

After the summary, assemble one counts-only JSON record per `references/run-log-schema.md` and pipe it to the validating helper (the sibling of `/cla:multi-pr`'s `log_chain_run.py` — `json.loads`-validates, size-checks the 4-KiB atomic-append ceiling, and appends UTF-8 bytes directly, so a malformed line can't silently poison the ledger the way a raw `printf >>` would):

```
python3 .claude/plugins/cla/skills/multi-lite/scripts/log_run.py <<'JSON'
{"ts":"...", ...}
JSON
```

It appends to `cla.io/retro/multi-lite-runs.jsonl`. Then commit **both** the ledger line and the run-notes file. Because `multi-lite` leaves independents' PRs open, Phase 3 normally ends with the primary clone's HEAD on some candidate's feature branch (the dependency-ordered last candidate is typically independent, so it's left open rather than merged) — so **return to `<base-branch>` first, unconditionally, whatever branch HEAD is on** (this is why the run-log lands cleanly, unlike a naive `--expect-branch <base-branch>` check that would fail from a feature branch):

```
git checkout <base-branch>
git pull
python3 .claude/plugins/cla/skills/spec-to-pr/scripts/git_state.py --expect-branch <base-branch>
git add cla.io/retro/multi-lite-runs.jsonl cla.io/retro/multi-lite-run-notes-<date>.md
git commit -m "chore: multi-lite run log"
git push
```

**Verify the push landed** — `git rev-parse HEAD` vs `git ls-remote origin <base-branch>`, compared in-context — since this is a direct push, not one delegated to `commit-push-pr`. Best-effort and non-fatal — a missing log line never blocks the run; skip entirely if `CLAUDE_RETRO_DIR` points the ledger outside the repo, or if the run finished in a reactive-worktree pivot (it may not be able to reach `<base-branch>`; note it and move on). **No analyzer skill yet, by design** — same "wait until ~8–10 runs accumulate" posture the sibling chain skills take before proposing a retro analyzer.
