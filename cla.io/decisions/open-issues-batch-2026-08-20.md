# Decision: fix the open GitHub issues (#82, #61, #60)

Built 2026-08-20 to batch the repo's open issues through `/cla:multi-lite`. Issues #1
(mechanical-checks.mjs overlay-driven) and #62 (git_state.py `clean` field naming) were closed as
already resolved — both verified against current `main`, no fix needed.

Each candidate below was checked against current source before inclusion; none are stale.

## Candidates

| id | description | depends_on |
|---|---|---|
| `merge-hatch-message` | In `.claude/plugins/cla/hooks/ask-destructive-git.py`, fix the `gh pr merge` ask-hook message (around line 337-338): it currently tells the reader to set `ALLOW_DESTRUCTIVE_GIT=1` to skip the prompt, but that var is env-only and the reader's only lever is an inline command prefix, which silently no-ops. Change the merge-specific branch of the message to name `ALLOW_PR_MERGE=1` (already parsed from command text by `_ALLOW_MERGE_PREFIX` at line 221) as the way to authorize an unattended merge, prefixed on that one command. Leave the force-push/`reset --hard` branches pointing at `ALLOW_DESTRUCTIVE_GIT`, worded as "export" since those have no narrow equivalent. Closes GitHub issue #82. | — |
| `log-run-path-clarity` | In `.claude/plugins/cla/skills/spec-to-pr/SKILL.md` (lines 133 and 345), the references to `lib/log_run.py` are ambiguous about what they're relative to — a reader naturally checks `skills/spec-to-pr/lib/` (which doesn't exist) instead of the actual plugin-root `${CLAUDE_PLUGIN_ROOT}/lib/log_run.py`, and concludes the file is missing from the release when it isn't (verified present in tags cla--v0.9.3 and cla--v0.10.0). Change both references to the explicit `${CLAUDE_PLUGIN_ROOT}/lib/log_run.py` path so the location is unambiguous. Closes GitHub issue #61. | — |
| `readme-windows-install-note` | In `README.md`'s "Install (any repo)" section, add a Windows-specific note after the two install commands: warn that running the install via PowerShell's `Set-Location` registers a canonicalized path casing that later Git-Bash/session-launched paths may not match, causing `cla` to silently fail to load (case-sensitive match against `installed_plugins.json`). Recommend installing from the same shell sessions will launch with, and add a verification step (`claude plugin list` — expect "✔ enabled", not "✘ failed to load"). Closes GitHub issue #60. | — |

No dependencies between candidates — all three are independent, small, doc/script edits in
disjoint files. Document order above is the run order.

## Out of scope for multi-lite

None — all remaining open issues are lite-pr-sized.

## Next step

`/cla:multi-lite` on this doc, one PR per candidate, left open for review (none merge each other).
