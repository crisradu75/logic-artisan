---
name: spec-to-pr-retro
description: "Review recent /cla:spec-to-pr runs across the fleet's spec-to-pr ledgers (warn reasons, round-cap exhaustion, per-agent Revise yield, ask answers, the --pr-rounds reversal check) and propose edits to the orchestrator. Run with /cla:spec-to-pr-retro."
argument-hint: "[N (last N runs per ledger, default 10)]"
# Slash-command only (a periodic retro over many runs): keeps this description out of the
# always-loaded skill listing. Nothing invokes it programmatically.
disable-model-invocation: true
---

# /cla:spec-to-pr-retro

Run it when Handoff prints a retro nudge, after about five new `/cla:spec-to-pr` runs, or when the loop feels off. For one run, read that run's record instead.

## Read

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr-retro/scripts/spec_to_pr_aggregate.py --limit <N>
```

`<N>` is `$ARGUMENTS`, or `10`. It reads every repo root in `cla.io/fleet.local.md` (absolute paths, per machine). When that file is missing or none of its roots exist here, it reads this repo's ledger and `source` says `local`. `--log <path>...` names ledgers instead.

## What each field means

- `ledgers`, `runs_analyzed`, `window`: the sample. `found: false` is a repo with no ledger yet; `skipped_records` counts lines it could not read (unmigrated or damaged). Under five runs is an anecdote: say so and stop.
- `warn_reasons`: a reason that recurs is one fix to make. Never rank `warn_reasons_unrecorded`.
- `cap_exhaustion.<phase>`: `hit/total` at or above 30% means the default cap is too low.
- `revise_findings.<agent>`: `found/runs` far below `code-reviewer`'s marks a trigger to narrow. `phantom/found` at or above 0.4 over five or more runs: demote that agent one tier, or narrow it. Never demote `code-reviewer` or `silent-failure-hunter`; spot-check two of their runs instead. `found` is Critical and Important together.
- `asks`: one answer chosen 80% of the time or more should become the default, with no prompt.
- `findings_by_round_reversal`: `condition_met: true` means the `--pr-rounds` reversal condition in spec-to-pr's Revise reference holds. Propose revisiting that default, citing the counts and `chain_proxy`.

## Report

Under 40 lines: the window, then the 2–4 patterns that would change the loop, each with its metric, then numbered edits (file and section, the exact change, the metric).

## Apply

Apply only the numbers the user picks. Never edit `openspec/**` or a script. The plugin is writable only when `${CLAUDE_PLUGIN_ROOT}` is inside `git rev-parse --show-toplevel`; otherwise send the edits to `/cla:report-upstream`.
