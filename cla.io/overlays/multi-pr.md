# multi-pr — project context overlay

<!--
Project-specific overlay for the `multi-pr` cla skill. This file is repo-local
(never distributed with the plugin). The generic SKILL.md supplies the procedure; this
file supplies the repo's facts. A skill runs fine against an empty stub — fill in
only the sections its SKILL.md references, delete the rest.
-->

## Repo commands
<!-- build/lint/test/dev commands with this repo's package-manager + workspace tokens -->

## Packages, paths, and app names
<!-- workspace/app/package/dir names and file paths this skill touches -->

## Permission sets
<!-- repo-scoped tool-permission expectations, if the skill uses them -->

## Incident / offense history

**No `/cla:multi-pr` chain has reached Phase 1c in this repo.** There is no
`cla.io/retro/multi-pr-run-notes-*.md` file — the file a chain first writes at Phase 1c step 4, and
appends measured actuals to at Phase 3 step 6. So this repo has no measured per-change timings, no
worktree-pivot precedent, and no stranded-docs precedent to offer; the two incidents below came
from landing a stack by hand, not from a chain.

`grep -rn "overlays/multi-pr" .claude/plugins/cla/` returns 9 pointers into this file, and most of
the sections they want are still empty stubs — including "Repo commands", which `change-loop.md`
and `cleanup.md` reach for as a build/lint/test fallback, and the local-stack and infra-gate
commands `discover-and-gate.md` names. Three of the 9 were reworded to read correctly when the
fact is absent (the stranded-docs precedent, the caps run-history statistic, the worktree pivot);
the rest are unhedged and will simply find nothing. Filling this file is the fix, not softening
more pointers.

**2026-08-14 — host classifier refused `gh pr merge` regardless of configuration.** In this repo,
on Claude Code with `--permission-mode auto`: `Bash(gh *)` present in `.claude/settings.local.json`,
`ALLOW_PR_MERGE=1` prefixed (the plugin's own hook confirmed it was disarmed), and the merge was
still refused by the host's auto-mode permission classifier — and refused again without
`--delete-branch`, and again after adding an explicit `Bash(gh pr merge *)` allowlist entry. This
is the measured basis for the stacked policy's "treat the first refusal as the answer" rule; the
6-PR remediation stack (#63-#68) was landed manually as a result.

**2026-08-14 (same day) — the deletion path closed a dependent PR despite documented retargeting.**
Landing that same stack: merging #63 with the delete flag CLOSED #64 (base: the deleted branch)
rather than retargeting it. Recovery: restore the deleted branch from the merge commit's second
parent, push it, reopen the PR, retarget it to main, delete the scaffold. The stacked landing
recipe is retarget-first because of this incident; the warn-stacked-pr-merge hook's close warning
is measured, not theoretical.
<!-- past failures in this repo that justify a discipline rule in the skill -->

## Product / domain context
<!-- this repo's applications, data, market, concepts -->

## Infrastructure values
<!-- ports, service names, env-var names tied to this repo's processes -->

## Repo file lists
<!-- enumerated specs/docs/files this skill is expected to touch -->
